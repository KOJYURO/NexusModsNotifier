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


NEXUS_TEMPORARY_TAG_RULES = (
    ("大型改変", ("total conversion", "conversion", "overhaul")),
    ("快適化", ("quality of life", "qol", "optimization", "optimisation", "fps", "lag")),
    ("UI", ("inventory", "interface", "backpack", "loadout", "ui")),
    ("HUD", ("hud", "crosshair")),
    ("クラフト", ("crafting", "craft", "recipe", "recipes", "food", "foods", "drink", "drinks", "smoothie", "cook", "cooking", "vehicle", "vehicles", "truck", "car", "bike", "uaz")),
    ("武器", ("weapons", "weapon", "melee", "brawler", "guns", "gun", "rifle", "pistol", "shotgun", "bow", "spear", "ammo")),
    ("サーバー向け", ("server tools", "server-side", "serverside", "dedicated", "admin tool", "server")),
    ("クライアント向け", ("client-side", "clientside", "client")),
    ("軽量化", ("performance",)),
    ("グラフィック", ("graphics", "visual", "weather", "lighting", "shader", "texture")),
    ("ゾンビ", ("zombies", "zombie", "undead", "horde")),
    ("クエスト", ("quests", "quest", "trader", "mission", "objective")),
    ("建築", ("buildings", "building", "prefabs", "prefab", "poi", "map", "world")),
    ("互換性", ("compatibility", "compatible")),
    ("バランス調整", ("balance", "balanced", "progression", "perk", "perks", "skill", "skills", "loot", "economy")),
)


def _infer_temporary_nexus_tags(*values: Any, limit: int = 4) -> list[str]:
    haystack = " ".join([str(value or "").strip().lower() for value in values if str(value or "").strip()])
    if not haystack:
        return []

    tags: list[str] = []
    max_tags = max(1, int(limit or 4))
    for tag_name, keywords in NEXUS_TEMPORARY_TAG_RULES:
        if any(keyword in haystack for keyword in keywords):
            tags.append(tag_name)
        if len(tags) >= max_tags:
            break
    return tags


@dataclass(frozen=True)
class NexusWatcherConfig:
    channel_id: str
    state_file: str
    prime_on_start: bool
    request_timeout: int
    watch_endpoint: str = ""
    watch_token: str = ""
    watch_limit: int = 20
    fallback_enabled: bool = True
    fallback_posts_endpoint: str = ""
    fallback_category_ids: str = ""
    fallback_max_age_hours: int = 168


