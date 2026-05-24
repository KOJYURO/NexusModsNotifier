from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.parse import quote


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


@dataclass(frozen=True)
class TwitterWatcherConfig:
    channel_id: str
    state_file: str
    prime_on_start: bool
    request_timeout: int
    watch_endpoint: str = ""
    watch_token: str = ""
    watch_limit: int = 20
    save_button_custom_id: str = ""
    default_poll_seconds: int = 86400


class TwitterWatcher:
    """WordPress の twitter-updates API を使って Twitter/X 通知を扱う watcher。"""

    def __init__(
        self,
        config: TwitterWatcherConfig,
        state_lock: Any,
        state: dict[str, Any],
        fetch_json_request: Callable[..., dict[str, Any]],
        discord_post_json: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_state: Callable[[], None],
        sanitize_text: Callable[[Any], str],
        now_iso_utc: Callable[[], str],
        build_watch_headers: Callable[[str, str], dict[str, str]],
        post_message: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config = config
        self.state_lock = state_lock
        self.state = state
        self._fetch_json_request = fetch_json_request
        self._discord_post_json = discord_post_json
        self._save_state = save_state
        self._sanitize_text = sanitize_text
        self._now_iso_utc = now_iso_utc
        self._build_watch_headers = build_watch_headers
        self._post_message = post_message
        self._min_poll_seconds = max(60, _safe_int(self.config.default_poll_seconds or 86400))

        with self.state_lock:
            self.state["poll_interval_seconds"] = max(
                self._min_poll_seconds,
                _safe_int(self.state.get("poll_interval_seconds", self.config.default_poll_seconds) or self.config.default_poll_seconds),
            )
            self.state["poll_interval_source"] = self._sanitize_text(self.state.get("poll_interval_source", "")) or "env"

    def state_snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def poll_once(
        self,
        limit: int | None = None,
        force_send_seen: bool = False,
        min_timestamp: float | None = None,
    ) -> dict[str, Any]:
        if not self.config.channel_id and self._post_message is None:
            return {"ok": False, "error": "TWITTER_NOTIFY_CHANNEL_ID is not set", "sent": 0}

        items = self._fetch_wordpress_items(limit=limit)
        poll_seconds, poll_source = self._current_poll_settings()
        current_ids = [self._item_id(item) for item in items if self._item_id(item)]

        with self.state_lock:
            seen = set([str(value) for value in self.state.get("seen_ids", [])])
            primed = bool(self.state.get("primed", False))

        if self.config.prime_on_start and not primed and not seen and not force_send_seen and min_timestamp is None:
            with self.state_lock:
                self.state["seen_ids"] = list(set(current_ids))[-2000:]
                self.state["primed"] = True
                self.state["last_run"] = self._now_iso_utc()
                self.state["last_error"] = ""
                self.state["last_total"] = len(items)
            self._save_state()
            return {
                "ok": True,
                "sent": 0,
                "primed": True,
                "source": "wordpress",
                "total": len(items),
                "poll_interval_seconds": poll_seconds,
                "poll_interval_source": poll_source,
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
            self.state["last_total"] = len(items)
        self._save_state()

        return {
            "ok": True,
            "sent": sent,
            "source": "wordpress",
            "total": len(items),
            "filtered_total": len(pending),
            "force_send_seen": bool(force_send_seen),
            "poll_interval_seconds": poll_seconds,
            "poll_interval_source": poll_source,
            "updated_at": self._now_iso_utc(),
        }

    def _fetch_wordpress_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        endpoint = str(self.config.watch_endpoint or "").strip()
        if not endpoint:
            raise RuntimeError("WP_TWITTER_WATCH_ENDPOINT is not set")

        capped_limit = max(1, min(int(limit if limit is not None else self.config.watch_limit or 20), 100))
        url = "{}{}limit={}".format(
            endpoint,
            "&" if "?" in endpoint else "?",
            capped_limit,
        )
        headers = self._build_watch_headers(self.config.watch_token, endpoint)

        data = self._fetch_json_request(url, headers=headers, timeout=self.config.request_timeout)
        self._apply_remote_poll_settings(data)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            raise RuntimeError("WP twitter watch response is invalid")
        return [self._normalize_item(item) for item in items if isinstance(item, dict)]

    def _apply_remote_poll_settings(self, data: Any) -> None:
        poll_seconds = self._min_poll_seconds
        poll_source = "env"

        if isinstance(data, dict):
            raw_seconds = data.get("poll_interval_seconds")
            raw_minutes = data.get("poll_interval_minutes")
            if raw_seconds not in (None, ""):
                poll_seconds = max(self._min_poll_seconds, _safe_int(raw_seconds))
                poll_source = "wordpress"
            elif raw_minutes not in (None, ""):
                poll_seconds = max(self._min_poll_seconds, _safe_int(raw_minutes) * 60)
                poll_source = "wordpress"

        with self.state_lock:
            self.state["poll_interval_seconds"] = poll_seconds
            self.state["poll_interval_source"] = poll_source

    def _current_poll_settings(self) -> tuple[int, str]:
        with self.state_lock:
            poll_seconds = max(self._min_poll_seconds, _safe_int(self.state.get("poll_interval_seconds", self.config.default_poll_seconds) or self.config.default_poll_seconds))
            poll_source = self._sanitize_text(self.state.get("poll_interval_source", "")) or "env"
        return poll_seconds, poll_source

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        author_name = self._sanitize_text(item.get("author_name", ""))
        author_username = self._sanitize_text(item.get("author_username", "")).lstrip("@")
        profile_url = self._sanitize_text(item.get("profile_url", ""))
        if not profile_url and author_username:
            profile_url = "https://x.com/{}".format(quote(author_username))

        tweet_url = self._sanitize_text(item.get("url", ""))
        tweet_id = self._sanitize_text(item.get("id", ""))
        if not tweet_url and author_username and tweet_id:
            tweet_url = "https://x.com/{}/status/{}".format(quote(author_username), quote(tweet_id))

        return {
            "id": tweet_id,
            "type": self._sanitize_text(item.get("type", "")) or "twitter_tweet",
            "text": self._sanitize_text(item.get("text", "")),
            "author_name": author_name or ("@{}".format(author_username) if author_username else "Unknown"),
            "author_username": author_username,
            "profile_image_url": self._sanitize_text(item.get("profile_image_url", "")),
            "profile_url": profile_url,
            "url": tweet_url,
            "created_at": self._sanitize_text(item.get("created_at", "")),
            "language": self._sanitize_text(item.get("language", "")),
            "retweet_count": _safe_int(item.get("retweet_count", 0)),
            "like_count": _safe_int(item.get("like_count", 0)),
            "image_url": self._sanitize_text(item.get("image_url", "")),
            "image_alt": self._sanitize_text(item.get("image_alt", "")),
            "media_type": self._sanitize_text(item.get("media_type", "")),
            "thumbnail_url": self._sanitize_text(item.get("thumbnail_url", "")),
            "link_url": self._sanitize_text(item.get("link_url", "")),
            "link_title": self._sanitize_text(item.get("link_title", "")),
            "link_description": self._sanitize_text(item.get("link_description", "")),
            "is_linked_member": bool(item.get("is_linked_member", False)),
            "member_level": self._sanitize_text(item.get("member_level", "")),
            "member_rank": _safe_int(item.get("member_rank", 0)),
            "member_display_name": self._sanitize_text(item.get("member_display_name", "")),
            "member_profile_url": self._sanitize_text(item.get("member_profile_url", "")),
            "member_profile_label": self._sanitize_text(item.get("member_profile_label", "")),
        }

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
        lines = ["【Twitter/X 新着投稿】"]
        member_name = self._sanitize_text(item.get("member_display_name", ""))
        if item.get("is_linked_member") and member_name:
            lines.append("連携メンバー: {}".format(member_name))
        if item.get("url"):
            lines.append(str(item.get("url")))
        return self._truncate_text("\n".join(lines), 1900)

    def _build_embed(self, item: dict[str, Any]) -> dict[str, Any]:
        creator_name = item.get("member_display_name") or item.get("author_name") or ("@{}".format(item.get("author_username")) if item.get("author_username") else "Unknown")
        account_name = "@{}".format(item.get("author_username")) if item.get("author_username") else "-"
        description_parts = []

        if item.get("text"):
            description_parts.append(str(item.get("text")))
        if item.get("link_title"):
            description_parts.append("リンク先: {}".format(item.get("link_title")))
        if item.get("link_description"):
            description_parts.append(str(item.get("link_description")))
        if item.get("is_linked_member") and item.get("member_display_name"):
            description_parts.append("連携メンバー: {}".format(item.get("member_display_name")))

        embed: dict[str, Any] = {
            "title": self._truncate_text("{} さんの新着投稿".format(item.get("author_name") or creator_name), 256),
            "url": item.get("url") or None,
            "description": self._truncate_text("\n\n".join([part for part in description_parts if part]), 3800),
            "color": 0x1D9BF0,
            "author": {
                "name": "Twitter/X Watch",
                "icon_url": item.get("profile_image_url") or "https://abs.twimg.com/favicons/twitter.3.ico",
            },
            "fields": [
                {
                    "name": "Creator",
                    "value": self._field_value(creator_name),
                    "inline": True,
                },
                {
                    "name": "Account",
                    "value": self._field_value(account_name),
                    "inline": True,
                },
                {
                    "name": "Language",
                    "value": self._field_value((item.get("language") or "-").upper()),
                    "inline": True,
                },
                {
                    "name": "Likes",
                    "value": str(item.get("like_count", 0) or 0),
                    "inline": True,
                },
                {
                    "name": "Reposts",
                    "value": str(item.get("retweet_count", 0) or 0),
                    "inline": True,
                },
                {
                    "name": "Published",
                    "value": self._field_value(item.get("created_at") or "-"),
                    "inline": True,
                },
            ],
        }

        if not embed["description"]:
            del embed["description"]

        if item.get("image_url"):
            embed["image"] = {"url": item.get("image_url")}
        if item.get("thumbnail_url"):
            embed["thumbnail"] = {"url": item.get("thumbnail_url")}

        return embed

    def _build_components(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        buttons = []
        if item.get("url"):
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": "投稿を見る / Open Post",
                    "url": item.get("url"),
                }
            )
        if item.get("link_url"):
            label = self._truncate_text(item.get("link_title") or "リンク先 / Link", 80)
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": label,
                    "url": item.get("link_url"),
                }
            )
        profile_url = item.get("member_profile_url") or item.get("profile_url")
        profile_label = item.get("member_profile_label") or ("@{}".format(item.get("author_username")) if item.get("author_username") else "アカウント / Profile")
        if profile_url:
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": self._truncate_text(profile_label, 80),
                    "url": profile_url,
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
        raw = self._sanitize_text(item.get("created_at", ""))
        if not raw:
            return 0
        candidates = [raw, raw[:19]]
        for candidate in candidates:
            for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return int(datetime.strptime(candidate, pattern).timestamp())
                except Exception:
                    continue
        return 0