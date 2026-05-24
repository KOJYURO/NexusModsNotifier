from __future__ import annotations

import asyncio
from collections import OrderedDict
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import quote

try:
	import aiohttp
except Exception:
	aiohttp = None


def _safe_int(value: Any) -> int:
	try:
		return int(value or 0)
	except Exception:
		return 0


@dataclass(frozen=True)
class TwitchChatBridgeConfig:
	enabled: bool
	client_id: str
	client_secret: str
	discord_channel_id: str
	broadcaster_login: str = ""
	broadcaster_user_id: str = ""
	subscription_user_logins: tuple[str, ...] = ()
	user_access_token: str = ""
	refresh_token: str = ""
	request_timeout: int = 10
	relay_delete_after_seconds: int = 3600
	websocket_url: str = "wss://eventsub.wss.twitch.tv/ws"


class TwitchChatBridge:
	"""EventSub WebSocket で Twitch chat を Discord へ片方向転送する bridge。"""

	def __init__(
		self,
		config: TwitchChatBridgeConfig,
		state_lock: Any,
		state: dict[str, Any],
		load_authorization: Callable[[], dict[str, Any]],
		save_authorization: Callable[[dict[str, Any]], None],
		post_discord_message: Callable[[str, dict[str, Any], str, int | None], Awaitable[Any]],
		delete_discord_messages: Callable[[list[dict[str, Any]], str], Awaitable[dict[str, Any]]],
		sanitize_text: Callable[[Any], str],
		truncate_text: Callable[[Any, int], str],
		now_iso_utc: Callable[[], str],
	) -> None:
		self.config = config
		self.state_lock = state_lock
		self.state = state
		self._load_authorization = load_authorization
		self._save_authorization = save_authorization
		self._post_discord_message = post_discord_message
		self._delete_discord_messages = delete_discord_messages
		self._sanitize_text = sanitize_text
		self._truncate_text = truncate_text
		self._now_iso_utc = now_iso_utc
		self._thread: threading.Thread | None = None
		self._loop: asyncio.AbstractEventLoop | None = None
		self._websocket: Any = None
		self._stop_event = threading.Event()
		self._auth_lock = threading.Lock()
		self._recent_lock = threading.Lock()
		self._auth_cache: dict[str, Any] = {}
		self._recent_event_ids: list[str] = []
		self._recent_event_id_set: set[str] = set()
		# Twitch 側削除イベントに追従するため、直近 relay の対応表だけを短期保持する。
		self._relay_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
		self._recent_feed_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
		self._relay_user_index: dict[str, set[str]] = {}
		self._relay_index_max_size = 2000
		self._recent_feed_max_size = 200
		self._reconnect_url = ""
		self._subscription_types = [
			"channel.chat.message",
			"channel.chat.notification",
			"channel.chat.message_delete",
			"channel.chat.clear_user_messages",
			"channel.chat.clear",
		]
		self._update_state(
			enabled=bool(self.config.enabled),
			running=False,
			connected=False,
			awaiting_authorization=bool(self.config.enabled),
			relay_channel_id=self.config.discord_channel_id,
			subscription_broadcasters=[],
			subscribed_types=[],
			token_scopes=[],
			tracked_message_count=0,
			last_delete_sync_at=None,
			last_delete_reason="",
			last_delete_target="",
			last_delete_count=0,
			total_deleted_count=0,
			auth_source="env" if self.config.user_access_token else "file",
		)

	def state_snapshot(self) -> dict[str, Any]:
		with self.state_lock:
			return dict(self.state)

	def recent_items(self, limit: int = 20) -> list[dict[str, Any]]:
		max_items = max(1, min(_safe_int(limit or 20), 100))
		self._prune_relay_index()
		with self._recent_lock:
			items = [dict(item) for item in self._recent_feed_records.values()]
		items.reverse()
		return items[:max_items]

	def start(self) -> bool:
		if not self.config.enabled:
			self._update_state(enabled=False, running=False, connected=False, awaiting_authorization=False)
			return False

		if aiohttp is None:
			self._update_state(running=False, connected=False, last_error="aiohttp is not installed")
			return False

		if self._thread is not None and self._thread.is_alive():
			return True

		self._stop_event.clear()
		self._thread = threading.Thread(target=self._run_thread, name="twitch-chat-bridge", daemon=True)
		self._thread.start()
		return True

	def stop(self) -> None:
		self._stop_event.set()
		loop = self._loop
		ws = self._websocket
		if loop is not None and ws is not None:
			try:
				asyncio.run_coroutine_threadsafe(ws.close(), loop)
			except Exception:
				pass
		if loop is not None:
			try:
				loop.call_soon_threadsafe(lambda: None)
			except Exception:
				pass
		thread = self._thread
		if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
			try:
				thread.join(timeout=5)
			except Exception:
				pass
		self._thread = None
		self._update_state(running=False, connected=False, session_id="", subscribed_types=[])

	async def send_chat_message_async(self, message_text: str) -> dict[str, Any]:
		if aiohttp is None:
			raise RuntimeError("aiohttp is not installed")

		message = self._sanitize_text(message_text)
		if not message:
			raise RuntimeError("message is empty")
		if len(message) > 500:
			raise RuntimeError("message is too long for Twitch chat")

		timeout = aiohttp.ClientTimeout(total=max(5, int(self.config.request_timeout or 10)))
		async with aiohttp.ClientSession(timeout=timeout) as session:
			identity = await self._ensure_identity(session, require_read_scope=False, require_write_scope=True)
			payload = {
				"broadcaster_id": identity["broadcaster_user_id"],
				"sender_id": identity["sender_user_id"],
				"message": message,
			}
			response = await self._helix_request_json(
				session,
				method="POST",
				url="https://api.twitch.tv/helix/chat/messages",
				payload=payload,
			)
			rows = response.get("data", []) if isinstance(response, dict) else []
			if not isinstance(rows, list) or not rows:
				raise RuntimeError("send chat message response is invalid")
			row = rows[0] if isinstance(rows[0], dict) else {}
			if not bool(row.get("is_sent", False)):
				drop_reason = row.get("drop_reason") if isinstance(row.get("drop_reason"), dict) else {}
				raise RuntimeError(self._sanitize_text(drop_reason.get("message", "Twitch rejected the chat message")))

			self._update_state(
				last_command=message,
				last_command_at=self._now_iso_utc(),
				last_error="",
			)
			return {
				"ok": True,
				"message": message,
				"message_id": self._sanitize_text(row.get("message_id", "")),
				"sent_at": self._now_iso_utc(),
				"broadcaster_login": identity["broadcaster_login"],
				"sender_login": identity["sender_login"],
			}

	def _run_thread(self) -> None:
		loop = asyncio.new_event_loop()
		self._loop = loop
		asyncio.set_event_loop(loop)
		try:
			loop.run_until_complete(self._worker_loop())
		finally:
			self._loop = None
			try:
				loop.run_until_complete(loop.shutdown_asyncgens())
			except Exception:
				pass
			loop.close()

	async def _worker_loop(self) -> None:
		self._update_state(running=True, last_error="")
		backoff_seconds = 5
		current_url = self.config.websocket_url
		resubscribe = True

		try:
			while not self._stop_event.is_set():
				auth = self._current_authorization(force_reload=True)
				if not auth.get("access_token"):
					self._update_state(
						connected=False,
						awaiting_authorization=True,
						last_error="",
						session_id="",
						subscribed_types=[],
					)
					await self._sleep_with_stop(10)
					continue

				try:
					reconnect_url, resubscribe = await self._listen_once(current_url, resubscribe)
					if reconnect_url:
						current_url = reconnect_url
						backoff_seconds = 5
						continue
					current_url = self.config.websocket_url
					resubscribe = True
					await self._sleep_with_stop(backoff_seconds)
					backoff_seconds = min(backoff_seconds * 2, 60)
				except Exception as exc:
					self._update_state(
						connected=False,
						awaiting_authorization=False,
						last_error=self._sanitize_text(str(exc)),
						session_id="",
						subscribed_types=[],
					)
					current_url = self.config.websocket_url
					resubscribe = True
					await self._sleep_with_stop(backoff_seconds)
					backoff_seconds = min(backoff_seconds * 2, 60)
		finally:
			self._update_state(running=False, connected=False, session_id="", subscribed_types=[])

	async def _listen_once(self, websocket_url: str, resubscribe: bool) -> tuple[str, bool]:
		timeout = aiohttp.ClientTimeout(total=None, sock_connect=max(5, int(self.config.request_timeout or 10)))
		async with aiohttp.ClientSession(timeout=timeout) as session:
			identity = await self._ensure_identity(session, require_read_scope=True, require_write_scope=False)
			self._update_state(
				awaiting_authorization=False,
				sender_login=identity["sender_login"],
				sender_user_id=identity["sender_user_id"],
				broadcaster_login=identity["broadcaster_login"],
				broadcaster_user_id=identity["broadcaster_user_id"],
			)

			try:
				async with session.ws_connect(websocket_url, heartbeat=None, autoping=True) as ws:
					self._websocket = ws
					receive_timeout = 30
					while not self._stop_event.is_set():
						message = await ws.receive(timeout=receive_timeout)
						if message.type == aiohttp.WSMsgType.CLOSED:
							raise RuntimeError("Twitch EventSub websocket closed")
						if message.type == aiohttp.WSMsgType.ERROR:
							raise RuntimeError("Twitch EventSub websocket error")
						if message.type != aiohttp.WSMsgType.TEXT:
							continue

						payload = json.loads(message.data)
						metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
						message_type = self._sanitize_text(metadata.get("message_type", ""))
						self._update_state(last_event_type=message_type or "unknown", last_event_at=self._now_iso_utc())

						if message_type == "session_welcome":
							session_data = payload.get("payload", {}).get("session", {}) if isinstance(payload.get("payload"), dict) else {}
							session_id = self._sanitize_text(session_data.get("id", ""))
							keepalive_timeout = _safe_int(session_data.get("keepalive_timeout_seconds", 10))
							receive_timeout = max(30, keepalive_timeout + 15)
							self._update_state(connected=True, session_id=session_id, last_error="")
							if resubscribe:
								await self._subscribe_to_chat(session, session_id, identity)
								self._update_state(subscribed_types=list(self._subscription_types))
							resubscribe = False
							continue

						if message_type == "session_keepalive":
							self._update_state(connected=True)
							continue

						if message_type == "session_reconnect":
							session_data = payload.get("payload", {}).get("session", {}) if isinstance(payload.get("payload"), dict) else {}
							reconnect_url = self._sanitize_text(session_data.get("reconnect_url", ""))
							self._update_state(connected=False, session_id="")
							return reconnect_url, False

						if message_type == "revocation":
							subscription = payload.get("payload", {}).get("subscription", {}) if isinstance(payload.get("payload"), dict) else {}
							reason = self._sanitize_text(subscription.get("status", "subscription revoked"))
							raise RuntimeError("twitch subscription revoked: {}".format(reason or "unknown reason"))

						if message_type != "notification":
							continue

						await self._handle_notification(payload)
			finally:
				self._websocket = None

		return "", True

	async def _handle_notification(self, payload: dict[str, Any]) -> None:
		metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
		payload_data = payload.get("payload", {}) if isinstance(payload.get("payload"), dict) else {}
		subscription = payload_data.get("subscription", {}) if isinstance(payload_data.get("subscription"), dict) else {}
		event = payload_data.get("event", {}) if isinstance(payload_data.get("event"), dict) else {}
		event_type = self._sanitize_text(subscription.get("type", ""))
		delivery_id = self._sanitize_text(metadata.get("message_id", ""))
		if delivery_id and self._is_duplicate_event(delivery_id):
			return

		if event_type in ("channel.chat.message_delete", "channel.chat.clear_user_messages", "channel.chat.clear"):
			await self._handle_delete_notification(event_type, event)
			return

		content = self._build_discord_content(event_type, event)
		if not content:
			return

		delete_after = max(0, _safe_int(self.config.relay_delete_after_seconds or 0)) or None
		discord_message = await self._post_discord_message(event_type, event, content, delete_after)
		if discord_message is None:
			return
		self._remember_relay(event_type, event, discord_message, delete_after, content)
		self._update_state(
			last_relayed_at=self._now_iso_utc(),
			last_message_preview=self._truncate_text(content, 180),
			last_error="",
		)

	async def _handle_delete_notification(self, event_type: str, event: dict[str, Any]) -> None:
		self._prune_relay_index()

		target_message_ids: list[str] = []
		target_label = ""
		if event_type == "channel.chat.message_delete":
			message_id = self._sanitize_text(event.get("message_id", ""))
			if message_id:
				target_message_ids = [message_id]
			target_label = message_id
		elif event_type == "channel.chat.clear_user_messages":
			target_user_id = self._sanitize_text(event.get("target_user_id", ""))
			target_message_ids = self._message_ids_for_user(target_user_id)
			target_label = target_user_id or self._sanitize_text(event.get("target_user_login", ""))
		elif event_type == "channel.chat.clear":
			target_message_ids = list(self._relay_records.keys())
			target_label = "all"

		recorded_at = self._now_iso_utc()
		if not target_message_ids:
			self._update_state(
				last_delete_sync_at=recorded_at,
				last_delete_reason=event_type,
				last_delete_target=self._truncate_text(target_label or event_type, 120),
				last_delete_count=0,
				tracked_message_count=len(self._relay_records),
				last_error="",
			)
			return

		records = []
		for twitch_message_id in target_message_ids:
			record = self._relay_records.get(twitch_message_id)
			if record:
				records.append(record)
		if not records:
			self._update_state(
				last_delete_sync_at=recorded_at,
				last_delete_reason=event_type,
				last_delete_target=self._truncate_text(target_label or event_type, 120),
				last_delete_count=0,
				tracked_message_count=len(self._relay_records),
				last_error="",
			)
			return

		discord_to_twitch = {
			self._sanitize_text(record.get("discord_message_id", "")): self._sanitize_text(record.get("twitch_message_id", ""))
			for record in records
			if self._sanitize_text(record.get("discord_message_id", "")) and self._sanitize_text(record.get("twitch_message_id", ""))
		}

		try:
			result = await self._delete_discord_messages(records, event_type)
		except Exception as exc:
			self._update_state(
				last_delete_sync_at=recorded_at,
				last_delete_reason=event_type,
				last_delete_target=self._truncate_text(target_label or event_type, 120),
				last_delete_count=0,
				tracked_message_count=len(self._relay_records),
				last_error=self._sanitize_text(str(exc)),
			)
			return

		deleted_or_missing: list[str] = []
		for field_name in ("deleted_ids", "missing_ids"):
			for discord_message_id in result.get(field_name, []) if isinstance(result.get(field_name), list) else []:
				twitch_message_id = discord_to_twitch.get(self._sanitize_text(discord_message_id))
				if twitch_message_id:
					deleted_or_missing.append(twitch_message_id)
		for twitch_message_id in deleted_or_missing:
			self._forget_relay_record(twitch_message_id)

		current_total = _safe_int(self.state_snapshot().get("total_deleted_count", 0))
		delete_count = _safe_int(result.get("deleted", 0))
		self._update_state(
			last_delete_sync_at=recorded_at,
			last_delete_reason=event_type,
			last_delete_target=self._truncate_text(target_label or event_type, 120),
			last_delete_count=delete_count,
			total_deleted_count=current_total + delete_count,
			tracked_message_count=len(self._relay_records),
			last_error=self._sanitize_text(result.get("error", "")),
		)

	async def _subscribe_to_chat(self, session: Any, session_id: str, identity: dict[str, str]) -> None:
		if not session_id:
			raise RuntimeError("twitch websocket session id is empty")

		targets = await self._resolve_subscription_targets(session, identity)
		subscribed_broadcasters: list[str] = []
		failed_targets: list[str] = []

		for target in targets:
			target_login = self._sanitize_text(target.get("broadcaster_login", ""))
			target_user_id = self._sanitize_text(target.get("broadcaster_user_id", ""))
			if not target_login or not target_user_id:
				continue

			target_failed = False
			for event_type in self._subscription_types:
				payload = {
					"type": event_type,
					"version": "1",
					"condition": {
						"broadcaster_user_id": target_user_id,
						"user_id": identity["sender_user_id"],
					},
					"transport": {
						"method": "websocket",
						"session_id": session_id,
					},
				}
				try:
					await self._helix_request_json(
						session,
						method="POST",
						url="https://api.twitch.tv/helix/eventsub/subscriptions",
						payload=payload,
					)
				except RuntimeError as exc:
					message = self._sanitize_text(str(exc)).lower()
					if "already exists" in message or "conflict" in message:
						continue
					target_failed = True
					failed_targets.append("{}: {}".format(target_login, self._sanitize_text(str(exc))))
					break

			if not target_failed:
				subscribed_broadcasters.append(target_login)

		self._update_state(subscription_broadcasters=subscribed_broadcasters)
		if not subscribed_broadcasters:
			raise RuntimeError(
				"twitch chat subscription failed for all broadcasters: {}".format(
					"; ".join(failed_targets[:3]) or "unknown error"
				)
			)

		if failed_targets:
			self._update_state(last_error=self._truncate_text("; ".join(failed_targets[:3]), 400))

	async def _resolve_subscription_targets(self, session: Any, identity: dict[str, str]) -> list[dict[str, str]]:
		seen_user_ids: set[str] = set()
		targets: list[dict[str, str]] = []

		configured_logins = []
		for raw_login in self.config.subscription_user_logins or ():
			login = self._sanitize_text(raw_login).lower()
			if login and login not in configured_logins:
				configured_logins.append(login)

		if configured_logins:
			rows = await self._fetch_users(session, logins=configured_logins)
			for row in rows:
				user_id = self._sanitize_text(row.get("id", ""))
				login = self._sanitize_text(row.get("login", "")).lower()
				if not user_id or not login or user_id in seen_user_ids:
					continue
				seen_user_ids.add(user_id)
				targets.append({
					"broadcaster_user_id": user_id,
					"broadcaster_login": login,
				})

		fallback_user_id = self._sanitize_text(identity.get("broadcaster_user_id", ""))
		fallback_login = self._sanitize_text(identity.get("broadcaster_login", "")).lower()
		if (not targets) and fallback_user_id and fallback_login and fallback_user_id not in seen_user_ids:
			seen_user_ids.add(fallback_user_id)
			targets.append({
				"broadcaster_user_id": fallback_user_id,
				"broadcaster_login": fallback_login,
			})

		return targets

	async def _ensure_identity(
		self,
		session: Any,
		require_read_scope: bool,
		require_write_scope: bool,
	) -> dict[str, str]:
		validate = await self._validate_user_token(session)
		scopes = set([self._sanitize_text(item) for item in validate.get("scopes", []) if self._sanitize_text(item)])
		if require_read_scope and "user:read:chat" not in scopes:
			raise RuntimeError("Twitch user token requires user:read:chat scope")
		if require_write_scope and "user:write:chat" not in scopes:
			raise RuntimeError("Twitch user token requires user:write:chat scope")

		sender_user_id = self._sanitize_text(validate.get("user_id", ""))
		sender_login = self._sanitize_text(validate.get("login", ""))
		if not sender_user_id or not sender_login:
			raise RuntimeError("Twitch user token validation did not return user identity")

		broadcaster_user_id = self._sanitize_text(self.config.broadcaster_user_id)
		broadcaster_login = self._sanitize_text(self.config.broadcaster_login)

		if broadcaster_user_id and not broadcaster_login:
			rows = await self._fetch_users(session, user_ids=[broadcaster_user_id])
			if not rows:
				raise RuntimeError("configured Twitch broadcaster_user_id was not found")
			broadcaster_login = self._sanitize_text(rows[0].get("login", ""))
		elif broadcaster_login and not broadcaster_user_id:
			rows = await self._fetch_users(session, logins=[broadcaster_login])
			if not rows:
				raise RuntimeError("configured Twitch broadcaster_login was not found")
			broadcaster_user_id = self._sanitize_text(rows[0].get("id", ""))
		elif not broadcaster_user_id and not broadcaster_login:
			broadcaster_user_id = sender_user_id
			broadcaster_login = sender_login

		self._update_state(
			token_scopes=sorted(scopes),
			token_expires_in=_safe_int(validate.get("expires_in", 0)),
			sender_user_id=sender_user_id,
			sender_login=sender_login,
			broadcaster_user_id=broadcaster_user_id,
			broadcaster_login=broadcaster_login,
		)

		return {
			"sender_user_id": sender_user_id,
			"sender_login": sender_login,
			"broadcaster_user_id": broadcaster_user_id,
			"broadcaster_login": broadcaster_login,
		}

	async def _validate_user_token(self, session: Any, allow_refresh: bool = True) -> dict[str, Any]:
		auth = self._current_authorization(force_reload=False)
		access_token = self._sanitize_text(auth.get("access_token", ""))
		if not access_token:
			raise RuntimeError("Twitch chat authorization is not configured")

		headers = {"Authorization": "OAuth {}".format(access_token)}
		async with session.get("https://id.twitch.tv/oauth2/validate", headers=headers) as resp:
			if resp.status == 401:
				if allow_refresh:
					await self._refresh_user_token(session)
					return await self._validate_user_token(session, allow_refresh=False)
				raise RuntimeError("Twitch user token is invalid or expired")
			raw = await resp.text()
			if resp.status >= 400:
				raise RuntimeError("Twitch validate failed: {} {}".format(resp.status, self._sanitize_text(raw)))
			data = json.loads(raw) if raw.strip() else {}
			if not isinstance(data, dict):
				raise RuntimeError("Twitch validate response is invalid")

			data["scopes"] = [self._sanitize_text(item) for item in data.get("scopes", []) if self._sanitize_text(item)]
			data["source"] = auth.get("source", "file")
			return data

	async def _refresh_user_token(self, session: Any) -> dict[str, Any]:
		auth = self._current_authorization(force_reload=True)
		refresh_token = self._sanitize_text(auth.get("refresh_token", ""))
		if not refresh_token:
			raise RuntimeError("Twitch refresh token is not configured")
		if not self.config.client_id or not self.config.client_secret:
			raise RuntimeError("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set")

		params = {
			"grant_type": "refresh_token",
			"refresh_token": refresh_token,
			"client_id": self.config.client_id,
			"client_secret": self.config.client_secret,
		}
		async with session.post("https://id.twitch.tv/oauth2/token", params=params) as resp:
			raw = await resp.text()
			if resp.status >= 400:
				raise RuntimeError("Twitch token refresh failed: {} {}".format(resp.status, self._sanitize_text(raw)))
			data = json.loads(raw) if raw.strip() else {}
			if not isinstance(data, dict):
				raise RuntimeError("Twitch token refresh response is invalid")

			updated = {
				"access_token": self._sanitize_text(data.get("access_token", "")),
				"refresh_token": self._sanitize_text(data.get("refresh_token", refresh_token)),
				"updated_at": self._now_iso_utc(),
				"source": auth.get("source", "file"),
			}
			for key in ("user_id", "login", "scopes"):
				if key in auth:
					updated[key] = auth.get(key)
			if not updated["access_token"]:
				raise RuntimeError("Twitch token refresh response has no access_token")

			self._set_authorization(updated, persist=updated.get("source") != "env")
			self._update_state(last_error="", auth_source=updated.get("source", "file"))
			return updated

	async def _fetch_users(self, session: Any, user_ids: list[str] | None = None, logins: list[str] | None = None) -> list[dict[str, Any]]:
		query_parts = []
		for user_id in user_ids or []:
			text = self._sanitize_text(user_id)
			if text:
				query_parts.append("id={}".format(quote(text)))
		for login in logins or []:
			text = self._sanitize_text(login)
			if text:
				query_parts.append("login={}".format(quote(text)))
		if not query_parts:
			return []

		response = await self._helix_request_json(
			session,
			method="GET",
			url="https://api.twitch.tv/helix/users?{}".format("&".join(query_parts)),
		)
		rows = response.get("data", []) if isinstance(response, dict) else []
		if not isinstance(rows, list):
			return []
		return [row for row in rows if isinstance(row, dict)]

	async def _helix_request_json(
		self,
		session: Any,
		method: str,
		url: str,
		payload: dict[str, Any] | None = None,
		allow_refresh: bool = True,
	) -> dict[str, Any]:
		auth = self._current_authorization(force_reload=False)
		access_token = self._sanitize_text(auth.get("access_token", ""))
		if not access_token:
			raise RuntimeError("Twitch chat authorization is not configured")

		headers = {
			"Authorization": "Bearer {}".format(access_token),
			"Client-Id": self.config.client_id,
			"Content-Type": "application/json",
			"User-Agent": "DiscordBotBridge/1.0",
		}

		kwargs: dict[str, Any] = {"headers": headers}
		if payload is not None:
			kwargs["json"] = payload

		async with session.request(method.upper(), url, **kwargs) as resp:
			raw = await resp.text()
			if resp.status == 401 and allow_refresh:
				await self._refresh_user_token(session)
				return await self._helix_request_json(session, method, url, payload=payload, allow_refresh=False)
			if resp.status >= 400:
				raise RuntimeError("Twitch API failed: {} {}".format(resp.status, self._sanitize_text(raw)))
			data = json.loads(raw) if raw.strip() else {}
			if not isinstance(data, dict):
				raise RuntimeError("Twitch API response is invalid")
			return data

	def _build_discord_content(self, event_type: str, event: dict[str, Any]) -> str:
		chatter_name = self._sanitize_text(event.get("chatter_user_name", "") or event.get("chatter_user_login", ""))
		broadcaster_login = self._sanitize_text(event.get("broadcaster_user_login", "") or self.state_snapshot().get("broadcaster_login", ""))
		source_url = "https://www.twitch.tv/{}".format(broadcaster_login) if broadcaster_login else "https://www.twitch.tv"
		source_text = "<{}>".format(source_url)

		if event_type == "channel.chat.notification":
			system_message = self._sanitize_text(event.get("system_message", ""))
			if not system_message:
				notice_type = self._sanitize_text(event.get("notice_type", "notification"))
				system_message = "{} notification".format(notice_type)
			content = "[Twitch notice] {}\nSource: {}".format(system_message, source_text)
			return self._truncate_text(content, 1900)

		message = event.get("message", {}) if isinstance(event.get("message"), dict) else {}
		text = self._sanitize_text(message.get("text", ""))
		if not text:
			parts = []
			for fragment in message.get("fragments", []) if isinstance(message.get("fragments"), list) else []:
				if not isinstance(fragment, dict):
					continue
				piece = self._sanitize_text(fragment.get("text", ""))
				if piece:
					parts.append(piece)
			text = self._sanitize_text(" ".join(parts))
		if not text:
			return ""

		prefix = "[Twitch] {}".format(chatter_name or "unknown")
		content = "{}: {}\nSource: {}".format(prefix, text, source_text)
		return self._truncate_text(content, 1900)

	def _is_duplicate_event(self, event_id: str) -> bool:
		identifier = self._sanitize_text(event_id)
		if not identifier:
			return False
		if identifier in self._recent_event_id_set:
			return True
		self._recent_event_ids.append(identifier)
		self._recent_event_id_set.add(identifier)
		while len(self._recent_event_ids) > 500:
			old_id = self._recent_event_ids.pop(0)
			self._recent_event_id_set.discard(old_id)
		return False

	def _remember_relay(self, event_type: str, event: dict[str, Any], discord_message: Any, delete_after: int | None, content: str) -> None:
		twitch_message_id = self._sanitize_text(event.get("message_id", ""))
		if not twitch_message_id:
			self._prune_relay_index()
			return

		discord_message_id = ""
		if isinstance(discord_message, dict):
			discord_message_id = self._sanitize_text(
				discord_message.get("id", "")
				or discord_message.get("message_id", "")
			)
		else:
			discord_message_id = self._sanitize_text(getattr(discord_message, "id", ""))
		if not discord_message_id:
			self._prune_relay_index()
			return

		chatter_user_id = self._sanitize_text(
			event.get("chatter_user_id", "")
			or event.get("user_id", "")
			or event.get("target_user_id", "")
		)
		discord_channel_id = ""
		if isinstance(discord_message, dict):
			discord_channel_id = self._sanitize_text(
				discord_message.get("channel_id", "")
				or discord_message.get("thread_id", "")
			)
		else:
			discord_channel_id = self._sanitize_text(getattr(getattr(discord_message, "channel", None), "id", ""))
		record = {
			"twitch_message_id": twitch_message_id,
			"discord_message_id": discord_message_id,
			"discord_channel_id": discord_channel_id,
			"user_id": chatter_user_id,
			"event_type": event_type,
			"created_at_ts": time.time(),
			"delete_at_ts": time.time() + float(delete_after) if delete_after else 0.0,
		}

		self._forget_relay_record(twitch_message_id)
		self._relay_records[twitch_message_id] = record
		if chatter_user_id:
			self._relay_user_index.setdefault(chatter_user_id, set()).add(twitch_message_id)
		recent_item = self._build_recent_feed_item(event_type, event, content)
		with self._recent_lock:
			self._recent_feed_records[twitch_message_id] = recent_item
			while len(self._recent_feed_records) > self._recent_feed_max_size:
				self._recent_feed_records.popitem(last=False)
		self._prune_relay_index()
		self._update_state(tracked_message_count=len(self._relay_records))

	def _forget_relay_record(self, twitch_message_id: str) -> None:
		identifier = self._sanitize_text(twitch_message_id)
		if not identifier:
			return
		record = self._relay_records.pop(identifier, None)
		if not isinstance(record, dict):
			return
		with self._recent_lock:
			self._recent_feed_records.pop(identifier, None)
		user_id = self._sanitize_text(record.get("user_id", ""))
		if user_id:
			user_records = self._relay_user_index.get(user_id)
			if user_records is not None:
				user_records.discard(identifier)
				if not user_records:
					self._relay_user_index.pop(user_id, None)

	def _message_ids_for_user(self, user_id: str) -> list[str]:
		target_user_id = self._sanitize_text(user_id)
		if not target_user_id:
			return []
		target_messages = self._relay_user_index.get(target_user_id, set())
		if not target_messages:
			return []
		return [message_id for message_id in self._relay_records.keys() if message_id in target_messages]

	def _prune_relay_index(self) -> None:
		expire_before = time.time()
		relay_delete_after_seconds = max(0, _safe_int(self.config.relay_delete_after_seconds or 0))
		while self._relay_records:
			if len(self._relay_records) > self._relay_index_max_size:
				oldest_id = next(iter(self._relay_records.keys()))
				self._forget_relay_record(oldest_id)
				continue
			if relay_delete_after_seconds <= 0:
				break
			oldest_id, oldest_record = next(iter(self._relay_records.items()))
			delete_at_ts = float(oldest_record.get("delete_at_ts", 0) or 0.0)
			if delete_at_ts <= 0 or delete_at_ts > expire_before:
				break
			self._forget_relay_record(oldest_id)

	def _build_recent_feed_item(self, event_type: str, event: dict[str, Any], content: str) -> dict[str, Any]:
		broadcaster_login = self._sanitize_text(event.get("broadcaster_user_login", "") or self.state_snapshot().get("broadcaster_login", ""))
		chatter_name = self._sanitize_text(event.get("chatter_user_name", "") or event.get("chatter_user_login", ""))
		chatter_login = self._sanitize_text(event.get("chatter_user_login", ""))
		source_url = "https://www.twitch.tv/{}".format(broadcaster_login) if broadcaster_login else "https://www.twitch.tv"

		text = ""
		if event_type == "channel.chat.notification":
			text = self._sanitize_text(event.get("system_message", ""))
			if not text:
				notice_type = self._sanitize_text(event.get("notice_type", "notification"))
				text = "{} notification".format(notice_type)
		else:
			message = event.get("message", {}) if isinstance(event.get("message"), dict) else {}
			text = self._sanitize_text(message.get("text", ""))
			if not text:
				parts = []
				for fragment in message.get("fragments", []) if isinstance(message.get("fragments"), list) else []:
					if not isinstance(fragment, dict):
						continue
					piece = self._sanitize_text(fragment.get("text", ""))
					if piece:
						parts.append(piece)
				text = self._sanitize_text(" ".join(parts))

		return {
			"id": self._sanitize_text(event.get("message_id", "")),
			"type": "twitch_chat",
			"event_type": self._sanitize_text(event_type),
			"author": chatter_name or chatter_login or "unknown",
			"user_name": chatter_name,
			"user_login": chatter_login,
			"broadcaster_login": broadcaster_login,
			"text": self._truncate_text(text or content, 500),
			"content": self._truncate_text(content, 500),
			"published": self._now_iso_utc(),
			"url": source_url,
		}

	async def _sleep_with_stop(self, seconds: int) -> None:
		remaining = max(1, int(seconds or 1))
		while remaining > 0 and not self._stop_event.is_set():
			await asyncio.sleep(1)
			remaining -= 1

	def _current_authorization(self, force_reload: bool) -> dict[str, Any]:
		with self._auth_lock:
			if self._auth_cache and not force_reload:
				return dict(self._auth_cache)

			payload = {
				"access_token": self._sanitize_text(self.config.user_access_token),
				"refresh_token": self._sanitize_text(self.config.refresh_token),
				"source": "env" if self.config.user_access_token else "file",
			}
			if not payload["access_token"]:
				loaded = self._load_authorization()
				if isinstance(loaded, dict):
					payload.update({
						"access_token": self._sanitize_text(loaded.get("access_token", "")),
						"refresh_token": self._sanitize_text(loaded.get("refresh_token", "")),
						"user_id": self._sanitize_text(loaded.get("user_id", "")),
						"login": self._sanitize_text(loaded.get("login", "")),
						"source": self._sanitize_text(loaded.get("source", "file")) or "file",
					})
					scopes = loaded.get("scopes", []) if isinstance(loaded.get("scopes"), list) else []
					payload["scopes"] = [self._sanitize_text(item) for item in scopes if self._sanitize_text(item)]
			self._auth_cache = dict(payload)
			return dict(self._auth_cache)

	def _set_authorization(self, payload: dict[str, Any], persist: bool) -> None:
		normalized = {
			"access_token": self._sanitize_text(payload.get("access_token", "")),
			"refresh_token": self._sanitize_text(payload.get("refresh_token", "")),
			"user_id": self._sanitize_text(payload.get("user_id", "")),
			"login": self._sanitize_text(payload.get("login", "")),
			"source": self._sanitize_text(payload.get("source", "file")) or "file",
			"updated_at": self._sanitize_text(payload.get("updated_at", "")) or self._now_iso_utc(),
		}
		scopes = payload.get("scopes", []) if isinstance(payload.get("scopes"), list) else []
		normalized["scopes"] = [self._sanitize_text(item) for item in scopes if self._sanitize_text(item)]

		with self._auth_lock:
			self._auth_cache = dict(normalized)

		if persist:
			self._save_authorization(normalized)

	def _update_state(self, **kwargs: Any) -> None:
		with self.state_lock:
			self.state.update(kwargs)