class NexusWatcher:
    """Nexus 通知の取得と Discord 投稿を担う watcher。"""

    def __init__(
        self,
        config: NexusWatcherConfig,
        state_lock: Any,
        state: dict[str, Any],
        fetch_json_request: Callable[..., dict[str, Any]],
        fetch_json_value_request: Callable[..., Any],
        discord_post_json: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_state: Callable[[], None],
        sanitize_text: Callable[[Any], str],
        strip_html_tags: Callable[[Any], str],
        now_iso_utc: Callable[[], str],
        build_watch_headers: Callable[[str, str], dict[str, str]],
        post_message: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config = config
        self.state_lock = state_lock
        self.state = state
        self._fetch_json_request = fetch_json_request
        self._fetch_json_value_request = fetch_json_value_request
        self._discord_post_json = discord_post_json
        self._save_state = save_state
        self._sanitize_text = sanitize_text
        self._strip_html_tags = strip_html_tags
        self._now_iso_utc = now_iso_utc
        self._build_watch_headers = build_watch_headers
        self._post_message = post_message

    def state_snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def fetch_wordpress_items(self, limit: int | None = None) -> dict[str, Any]:
        endpoint = str(self.config.watch_endpoint or "").strip()
        if not endpoint:
            raise RuntimeError("WP_NEXUS_WATCH_ENDPOINT is not set")

        token = str(self.config.watch_token or "").strip()
        if not token:
            raise RuntimeError("WP_NEXUS_WATCH_TOKEN is not set")

        capped = self._resolve_limit(limit)
        url = "{}{}limit={}".format(
            endpoint,
            "&" if "?" in endpoint else "?",
            capped,
        )
        headers = self._build_watch_headers(token, endpoint)
        data = self._fetch_json_request(url, headers=headers, timeout=self.config.request_timeout)
        if not isinstance(data, dict):
            raise RuntimeError("WP nexus watch response is invalid")
        return data

    def fetch_fallback_posts(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.config.fallback_enabled:
            return []

        endpoint = str(self.config.fallback_posts_endpoint or "").strip()
        if not endpoint:
            return []

        capped = self._resolve_limit(limit)
        query_parts = [
            "per_page={}".format(max(capped * 3, 20)),
            "_fields=id,date_gmt,date,link,title,categories",
        ]
        if str(self.config.fallback_category_ids or "").strip():
            query_parts.append("categories={}".format(quote(str(self.config.fallback_category_ids).strip())))
        url = "{}{}{}".format(endpoint, "&" if "?" in endpoint else "?", "&".join(query_parts))

        headers = self._build_watch_headers("", endpoint)
        data = self._fetch_json_value_request(url, headers=headers, timeout=self.config.request_timeout)
        if not isinstance(data, list):
            return []

        now_epoch = datetime.utcnow().timestamp()
        max_age_seconds = max(1, int(self.config.fallback_max_age_hours or 168)) * 3600
        items: list[dict[str, Any]] = []

        for row in data:
            if not isinstance(row, dict):
                continue

            post_id = self._sanitize_text(row.get("id", ""))
            title_raw = row.get("title", {})
            if isinstance(title_raw, dict):
                title = self._strip_html_tags(title_raw.get("rendered", ""))
            else:
                title = self._strip_html_tags(title_raw)

            link = self._sanitize_text(row.get("link", ""))
            dt_text = self._sanitize_text(row.get("date_gmt", "") or row.get("date", ""))
            parsed = self._parse_timestamp(dt_text)
            if parsed and (now_epoch - parsed) > max_age_seconds:
                continue

            if not post_id or not title:
                continue

            items.append(
                {
                    "id": "fallback-{}".format(post_id),
                    "title": title,
                    "url": link,
                    "score": 0,
                    "badge": "fallback",
                    "diff": "",
                    "updated_at": dt_text,
                    "updated_ts": int(parsed or 0),
                    "category": "mod-fallback",
                    "tags_ja": [],
                    "author": "",
                    "version": "",
                    "summary": "",
                    "image_url": "",
                    "source": "posts-fallback",
                }
            )

            if len(items) >= capped:
                break

        return items

    def format_plaintext_notification(self, item: dict[str, Any]) -> str:
        title = self._sanitize_text(item.get("title", "Unknown Mod"))
        url = self._sanitize_text(item.get("url", ""))
        score = _safe_int(item.get("score", 0))
        badge = self._sanitize_text(item.get("badge", ""))
        diff = self._sanitize_text(item.get("diff", ""))
        updated_at = self._sanitize_text(item.get("updated_at", ""))
        category = self._sanitize_text(item.get("category", ""))
        author = self._sanitize_text(item.get("author", ""))
        version = self._sanitize_text(item.get("version", ""))
        tags = item.get("tags_ja", []) if isinstance(item.get("tags_ja"), list) else []
        tags_text = " / ".join([self._sanitize_text(value) for value in tags if self._sanitize_text(value)][:4])

        lines = ["【7DTD MOD更新通知】", "{} ({})".format(title, badge or "判定なし")]
        if author:
            lines.append("作者: {}".format(author))
        if version:
            lines.append("Version: {}".format(version))
        lines.append("スコア: {}".format(score))
        if diff:
            lines.append("差分: {}".format(diff))
        if category:
            lines.append("カテゴリ: {}".format(category))
        if updated_at:
            lines.append("更新日: {}".format(updated_at))
        if tags_text:
            lines.append("タグ: {}".format(tags_text))
        if url:
            lines.append(url)
        return self._truncate_text("\n".join(lines), 1900)

    def poll_once(
        self,
        limit: int | None = None,
        force_send_seen: bool = False,
        min_timestamp: float | None = None,
    ) -> dict[str, Any]:
        if not self.config.channel_id and self._post_message is None:
            return {"ok": False, "error": "DISCORD_NEXUS_NOTIFY_CHANNEL_ID is not set", "sent": 0}

        items, source = self._fetch_latest_items(limit)
        current_ids = [self._item_id(item) for item in items if self._item_id(item)]

        with self.state_lock:
            seen = set([str(value) for value in self.state.get("seen_ids", [])])
            primed = bool(self.state.get("primed", False))

        if self.config.prime_on_start and not primed and not seen and not force_send_seen and min_timestamp is None:
            with self.state_lock:
                self.state["seen_ids"] = list(set(current_ids))[-1000:]
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
            self.state["seen_ids"] = list(seen)[-1000:]
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

    def _fetch_latest_items(self, limit: int | None = None) -> tuple[list[dict[str, Any]], str]:
        last_error: Exception | None = None
        if self.config.watch_endpoint:
            try:
                data = self.fetch_wordpress_items(limit)
                items = data.get("items", []) if isinstance(data, dict) else []
                if not isinstance(items, list):
                    raise RuntimeError("WP nexus watch response is invalid")
                source = "wordpress-fallback" if bool(data.get("fallback", False)) else "wordpress"
                return [self._normalize_item(item) for item in items if isinstance(item, dict)], source
            except Exception as exc:
                last_error = exc

        if self.config.fallback_enabled:
            fallback_items = self.fetch_fallback_posts(limit)
            return [self._normalize_item(item) for item in fallback_items if isinstance(item, dict)], "posts-fallback"

        if last_error is not None:
            raise last_error
        raise RuntimeError("Nexus watch source is not available")

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_tags = item.get("tags_ja", []) if isinstance(item.get("tags_ja"), list) else []
        tags = [self._sanitize_text(value) for value in raw_tags if self._sanitize_text(value)]
        category = self._sanitize_text(item.get("category", ""))
        if not tags:
            tags = _infer_temporary_nexus_tags(
                item.get("title", ""),
                item.get("summary", ""),
                item.get("category", ""),
                item.get("author", ""),
            )
        if (not tags) and category and category != "-":
            tags = [category]
        if (not category or category == "-") and tags:
            category = tags[0]

        normalized_tags = []
        for raw_tag in tags:
            tag_name = self._sanitize_text(raw_tag)
            if not tag_name or tag_name in normalized_tags:
                continue
            normalized_tags.append(tag_name)
        return {
            "id": self._sanitize_text(item.get("id", "")),
            "title": self._sanitize_text(item.get("title", "Nexus MOD 更新")) or "Nexus MOD 更新",
            "url": self._sanitize_text(item.get("url", "")),
            "score": _safe_int(item.get("score", 0)),
            "badge": self._sanitize_text(item.get("badge", "")),
            "diff": self._sanitize_text(item.get("diff", "")),
            "updated_at": self._sanitize_text(item.get("updated_at", "")),
            "updated_ts": _safe_int(item.get("updated_ts", 0)),
            "downloads": _safe_int(item.get("downloads", 0)),
            "endorsements": _safe_int(item.get("endorsements", 0)),
            "category": category,
            "tags_ja": normalized_tags,
            "author": self._sanitize_text(item.get("author", "")),
            "version": self._sanitize_text(item.get("version", "")),
            "summary": self._sanitize_multiline_text(item.get("summary", "")),
            "image_url": self._sanitize_text(item.get("image_url", "")),
            "source": self._sanitize_text(item.get("source", "wordpress")) or "wordpress",
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
        lines = ["【7DTD MOD更新通知】"]
        if item.get("url"):
            lines.append(str(item.get("url")))
        return self._truncate_text("\n".join(lines), 1900)

    def _build_embed(self, item: dict[str, Any]) -> dict[str, Any]:
        description_lines = []
        if item.get("badge"):
            description_lines.append("判定: {}".format(item.get("badge")))
        if item.get("diff"):
            description_lines.append("差分: {}".format(item.get("diff")))
        if item.get("summary"):
            description_lines.append(self._truncate_text(item.get("summary"), 3200))

        fields = [
            {
                "name": "Score",
                "value": self._field_value(item.get("score", 0)),
                "inline": True,
            },
            {
                "name": "Category",
                "value": self._field_value(item.get("category") or "-"),
                "inline": True,
            },
            {
                "name": "Updated",
                "value": self._field_value(item.get("updated_at") or "-"),
                "inline": True,
            },
            {
                "name": "Author",
                "value": self._field_value(item.get("author") or "-"),
                "inline": True,
            },
            {
                "name": "Version",
                "value": self._field_value(item.get("version") or "-"),
                "inline": True,
            },
            {
                "name": "Source",
                "value": self._field_value(item.get("source") or "wordpress"),
                "inline": True,
            },
        ]

        tags = item.get("tags_ja", []) if isinstance(item.get("tags_ja"), list) else []
        if item.get("downloads") or item.get("endorsements"):
            fields.append(
                {
                    "name": "Downloads / Endorsements",
                    "value": self._field_value("{} / {}".format(item.get("downloads", 0), item.get("endorsements", 0))),
                    "inline": False,
                }
            )
        if tags:
            fields.append(
                {
                    "name": "Tags",
                    "value": self._field_value(" / ".join(tags[:4])),
                    "inline": False,
                }
            )

        embed: dict[str, Any] = {
            "title": self._truncate_text(item.get("title") or "Nexus MOD 更新", 256),
            "url": item.get("url") or None,
            "description": self._truncate_text("\n\n".join(description_lines), 3800),
            "color": self._score_color(item.get("score", 0)),
            "author": {
                "name": "Nexus Mods Watch",
            },
            "fields": fields,
        }

        if not embed["description"]:
            del embed["description"]

        image_url = self._sanitize_text(item.get("image_url", ""))
        if image_url:
            embed["image"] = {"url": image_url}

        return embed

    def _build_components(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        buttons = []
        if item.get("url"):
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": "Nexus Mods で開く / Open",
                    "url": item.get("url"),
                }
            )
        buttons.append(
            {
                "type": 2,
                "style": 2,
                "label": "お気に入り / Favorite",
                "custom_id": "nexus:favorite",
            }
        )
        return [{"type": 1, "components": buttons[:5]}]

    def _resolve_limit(self, limit: int | None = None) -> int:
        raw = self.config.watch_limit if limit is None else limit
        return max(1, min(int(raw or 20), 50))

    def _score_color(self, score: Any) -> int:
        value = _safe_int(score)
        if value >= 80:
            return 0x2ECC71
        if value >= 60:
            return 0x3498DB
        if value >= 40:
            return 0xF39C12
        return 0x95A5A6

    def _field_value(self, value: Any) -> str:
        text = self._sanitize_text(value)
        return self._truncate_text(text or "-", 1024)

    def _sanitize_multiline_text(self, value: Any) -> str:
        raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        parts = []
        previous_blank = True

        for line in raw.split("\n"):
            cleaned = self._sanitize_text(line)
            if cleaned:
                parts.append(cleaned)
                previous_blank = False
                continue
            if not previous_blank and parts:
                parts.append("")
            previous_blank = True

        return "\n".join(parts).strip()

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
        updated_ts = _safe_int(item.get("updated_ts", 0))
        if updated_ts > 0:
            return updated_ts
        return int(self._parse_timestamp(item.get("updated_at", "")) or 0)

    def _parse_timestamp(self, value: Any) -> float | None:
        text = self._sanitize_text(value)
        if not text:
            return None
        patterns = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
        for pattern in patterns:
            try:
                return datetime.strptime(text, pattern).timestamp()
            except Exception:
                continue
        return None