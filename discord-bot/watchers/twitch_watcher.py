from __future__ import annotations

import time
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


@dataclass(frozen=True)
class TwitchWatcherConfig:
    channel_id: str
    client_id: str
    client_secret: str
    user_logins_csv: str
    state_file: str
    prime_on_start: bool
    request_timeout: int
    watch_endpoint: str = ""
    watch_token: str = ""
    watch_limit: int = 20
    save_button_custom_id: str = ""


class TwitchWatcher:
    """Social Finder 風の構成で Twitch 通知を扱う watcher。"""

    def __init__(
        self,
        config: TwitchWatcherConfig,
        state_lock: Any,
        state: dict[str, Any],
        fetch_json_request: Callable[..., dict[str, Any]],
        discord_post_json: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_state: Callable[[], None],
        parse_csv_list: Callable[[str], list[str]],
        sanitize_text: Callable[[Any], str],
        now_iso_utc: Callable[[], str],
        build_watch_headers: Callable[[str, str], dict[str, str]] | None = None,
        post_message: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config = config
        self.state_lock = state_lock
        self.state = state
        self._fetch_json_request = fetch_json_request
        self._discord_post_json = discord_post_json
        self._save_state = save_state
        self._parse_csv_list = parse_csv_list
        self._sanitize_text = sanitize_text
        self._now_iso_utc = now_iso_utc
        self._build_watch_headers = build_watch_headers
        self._post_message = post_message
        self._token_cache = {
            "access_token": "",
            "expires_at": 0,
        }

    def state_snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def fetch_app_token(self) -> str:
        now = int(time.time())
        if self._token_cache.get("access_token") and now < int(self._token_cache.get("expires_at", 0)) - 60:
            return str(self._token_cache.get("access_token") or "")

        if not self.config.client_id or not self.config.client_secret:
            raise RuntimeError("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set")

        url = (
            "https://id.twitch.tv/oauth2/token"
            "?client_id={}&client_secret={}&grant_type=client_credentials"
        ).format(quote(self.config.client_id), quote(self.config.client_secret))

        data = self._fetch_json_request(
            url,
            headers={"User-Agent": "DiscordBotBridge/1.0"},
            timeout=self.config.request_timeout,
            method="POST",
        )
        access_token = str(data.get("access_token", "") or "").strip()
        expires_in = _safe_int(data.get("expires_in", 0))
        if not access_token:
            raise RuntimeError("twitch app token response has no access_token")

        self._token_cache["access_token"] = access_token
        self._token_cache["expires_at"] = now + max(60, expires_in)
        return access_token

    def fetch_live_streams(self, user_logins: list[str] | None = None) -> list[dict[str, Any]]:
        if user_logins is None:
            user_logins = self._parse_csv_list(self.config.user_logins_csv)
        if not user_logins:
            return []

        token = self.fetch_app_token()
        headers = {
            "Client-ID": self.config.client_id,
            "Authorization": "Bearer {}".format(token),
            "User-Agent": "DiscordBotBridge/1.0",
        }

        result: list[dict[str, Any]] = []
        chunk: list[str] = []
        for login in user_logins:
            chunk.append(login)
            if len(chunk) == 100:
                result.extend(self.fetch_streams_chunk(headers, chunk))
                chunk = []
        if chunk:
            result.extend(self.fetch_streams_chunk(headers, chunk))
        return result

    def fetch_streams_chunk(self, headers: dict[str, str], user_logins: list[str]) -> list[dict[str, Any]]:
        query = "&".join(["user_login={}".format(quote(login)) for login in user_logins if login])
        url = "https://api.twitch.tv/helix/streams?{}".format(query)
        data = self._fetch_json_request(url, headers=headers, timeout=self.config.request_timeout)
        rows = data.get("data", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def format_plaintext_notification(self, stream: dict[str, Any]) -> str:
        item = self._normalize_item(stream)
        status_label = "配信開始" if item.get("broadcast_state") == "live" else "アーカイブ公開"
        metric_label = "視聴者数" if item.get("broadcast_state") == "live" else "再生数"
        metric_value = item.get("viewer_count", 0) or item.get("view_count", 0)
        timestamp = item.get("started_at", "") or item.get("published_at", "") or item.get("created_at", "")

        lines = [
            "【Twitch {}】".format(status_label),
            "{}".format(item.get("user_name") or "Unknown"),
            item.get("title") or "Twitch 更新",
        ]
        if item.get("game_name"):
            lines.append("ゲーム: {}".format(item.get("game_name")))
        lines.append("{}: {}".format(metric_label, metric_value))
        if timestamp:
            lines.append("時刻: {}".format(timestamp))
        if item.get("is_linked_member") and item.get("member_display_name"):
            lines.append("連携メンバー: {}".format(item.get("member_display_name")))
        if item.get("url"):
            lines.append(item.get("url"))
        return self._truncate_text("\n".join(lines), 1900)

    def poll_once(
        self,
        limit: int | None = None,
        force_send_seen: bool = False,
        min_timestamp: float | None = None,
    ) -> dict[str, Any]:
        if not self.config.channel_id and self._post_message is None:
            return {"ok": False, "error": "TWITCH_NOTIFY_CHANNEL_ID is not set", "sent": 0}

        items, source = self._fetch_latest_items(limit=limit)
        current_ids = [self._item_id(item) for item in items if self._item_id(item)]

        with self.state_lock:
            seen = set([str(value) for value in self.state.get("seen_ids", [])])
            primed = bool(self.state.get("primed", False))
            previous_source = str(self.state.get("last_source", "") or "")

        source_migrated = source == "wordpress" and not seen and previous_source != "wordpress"

        if ((self.config.prime_on_start and not primed and not seen and not force_send_seen and min_timestamp is None) or source_migrated):
            with self.state_lock:
                self.state["seen_ids"] = list(set(current_ids))[-2000:]
                self.state["primed"] = True
                self.state["last_run"] = self._now_iso_utc()
                self.state["last_error"] = ""
                self.state["last_source"] = source
                self.state["last_total"] = len(items)
            self._save_state()
            return {
                "ok": True,
                "sent": 0,
                "primed": True,
                "migrated": source_migrated,
                "source": source,
                "total": len(items),
                "updated_at": self._now_iso_utc(),
            }

        pending = []
        for item in items:
            item_id = self._item_id(item)
            if not item_id:
                continue
            if min_timestamp is not None:
                item_ts = self._sort_timestamp(item)
                if item_ts <= 0 or item_ts < min_timestamp:
                    continue
            if (not force_send_seen) and item_id in seen:
                continue
            pending.append(item)

        pending.sort(key=self._sort_timestamp)

        sent = 0
        for item in pending:
            payload = self._build_message_payload(item)
            if self._post_message is not None:
                self._post_message(item, payload)
            else:
                self._discord_post_json(
                    "/channels/{}/messages".format(self.config.channel_id),
                    payload,
                )
            seen.add(self._item_id(item))
            sent += 1

        with self.state_lock:
            self.state["seen_ids"] = list(seen)[-2000:]
            self.state["primed"] = True
            self.state["last_run"] = self._now_iso_utc()
            self.state["last_error"] = ""
            self.state["last_source"] = source
            self.state["last_total"] = len(items)
        self._save_state()

        return {
            "ok": True,
            "sent": sent,
            "source": source,
            "total": len(items),
            "filtered_total": len(pending),
            "force_send_seen": bool(force_send_seen),
            "updated_at": self._now_iso_utc(),
        }

    def fetch_latest_items(self, limit: int | None = None) -> tuple[list[dict[str, Any]], str]:
        items, source = self._fetch_latest_items(limit=limit)
        return ([dict(item) for item in items if isinstance(item, dict)], source)

    def build_vrc_playlist_payload(self, limit: int | None = None) -> dict[str, Any]:
        items, source = self.fetch_latest_items(limit=limit)
        playlist_items = [self._build_vrc_playlist_item(item) for item in items if isinstance(item, dict)]
        playlist_items = [item for item in playlist_items if item.get("url")]
        playlist_items.sort(
            key=lambda item: (
                1 if item.get("is_live") else 0,
                _safe_int(item.get("sort_ts", 0)),
            ),
            reverse=True,
        )
        return {
            "ok": True,
            "schema": "7djp_twitch_playlist_v1",
            "generated_at": self._now_iso_utc(),
            "source": source,
            "count": len(playlist_items),
            "items": playlist_items,
        }

    def _build_vrc_playlist_item(self, item: dict[str, Any]) -> dict[str, Any]:
        title = self._sanitize_text(item.get("title", "Twitch 更新")) or "Twitch 更新"
        user_name = self._sanitize_text(item.get("user_name", "")) or "Unknown"
        game_name = self._sanitize_text(item.get("game_name", ""))
        user_login = self._sanitize_text(item.get("user_login", ""))
        url = self._sanitize_text(item.get("url", ""))
        timestamp = (
            self._sanitize_text(item.get("started_at", ""))
            or self._sanitize_text(item.get("published_at", ""))
            or self._sanitize_text(item.get("created_at", ""))
        )
        is_live = self._sanitize_text(item.get("broadcast_state", "")).lower() == "live"

        subtitle_parts = [user_name]
        if game_name:
            subtitle_parts.append(game_name)
        if is_live:
            subtitle_parts.append("LIVE")

        return {
            "id": self._sanitize_text(item.get("id", "")),
            "type": self._sanitize_text(item.get("type", "")) or "twitch_stream",
            "title": title,
            "subtitle": " / ".join(subtitle_parts),
            "description": " - ".join([part for part in (user_name, game_name) if part]),
            "url": url,
            "video_url": url,
            "thumbnail_url": self._normalize_thumbnail_url(item.get("thumbnail_url", "")),
            "image_url": self._normalize_thumbnail_url(item.get("thumbnail_url", "")),
            "user_name": user_name,
            "user_login": user_login,
            "game_name": game_name,
            "broadcast_state": self._sanitize_text(item.get("broadcast_state", "")) or "live",
            "is_live": is_live,
            "viewer_count": _safe_int(item.get("viewer_count", 0)),
            "view_count": _safe_int(item.get("view_count", 0)),
            "timestamp": timestamp,
            "member_display_name": self._sanitize_text(item.get("member_display_name", "")),
            "member_profile_url": self._sanitize_text(item.get("member_profile_url", "")),
            "sort_ts": int(self._sort_timestamp(item)),
        }

    def _fetch_latest_items(self, limit: int | None = None) -> tuple[list[dict[str, Any]], str]:
        last_error: Exception | None = None
        if self.config.watch_endpoint:
            try:
                return self._fetch_wordpress_items(limit=limit), "wordpress"
            except Exception as exc:
                last_error = exc

        try:
            direct_items = self._fetch_direct_items()
            return direct_items, "helix" if last_error is None else "helix-fallback"
        except Exception:
            if last_error is not None:
                raise last_error
            raise

    def _fetch_direct_items(self) -> list[dict[str, Any]]:
        user_logins = self._parse_csv_list(self.config.user_logins_csv)
        if not user_logins:
            raise RuntimeError("TWITCH_NOTIFY_USER_LOGINS is empty")

        return [self._normalize_item(stream) for stream in self.fetch_live_streams(user_logins)]

    def _fetch_wordpress_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        endpoint = str(self.config.watch_endpoint or "").strip()
        if not endpoint:
            raise RuntimeError("WP_TWITCH_WATCH_ENDPOINT is not set")

        capped_limit = max(1, min(int(limit if limit is not None else self.config.watch_limit or 20), 100))
        url = "{}{}limit={}".format(
            endpoint,
            "&" if "?" in endpoint else "?",
            capped_limit,
        )
        if self._build_watch_headers is not None:
            headers = self._build_watch_headers(self.config.watch_token, endpoint)
        else:
            headers = {
                "User-Agent": "DiscordBotBridge/1.0",
            }
            if self.config.watch_token:
                headers["Authorization"] = "Bearer {}".format(self.config.watch_token)
                headers["X-Sevendtd-Bearer"] = self.config.watch_token

        data = self._fetch_json_request(url, headers=headers, timeout=self.config.request_timeout)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            raise RuntimeError("WP twitch watch response is invalid")
        return [self._normalize_item(item) for item in items if isinstance(item, dict)]

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        user_name = self._sanitize_text(item.get("user_name", "") or item.get("member_display_name", ""))
        user_login = self._sanitize_text(item.get("user_login", ""))
        title = self._sanitize_text(item.get("title", "Twitch 更新"))
        game_name = self._sanitize_text(item.get("game_name", ""))
        language = self._sanitize_text(item.get("language", ""))
        thumbnail_url = self._normalize_thumbnail_url(item.get("thumbnail_url", ""))

        url = self._sanitize_text(item.get("url", ""))
        if not url and user_login:
            url = "https://www.twitch.tv/{}".format(user_login)

        broadcast_state = self._sanitize_text(item.get("broadcast_state", "")) or "live"
        normalized = {
            "id": self._sanitize_text(item.get("id", "")),
            "type": self._sanitize_text(item.get("type", "")) or "twitch_stream",
            "title": title,
            "user_name": user_name or "Unknown",
            "user_login": user_login,
            "game_name": game_name,
            "language": language,
            "viewer_count": _safe_int(item.get("viewer_count", 0)),
            "view_count": _safe_int(item.get("view_count", 0)),
            "thumbnail_url": thumbnail_url,
            "url": url,
            "started_at": self._sanitize_text(item.get("started_at", "")),
            "published_at": self._sanitize_text(item.get("published_at", "")),
            "created_at": self._sanitize_text(item.get("created_at", "")),
            "duration": self._sanitize_text(item.get("duration", "")),
            "broadcast_state": broadcast_state,
            "is_linked_member": bool(item.get("is_linked_member", False)),
            "member_level": self._sanitize_text(item.get("member_level", "")),
            "member_rank": _safe_int(item.get("member_rank", 0)),
            "member_display_name": self._sanitize_text(item.get("member_display_name", "")),
            "member_profile_url": self._sanitize_text(item.get("member_profile_url", "")),
            "member_profile_label": self._sanitize_text(item.get("member_profile_label", "")),
        }
        return normalized

    def _normalize_thumbnail_url(self, value: Any) -> str:
        thumbnail_url = self._sanitize_text(value)
        if not thumbnail_url:
            return ""

        thumbnail_url = thumbnail_url.replace("{width}", "640").replace("{height}", "360")
        thumbnail_url = thumbnail_url.replace("%{width}", "640").replace("%{height}", "360")
        thumbnail_url = re.sub(r"%width", "640", thumbnail_url, flags=re.IGNORECASE)
        thumbnail_url = re.sub(r"%height", "360", thumbnail_url, flags=re.IGNORECASE)

        # Twitch 側が processing placeholder しか返さない場合は、壊れたサムネを embed に出さない。
        if "404_processing" in thumbnail_url or "/_404/" in thumbnail_url:
            return ""

        return thumbnail_url

    def _build_message_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": self._build_content(item),
            "embeds": [self._build_embed(item)],
        }
        components = self._build_components(item)
        if components:
            payload["components"] = components
        return payload

    def _build_content(self, item: dict[str, Any]) -> str:
        status_label = "LIVE" if item.get("broadcast_state") == "live" else "ARCHIVE"
        lines = ["【Twitch {}】".format(status_label)]
        member_name = self._sanitize_text(item.get("member_display_name", ""))
        if item.get("is_linked_member") and member_name:
            lines.append("連携メンバー: {}".format(member_name))
        if item.get("url"):
            lines.append(str(item.get("url")))
        return self._truncate_text("\n".join(lines), 1900)

    def _build_embed(self, item: dict[str, Any]) -> dict[str, Any]:
        is_live = item.get("broadcast_state") == "live"
        metric_label = "Viewers" if is_live else "Views"
        metric_value = item.get("viewer_count", 0) or item.get("view_count", 0)
        timestamp_label = "Started" if is_live else "Published"
        timestamp_value = item.get("started_at") or item.get("published_at") or item.get("created_at") or "-"
        description_lines = []

        if item.get("is_linked_member"):
            member_level = self._sanitize_text(item.get("member_level", "")).lower()
            member_name = self._sanitize_text(item.get("member_display_name", ""))
            member_text = member_name or "アカウント連携済み"
            if member_level:
                member_text = "{} member / {}".format(member_level, member_text)
            description_lines.append(member_text)

        if item.get("duration"):
            description_lines.append("Duration: {}".format(item.get("duration")))

        embed: dict[str, Any] = {
            "title": self._truncate_text(item.get("title") or "Twitch 更新", 256),
            "url": item.get("url") or None,
            "description": self._truncate_text("\n".join(description_lines), 1024),
            "color": 0x9146FF if is_live else 0x6441A5,
            "author": {
                "name": "Twitch Watch",
                "icon_url": "https://static.twitchcdn.net/assets/favicon-32-e29e246c157142c94346.png",
            },
            "fields": [
                {
                    "name": "Streamer",
                    "value": self._field_value(item.get("user_name") or "Unknown"),
                    "inline": True,
                },
                {
                    "name": "Creator",
                    "value": self._field_value(item.get("member_display_name") or item.get("user_name") or "Unknown"),
                    "inline": True,
                },
                {
                    "name": "Status",
                    "value": "LIVE" if is_live else "ARCHIVE",
                    "inline": True,
                },
                {
                    "name": metric_label,
                    "value": str(metric_value),
                    "inline": True,
                },
                {
                    "name": "Game",
                    "value": self._field_value(item.get("game_name") or "7 Days to Die"),
                    "inline": True,
                },
                {
                    "name": "Language",
                    "value": self._field_value((item.get("language") or "-").upper()),
                    "inline": True,
                },
                {
                    "name": timestamp_label,
                    "value": self._field_value(timestamp_value),
                    "inline": True,
                },
            ],
        }

        if not embed["description"]:
            del embed["description"]

        if item.get("thumbnail_url"):
            embed["image"] = {"url": item.get("thumbnail_url")}

        return embed

    def _build_components(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        buttons = []
        if item.get("url"):
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": "視聴する / Watch",
                    "url": item.get("url"),
                }
            )
        if item.get("member_profile_url"):
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": self._truncate_text(item.get("member_profile_label") or "メンバー / Member", 80),
                    "url": item.get("member_profile_url"),
                }
            )
        if self.config.save_button_custom_id:
            buttons.append(
                {
                    "type": 2,
                    "style": 2,
                    "label": "お気に入り / Favorite",
                    "custom_id": self.config.save_button_custom_id,
                }
            )
        if not buttons:
            return []
        return [{"type": 1, "components": buttons[:5]}]

    def _field_value(self, value: Any) -> str:
        text = self._sanitize_text(value)
        return self._truncate_text(text or "-", 1024)

    def _truncate_text(self, value: Any, limit: int) -> str:
        raw = str(value or "")
        if limit <= 0:
            return ""
        if len(raw) <= limit:
            return raw
        if limit <= 3:
            return raw[:limit]
        return raw[: limit - 3] + "..."

    def _item_id(self, item: dict[str, Any]) -> str:
        return self._sanitize_text(item.get("id", ""))

    def _sort_timestamp(self, item: dict[str, Any]) -> int:
        for field in ("started_at", "published_at", "created_at"):
            raw = self._sanitize_text(item.get(field, ""))
            if not raw:
                continue
            candidates = [raw, raw[:19]]
            for candidate in candidates:
                for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return int(datetime.strptime(candidate, pattern).timestamp())
                    except Exception:
                        continue
        return 0