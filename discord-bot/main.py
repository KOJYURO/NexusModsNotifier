import json
import os
import threading
import time
import asyncio
import hmac
import hashlib
import secrets
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen

try:
    import discord
except Exception:
    discord = None

from watchers.nexus_watcher import NexusWatcher, NexusWatcherConfig
from watchers.twitch_chat_bridge import TwitchChatBridge, TwitchChatBridgeConfig
from watchers.twitch_watcher import TwitchWatcher, TwitchWatcherConfig
from watchers.twitter_watcher import TwitterWatcher, TwitterWatcherConfig


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:
                os.environ[key] = val


load_env_file(os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DISCORD_GUILD_ID = (os.getenv("DISCORD_GUILD_ID", "") or "").strip()
DISCORD_THREAD_CHANNEL_ID = (os.getenv("DISCORD_THREAD_CHANNEL_ID", "") or "").strip()
DISCORD_ANNOUNCEMENT_CHANNEL_ID = (os.getenv("DISCORD_ANNOUNCEMENT_CHANNEL_ID", "") or "").strip()
DISCORD_NEXUS_NOTIFY_CHANNEL_ID = (os.getenv("DISCORD_NEXUS_NOTIFY_CHANNEL_ID", "") or "").strip()
DISCORD_NEXUS_MEDIA_CHANNEL_ID = (os.getenv("DISCORD_NEXUS_MEDIA_CHANNEL_ID", "") or "").strip()
DISCORD_NEXUS_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_NEXUS_NOTIFY_THREAD_NAME", "新着通知") or "新着通知").strip()
DISCORD_NEXUS_NOTIFY_TAG_NAME = (os.getenv("DISCORD_NEXUS_NOTIFY_TAG_NAME", "新着通知") or "新着通知").strip()
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8787") or "8787")
BOT_API_SHARED_KEY = (os.getenv("BOT_API_SHARED_KEY", "") or "").strip()
BOT_PUBLIC_BASE_URL = (os.getenv("BOT_PUBLIC_BASE_URL", "https://bot.7daystodie.jp") or "https://bot.7daystodie.jp").strip().rstrip("/")
EVENT_LEADERBOARD_DB_PATH = (
    os.getenv("EVENT_LEADERBOARD_DB_PATH", "/root/DiscordBot/7DJPGameManager/runtime/game_manager.db")
    or "/root/DiscordBot/7DJPGameManager/runtime/game_manager.db"
).strip()
WORDPRESS_ACCOUNT_LINK_URL = (os.getenv("WORDPRESS_ACCOUNT_LINK_URL", "https://7daystodie.jp/community/account-link/") or "https://7daystodie.jp/community/account-link/").strip()
WP_BRIDGE_ENDPOINT = (os.getenv("WP_BRIDGE_ENDPOINT", "") or "").strip()
WP_BRIDGE_BEARER_TOKEN = (os.getenv("WP_BRIDGE_BEARER_TOKEN", "") or "").strip()
WP_BRIDGE_HMAC_SECRET = (os.getenv("WP_BRIDGE_HMAC_SECRET", "") or "").strip()
WP_BRIDGE_TIMEOUT = int(os.getenv("WP_BRIDGE_TIMEOUT", "10") or "10")
WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER = (
    (os.getenv("WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER", "1") or "1").strip().lower()
    not in ("0", "false", "off")
)
WP_BRIDGE_DEBUG = (os.getenv("WP_BRIDGE_DEBUG", "0") or "0").strip().lower() in ("1", "true", "on")
DISCORD_GATEWAY_ENABLED = (os.getenv("DISCORD_GATEWAY_ENABLED", "1") or "1").strip().lower() not in ("0", "false", "off")
PROFILE_NOTIFY_STATE_FILE = (os.getenv("PROFILE_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "profile_notify_state.json")).strip()
WP_NEXUS_WATCH_ENDPOINT = (os.getenv("WP_NEXUS_WATCH_ENDPOINT", "") or "").strip()
WP_NEXUS_CATEGORIES_ENDPOINT = (os.getenv("WP_NEXUS_CATEGORIES_ENDPOINT", "") or "").strip()
if (not WP_NEXUS_CATEGORIES_ENDPOINT) and "watch-updates" in WP_NEXUS_WATCH_ENDPOINT:
    WP_NEXUS_CATEGORIES_ENDPOINT = WP_NEXUS_WATCH_ENDPOINT.replace("watch-updates", "categories", 1)
WP_NEXUS_WATCH_TOKEN = (os.getenv("WP_NEXUS_WATCH_TOKEN", "") or "").strip()
NEXUS_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("NEXUS_NOTIFY_POLL_SECONDS", "300") or "300"))
NEXUS_NOTIFY_STATE_FILE = (os.getenv("NEXUS_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "nexus_notify_state.json")).strip()
NEXUS_NOTIFY_PRIME_ON_START = (os.getenv("NEXUS_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
NEXUS_MEDIA_INIT_TAGS_ON_START = (os.getenv("NEXUS_MEDIA_INIT_TAGS_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
WP_NEXUS_FALLBACK_ENABLED = (os.getenv("WP_NEXUS_FALLBACK_ENABLED", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
WP_NEXUS_FALLBACK_POSTS_ENDPOINT = (os.getenv("WP_NEXUS_FALLBACK_POSTS_ENDPOINT", "https://7daystodie.jp/wp-json/wp/v2/posts") or "").strip()
WP_NEXUS_FALLBACK_CATEGORY_IDS = (os.getenv("WP_NEXUS_FALLBACK_CATEGORY_IDS", "") or "").strip()
WP_NEXUS_FALLBACK_MAX_AGE_HOURS = max(1, min(24 * 30, int(os.getenv("WP_NEXUS_FALLBACK_MAX_AGE_HOURS", "168") or "168")))

DISCORD_SOCIAL_NOTIFY_CHANNEL_ID = (os.getenv("DISCORD_SOCIAL_NOTIFY_CHANNEL_ID", "") or "").strip()
WP_SOCIAL_WATCH_ENDPOINT = (os.getenv("WP_SOCIAL_WATCH_ENDPOINT", "") or "").strip()
WP_SOCIAL_WATCH_TOKEN = (os.getenv("WP_SOCIAL_WATCH_TOKEN", "") or "").strip()
WP_TWITCH_WATCH_ENDPOINT = (os.getenv("WP_TWITCH_WATCH_ENDPOINT", "") or "").strip()
if (not WP_TWITCH_WATCH_ENDPOINT) and "watch-updates" in WP_SOCIAL_WATCH_ENDPOINT:
    WP_TWITCH_WATCH_ENDPOINT = WP_SOCIAL_WATCH_ENDPOINT.replace("watch-updates", "twitch-updates", 1)
WP_TWITCH_WATCH_TOKEN = (os.getenv("WP_TWITCH_WATCH_TOKEN", "") or WP_SOCIAL_WATCH_TOKEN).strip()
WP_YOUTUBE_WATCH_ENDPOINT = (os.getenv("WP_YOUTUBE_WATCH_ENDPOINT", "") or "").strip()
if (not WP_YOUTUBE_WATCH_ENDPOINT) and "watch-updates" in WP_SOCIAL_WATCH_ENDPOINT:
    WP_YOUTUBE_WATCH_ENDPOINT = WP_SOCIAL_WATCH_ENDPOINT.replace("watch-updates", "youtube-updates", 1)
WP_YOUTUBE_WATCH_TOKEN = (os.getenv("WP_YOUTUBE_WATCH_TOKEN", "") or WP_SOCIAL_WATCH_TOKEN).strip()
WP_TWITTER_WATCH_ENDPOINT = (os.getenv("WP_TWITTER_WATCH_ENDPOINT", "") or "").strip()
if (not WP_TWITTER_WATCH_ENDPOINT) and "watch-updates" in WP_SOCIAL_WATCH_ENDPOINT:
    WP_TWITTER_WATCH_ENDPOINT = WP_SOCIAL_WATCH_ENDPOINT.replace("watch-updates", "twitter-updates", 1)
WP_TWITTER_WATCH_TOKEN = (os.getenv("WP_TWITTER_WATCH_TOKEN", "") or WP_SOCIAL_WATCH_TOKEN).strip()
SOCIAL_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("SOCIAL_NOTIFY_POLL_SECONDS", "300") or "300"))
SOCIAL_NOTIFY_STATE_FILE = (os.getenv("SOCIAL_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "social_notify_state.json")).strip()
COMMENTS_NOTIFY_ENABLED = (os.getenv("COMMENTS_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
WP_COMMENTS_WATCH_ENDPOINT = (os.getenv("WP_COMMENTS_WATCH_ENDPOINT", "") or "").strip()
WP_COMMENTS_WATCH_TOKEN = (os.getenv("WP_COMMENTS_WATCH_TOKEN", "") or "").strip()
DISCORD_COMMENTS_NOTIFY_CHANNEL_ID = (os.getenv("DISCORD_COMMENTS_NOTIFY_CHANNEL_ID", "") or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
COMMENTS_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("COMMENTS_NOTIFY_POLL_SECONDS", "300") or "300"))
COMMENTS_NOTIFY_STATE_FILE = (os.getenv("COMMENTS_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "comments_notify_state.json")).strip()

TWITCH_NOTIFY_ENABLED = (os.getenv("TWITCH_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
TWITCH_CLIENT_ID = (os.getenv("TWITCH_CLIENT_ID", "") or "").strip()
TWITCH_CLIENT_SECRET = (os.getenv("TWITCH_CLIENT_SECRET", "") or "").strip()
TWITCH_SUPPORT_DB_PATH = (
    os.getenv("TWITCH_SUPPORT_DB_PATH", "/root/DiscordBot/7DJPTwitchIntegrationHelper/runtime/twitch_support.db")
    or "/root/DiscordBot/7DJPTwitchIntegrationHelper/runtime/twitch_support.db"
).strip()
TWITCH_NOTIFY_USER_LOGINS = (os.getenv("TWITCH_NOTIFY_USER_LOGINS", "") or "").strip()
TWITCH_NOTIFY_CHANNEL_ID = (os.getenv("TWITCH_NOTIFY_CHANNEL_ID", "") or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
DISCORD_TWITCH_MEDIA_CHANNEL_ID = (os.getenv("DISCORD_TWITCH_MEDIA_CHANNEL_ID", "") or "").strip()
DISCORD_TWITCH_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_TWITCH_NOTIFY_THREAD_NAME", "新着通知") or "新着通知").strip()
DISCORD_TWITCH_NOTIFY_TAG_NAME = (os.getenv("DISCORD_TWITCH_NOTIFY_TAG_NAME", "新着通知") or "新着通知").strip()
TWITCH_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("TWITCH_NOTIFY_POLL_SECONDS", "180") or "180"))
TWITCH_NOTIFY_STATE_FILE = (os.getenv("TWITCH_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "twitch_notify_state.json")).strip()
TWITCH_NOTIFY_PRIME_ON_START = (os.getenv("TWITCH_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
TWITCH_NOTIFY_FETCH_LIMIT = max(1, min(100, int(os.getenv("TWITCH_NOTIFY_FETCH_LIMIT", "20") or "20")))
TWITCH_MEDIA_INIT_TAGS_ON_START = (os.getenv("TWITCH_MEDIA_INIT_TAGS_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
TWITCH_CHAT_ENABLED = (os.getenv("TWITCH_CHAT_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
TWITCH_CHAT_DISCORD_CHANNEL_ID = (os.getenv("TWITCH_CHAT_DISCORD_CHANNEL_ID", "") or TWITCH_NOTIFY_CHANNEL_ID).strip()
TWITCH_CHAT_OWNER_DISCORD_USER_ID = re.sub(r"[^0-9]", "", (os.getenv("TWITCH_CHAT_OWNER_DISCORD_USER_ID", "") or "").strip())
TWITCH_CHAT_BROADCASTER_LOGIN = (os.getenv("TWITCH_CHAT_BROADCASTER_LOGIN", "") or "").strip()
TWITCH_CHAT_BROADCASTER_USER_ID = (os.getenv("TWITCH_CHAT_BROADCASTER_USER_ID", "") or "").strip()
TWITCH_CHAT_BROADCASTER_LOGINS = (
    os.getenv("TWITCH_CHAT_BROADCASTER_LOGINS", "")
    or TWITCH_NOTIFY_USER_LOGINS
    or TWITCH_CHAT_BROADCASTER_LOGIN
).strip()
TWITCH_CHAT_ALLOWED_GAME_NAMES = (os.getenv("TWITCH_CHAT_ALLOWED_GAME_NAMES", "") or "").strip()
TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS = (
    os.getenv(
        "TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS",
        "1" if DISCORD_TWITCH_MEDIA_CHANNEL_ID else "0",
    )
    or ("1" if DISCORD_TWITCH_MEDIA_CHANNEL_ID else "0")
).strip().lower() in ("1", "true", "on", "yes")
TWITCH_CHAT_STREAM_CONTEXT_CACHE_SECONDS = max(15, int(os.getenv("TWITCH_CHAT_STREAM_CONTEXT_CACHE_SECONDS", "60") or "60"))
TWITCH_CHAT_USER_ACCESS_TOKEN = (os.getenv("TWITCH_CHAT_USER_ACCESS_TOKEN", "") or "").strip()
TWITCH_CHAT_REFRESH_TOKEN = (os.getenv("TWITCH_CHAT_REFRESH_TOKEN", "") or "").strip()
TWITCH_CHAT_XML_PATH = (os.getenv("TWITCH_CHAT_XML_PATH", "") or "/home/steam/7dtd/Data/Config/twitch.xml").strip()
TWITCH_CHAT_AUTH_STATE_FILE = (
    os.getenv("TWITCH_CHAT_AUTH_STATE_FILE", "")
    or os.path.join(os.path.dirname(__file__), "twitch_chat_auth_state.json")
).strip()
TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS = max(0, int(os.getenv("TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS", "3600") or "3600"))

TWITTER_NOTIFY_ENABLED = (os.getenv("TWITTER_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
TWITTER_NOTIFY_CHANNEL_ID = (os.getenv("TWITTER_NOTIFY_CHANNEL_ID", "") or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
DISCORD_TWITTER_MEDIA_CHANNEL_ID = (os.getenv("DISCORD_TWITTER_MEDIA_CHANNEL_ID", "") or "").strip()
DISCORD_TWITTER_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_TWITTER_NOTIFY_THREAD_NAME", "新着通知") or "新着通知").strip()
DISCORD_TWITTER_NOTIFY_TAG_NAME = (os.getenv("DISCORD_TWITTER_NOTIFY_TAG_NAME", "新着通知") or "新着通知").strip()
TWITTER_NOTIFY_POLL_SECONDS = max(86400, int(os.getenv("TWITTER_NOTIFY_POLL_SECONDS", "86400") or "86400"))
TWITTER_NOTIFY_STATE_FILE = (os.getenv("TWITTER_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "twitter_notify_state.json")).strip()
TWITTER_NOTIFY_PRIME_ON_START = (os.getenv("TWITTER_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
TWITTER_NOTIFY_FETCH_LIMIT = max(1, min(100, int(os.getenv("TWITTER_NOTIFY_FETCH_LIMIT", "20") or "20")))
TWITTER_MEDIA_INIT_TAGS_ON_START = (os.getenv("TWITTER_MEDIA_INIT_TAGS_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")

YOUTUBE_NOTIFY_ENABLED = (os.getenv("YOUTUBE_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
YOUTUBE_NOTIFY_CHANNEL_IDS = (os.getenv("YOUTUBE_NOTIFY_CHANNEL_IDS", "") or "").strip()
YOUTUBE_NOTIFY_API_KEY = (os.getenv("YOUTUBE_NOTIFY_API_KEY", "") or "").strip()
YOUTUBE_NOTIFY_CHANNEL_ID = (os.getenv("YOUTUBE_NOTIFY_CHANNEL_ID", "") or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
DISCORD_YOUTUBE_MEDIA_CHANNEL_ID = (os.getenv("DISCORD_YOUTUBE_MEDIA_CHANNEL_ID", "") or "").strip()
DISCORD_YOUTUBE_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_YOUTUBE_NOTIFY_THREAD_NAME", "新着通知") or "新着通知").strip()
DISCORD_YOUTUBE_NOTIFY_TAG_NAME = (os.getenv("DISCORD_YOUTUBE_NOTIFY_TAG_NAME", "新着通知") or "新着通知").strip()
YOUTUBE_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("YOUTUBE_NOTIFY_POLL_SECONDS", "300") or "300"))
YOUTUBE_NOTIFY_STATE_FILE = (os.getenv("YOUTUBE_NOTIFY_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "youtube_notify_state.json")).strip()
YOUTUBE_NOTIFY_PRIME_ON_START = (os.getenv("YOUTUBE_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
YOUTUBE_MEDIA_INIT_TAGS_ON_START = (os.getenv("YOUTUBE_MEDIA_INIT_TAGS_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
YOUTUBE_COMMENTS_NOTIFY_ENABLED = (os.getenv("YOUTUBE_COMMENTS_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS = (os.getenv("YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS", "") or YOUTUBE_NOTIFY_CHANNEL_IDS).strip()
YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID = (os.getenv("YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID", "") or YOUTUBE_NOTIFY_CHANNEL_ID or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
DISCORD_YOUTUBE_COMMENTS_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_YOUTUBE_COMMENTS_NOTIFY_THREAD_NAME", "動画コメント") or "動画コメント").strip()
YOUTUBE_COMMENTS_NOTIFY_POLL_SECONDS = max(60, int(os.getenv("YOUTUBE_COMMENTS_NOTIFY_POLL_SECONDS", "900") or "900"))
YOUTUBE_COMMENTS_NOTIFY_STATE_FILE = (
    os.getenv("YOUTUBE_COMMENTS_NOTIFY_STATE_FILE", "")
    or os.path.join(os.path.dirname(__file__), "youtube_comments_notify_state.json")
).strip()
YOUTUBE_COMMENTS_NOTIFY_PRIME_ON_START = (os.getenv("YOUTUBE_COMMENTS_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
YOUTUBE_COMMENTS_FETCH_LIMIT = max(1, min(100, int(os.getenv("YOUTUBE_COMMENTS_FETCH_LIMIT", "20") or "20")))
YOUTUBE_COMMENTS_VIDEO_LIMIT = max(1, min(20, int(os.getenv("YOUTUBE_COMMENTS_VIDEO_LIMIT", "5") or "5")))
YOUTUBE_COMMENTS_PER_VIDEO_LIMIT = max(1, min(20, int(os.getenv("YOUTUBE_COMMENTS_PER_VIDEO_LIMIT", "5") or "5")))
YOUTUBE_LIVECHAT_NOTIFY_ENABLED = (os.getenv("YOUTUBE_LIVECHAT_NOTIFY_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_IDS = (os.getenv("YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_IDS", "") or YOUTUBE_NOTIFY_CHANNEL_IDS).strip()
YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID = (os.getenv("YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID", "") or YOUTUBE_NOTIFY_CHANNEL_ID or DISCORD_SOCIAL_NOTIFY_CHANNEL_ID).strip()
DISCORD_YOUTUBE_LIVECHAT_NOTIFY_THREAD_NAME = (os.getenv("DISCORD_YOUTUBE_LIVECHAT_NOTIFY_THREAD_NAME", "ライブチャット") or "ライブチャット").strip()
YOUTUBE_LIVECHAT_POLL_SECONDS = max(60, int(os.getenv("YOUTUBE_LIVECHAT_POLL_SECONDS", "120") or "120"))
YOUTUBE_LIVECHAT_STATE_FILE = (
    os.getenv("YOUTUBE_LIVECHAT_STATE_FILE", "")
    or os.path.join(os.path.dirname(__file__), "youtube_livechat_notify_state.json")
).strip()
YOUTUBE_LIVECHAT_NOTIFY_PRIME_ON_START = (os.getenv("YOUTUBE_LIVECHAT_NOTIFY_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
YOUTUBE_LIVECHAT_FETCH_LIMIT = max(1, min(200, int(os.getenv("YOUTUBE_LIVECHAT_FETCH_LIMIT", "50") or "50")))
YOUTUBE_LIVECHAT_VIDEO_LIMIT = max(1, min(20, int(os.getenv("YOUTUBE_LIVECHAT_VIDEO_LIMIT", "5") or "5")))
WP_PAGE_PROMO_ENABLED = (os.getenv("WP_PAGE_PROMO_ENABLED", "0") or "0").strip().lower() in ("1", "true", "on", "yes")
WP_PAGE_PROMO_ENDPOINT = (os.getenv("WP_PAGE_PROMO_ENDPOINT", "") or "").strip()
WP_PAGE_PROMO_TOKEN = (os.getenv("WP_PAGE_PROMO_TOKEN", "") or "").strip()
DISCORD_PAGE_PROMO_CHANNEL_ID = (os.getenv("DISCORD_PAGE_PROMO_CHANNEL_ID", "") or "").strip()
PAGE_PROMO_POLL_SECONDS = max(60, int(os.getenv("PAGE_PROMO_POLL_SECONDS", "600") or "600"))
PAGE_PROMO_STATE_FILE = (os.getenv("PAGE_PROMO_STATE_FILE", "") or os.path.join(os.path.dirname(__file__), "page_promo_state.json")).strip()
PAGE_PROMO_BATCH_SIZE = max(1, min(10, int(os.getenv("PAGE_PROMO_BATCH_SIZE", "10") or "10")))
PAGE_PROMO_MAX_ITEMS_PER_SYNC = max(1, min(100, int(os.getenv("PAGE_PROMO_MAX_ITEMS_PER_SYNC", "50") or "50")))
PAGE_PROMO_PRIME_ON_START = (os.getenv("PAGE_PROMO_PRIME_ON_START", "1") or "1").strip().lower() not in ("0", "false", "off", "no")
PAGE_PROMO_COMMENT_TEMPLATE = (
    os.getenv("PAGE_PROMO_COMMENT_TEMPLATE", "")
    or "気になるページがあればコメントで教えてください。({page}/{pages})"
).strip()
DISCORD_INSTANCE_ROLE_PREFIX = (os.getenv("DISCORD_INSTANCE_ROLE_PREFIX", "instance") or "instance").strip()
DISCORD_INSTANCE_ROLE_CAPACITY = (os.getenv("DISCORD_INSTANCE_ROLE_CAPACITY", "") or "").strip()
DISCORD_INSTANCE_ROLE_DEFAULT_CAPACITY = max(0, int(os.getenv("DISCORD_INSTANCE_ROLE_DEFAULT_CAPACITY", "0") or "0"))
DISCORD_STATUS_METRICS_STATE_FILE = (
    os.getenv("DISCORD_STATUS_METRICS_STATE_FILE", "")
    or os.path.join(os.path.dirname(__file__), "discord_status_metrics_state.json")
).strip()
FAVORITE_MEDIA_TAG_NAME = (os.getenv("FAVORITE_MEDIA_TAG_NAME", "お気に入り") or "お気に入り").strip()

DISCORD_PERMISSION_MANAGE_CHANNELS = 1 << 4
DISCORD_PERMISSION_VIEW_CHANNEL = 1 << 10
DISCORD_PERMISSION_SEND_MESSAGES = 1 << 11
DISCORD_PERMISSION_MANAGE_MESSAGES = 1 << 13
DISCORD_PERMISSION_READ_MESSAGE_HISTORY = 1 << 16
DISCORD_PERMISSION_CONNECT = 1 << 20
DISCORD_PERMISSION_SPEAK = 1 << 21
DISCORD_PERMISSION_USE_APPLICATION_COMMANDS = 1 << 31
DISCORD_PERMISSION_MANAGE_THREADS = 1 << 34
NEXUS_FAVORITE_BUTTON_CUSTOM_ID = "nexus:favorite"
TWITCH_FAVORITE_BUTTON_CUSTOM_ID = "twitch:favorite"
TWITTER_FAVORITE_BUTTON_CUSTOM_ID = "twitter:favorite"
YOUTUBE_FAVORITE_BUTTON_CUSTOM_ID = "youtube:favorite"
PROFILE_CARD_THREAD_TOGGLE_CUSTOM_ID = "profile:thread:toggle"
PROFILE_CARD_EDIT_BUTTON_PREFIX = "profile:thread:edit"
PROFILE_CARD_INVITE_BUTTON_PREFIX = "profile:thread:invite"
PROFILE_CARD_IMAGE_BUTTON_PREFIX = "profile:thread:image"
PROFILE_CARD_TAG_BUTTON_PREFIX = "profile:thread:tag"
PROFILE_CARD_CHANNEL_BUTTON_PREFIX = "profile:thread:channel"
PROFILE_CARD_WORKSPACE_BUTTON_PREFIX = "profile:thread:workspace"
PROFILE_CARD_DELETE_BUTTON_PREFIX = "profile:thread:delete"
NEXUS_LEGACY_SAVE_BUTTON_CUSTOM_ID = "nexus:save"
TWITCH_LEGACY_SAVE_BUTTON_CUSTOM_ID = "twitch:save"
TWITTER_LEGACY_SAVE_BUTTON_CUSTOM_ID = "twitter:save"
YOUTUBE_LEGACY_SAVE_BUTTON_CUSTOM_ID = "youtube:save"
CHANNEL_REPOST_LEGACY_IMAGE_BUTTON_CUSTOM_ID = "channelrepost:image"
CHANNEL_REPOST_EDIT_BUTTON_CUSTOM_ID = "channelrepost:edit"

NEXUS_TEMPORARY_CATEGORY_RULES = (
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

# discord.py クライアントと asyncio ループをスレッド間で共有するためのグローバル変数
_discord_client = None
_discord_loop = None


snapshot_lock = threading.Lock()
snapshot = {
    "ok": False,
    "channel_id": DISCORD_THREAD_CHANNEL_ID,
    "count": 0,
    "updated_at": None,
    "threads": [],
    "error": "not initialized",
}

gateway_lock = threading.Lock()
gateway_state = {
    "connected": False,
    "ready": False,
    "user": "",
    "error": "",
    "command_count": 0,
    "command_sync_scope": "",
    "command_sync_error": "",
}


def get_gateway_runtime_check():
    client = _discord_client
    loop = _discord_loop

    loop_valid = loop is not None
    if loop_valid:
        try:
            loop_valid = not loop.is_closed()
        except Exception:
            loop_valid = False

    client_valid = client is not None
    if client_valid:
        try:
            client_valid = not client.is_closed()
        except Exception:
            client_valid = False

    runtime_ok = bool(client_valid and loop_valid)
    return {
        "client_valid": bool(client_valid),
        "loop_valid": bool(loop_valid),
        "runtime_ok": bool(runtime_ok),
    }


def ensure_gateway_runtime():
    runtime = get_gateway_runtime_check()
    if runtime["runtime_ok"]:
        return runtime

    set_gateway_state(connected=False, ready=False)
    return runtime

nexus_notify_lock = threading.Lock()
nexus_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
    "last_source": "",
    "last_total": 0,
    "rebucketed_message_ids": [],
    "last_rebucket_run": None,
    "last_rebucket_error": "",
    "last_rebucket_scanned": 0,
    "last_rebucket_sorted": 0,
}

social_notify_lock = threading.Lock()
social_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
}

comments_notify_lock = threading.Lock()
comments_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
}

profile_notify_lock = threading.Lock()
profile_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
    "enabled": False,
    "voice_channel_id": "",
    "voice_channel_name": "",
    "post_channel_id": "",
    "post_channel_name": "",
    "last_notified_user_id": "",
    "last_notified_message_id": "",
    "last_voice_channel_id": "",
    "last_voice_channel_name": "",
}

twitch_notify_lock = threading.Lock()
twitch_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
}

twitch_chat_lock = threading.Lock()
twitch_chat_state = {
    "enabled": TWITCH_CHAT_ENABLED,
    "running": False,
    "connected": False,
    "awaiting_authorization": TWITCH_CHAT_ENABLED,
    "relay_channel_id": TWITCH_CHAT_DISCORD_CHANNEL_ID,
    "subscription_broadcasters": [],
    "session_id": "",
    "sender_login": "",
    "sender_user_id": "",
    "broadcaster_login": "",
    "broadcaster_user_id": "",
    "subscribed_types": [],
    "token_scopes": [],
    "token_expires_in": 0,
    "auth_source": "env" if TWITCH_CHAT_USER_ACCESS_TOKEN else "file",
    "owner_discord_user_id": TWITCH_CHAT_OWNER_DISCORD_USER_ID,
    "owner_twitch_user_id": "",
    "owner_twitch_login": "",
    "last_event_type": "",
    "last_event_at": None,
    "last_relayed_at": None,
    "last_message_preview": "",
    "tracked_message_count": 0,
    "last_delete_sync_at": None,
    "last_delete_reason": "",
    "last_delete_target": "",
    "last_delete_count": 0,
    "total_deleted_count": 0,
    "last_command": "",
    "last_command_at": None,
    "last_error": "",
}

twitch_chat_auth_lock = threading.Lock()
twitch_chat_stream_context_lock = threading.Lock()
twitch_chat_stream_context_cache = {
    "expires_at": 0.0,
    "source": "",
    "last_error": "",
    "by_login": {},
}
twitch_chat_auth_state = {
    "access_token": "",
    "refresh_token": "",
    "user_id": "",
    "login": "",
    "owner_discord_user_id": TWITCH_CHAT_OWNER_DISCORD_USER_ID,
    "owner_twitch_user_id": "",
    "owner_twitch_login": "",
    "scopes": [],
    "updated_at": None,
    "source": "env" if TWITCH_CHAT_USER_ACCESS_TOKEN else "file",
}

twitch_chat_oauth_lock = threading.Lock()
twitch_chat_oauth_states = {}

twitter_notify_lock = threading.Lock()
twitter_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
    "last_total": 0,
    "poll_interval_seconds": TWITTER_NOTIFY_POLL_SECONDS,
    "poll_interval_source": "env",
}

youtube_notify_lock = threading.Lock()
youtube_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "last_source": "",
    "primed": False,
}

youtube_comments_notify_lock = threading.Lock()
youtube_comments_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "last_source": "",
    "primed": False,
    "last_total": 0,
    "recent_items": [],
}

youtube_livechat_notify_lock = threading.Lock()
youtube_livechat_notify_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "last_source": "",
    "primed": False,
    "last_total": 0,
    "page_tokens": {},
    "active_chat_ids": [],
    "active_video_ids": [],
    "recent_items": [],
}

page_promo_lock = threading.Lock()
page_promo_state = {
    "seen_ids": [],
    "last_run": None,
    "last_error": "",
    "primed": False,
}

_nexus_watcher = None
_nexus_watcher_factory_lock = threading.Lock()
_twitch_watcher = None
_twitch_watcher_factory_lock = threading.Lock()
_twitch_chat_bridge = None
_twitch_chat_bridge_factory_lock = threading.Lock()
_twitter_watcher = None
_twitter_watcher_factory_lock = threading.Lock()

twitch_localization_lock = threading.Lock()
twitch_localization_cache = None
twitch_action_catalog_lock = threading.Lock()
twitch_action_catalog_cache = {
    "path": "",
    "mtime": 0,
    "loaded_at": None,
    "catalog": None,
    "error": "",
}

status_metrics_lock = threading.Lock()
status_metrics_state = {
    "points": [],
}


def load_nexus_notify_state():
    global nexus_notify_state
    try:
        if os.path.exists(NEXUS_NOTIFY_STATE_FILE):
            with open(NEXUS_NOTIFY_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                seen = data.get("seen_ids", [])
                rebucketed = data.get("rebucketed_message_ids", [])
                nexus_notify_state = {
                    "seen_ids": list(seen)[:1000] if isinstance(seen, list) else [],
                    "last_run": data.get("last_run"),
                    "last_error": data.get("last_error", ""),
                    "primed": bool(data.get("primed", False)),
                    "last_source": data.get("last_source", ""),
                    "last_total": int(data.get("last_total", 0) or 0),
                    "rebucketed_message_ids": list(rebucketed)[-5000:] if isinstance(rebucketed, list) else [],
                    "last_rebucket_run": data.get("last_rebucket_run"),
                    "last_rebucket_error": data.get("last_rebucket_error", ""),
                    "last_rebucket_scanned": int(data.get("last_rebucket_scanned", 0) or 0),
                    "last_rebucket_sorted": int(data.get("last_rebucket_sorted", 0) or 0),
                }
    except Exception as exc:
        print("load_nexus_notify_state error: {}".format(exc))


def save_nexus_notify_state():
    try:
        with nexus_notify_lock:
            payload = dict(nexus_notify_state)
            payload["seen_ids"] = list(payload.get("seen_ids", []))[-1000:]
            payload["primed"] = bool(payload.get("primed", False))
            payload["last_source"] = str(payload.get("last_source", "") or "")
            payload["last_total"] = int(payload.get("last_total", 0) or 0)
            payload["rebucketed_message_ids"] = list(payload.get("rebucketed_message_ids", []))[-5000:]
            payload["last_rebucket_error"] = str(payload.get("last_rebucket_error", "") or "")
            payload["last_rebucket_scanned"] = int(payload.get("last_rebucket_scanned", 0) or 0)
            payload["last_rebucket_sorted"] = int(payload.get("last_rebucket_sorted", 0) or 0)
        with open(NEXUS_NOTIFY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as exc:
        print("save_nexus_notify_state error: {}".format(exc))


def load_discord_status_metrics_state():
    global status_metrics_state
    try:
        if os.path.exists(DISCORD_STATUS_METRICS_STATE_FILE):
            with open(DISCORD_STATUS_METRICS_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                points = data.get("points", [])
                if not isinstance(points, list):
                    points = []
                normalized_points = []
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    try:
                        ts = int(point.get("ts", 0) or 0)
                    except Exception:
                        ts = 0
                    if ts <= 0:
                        continue
                    normalized_points.append(
                        {
                            "ts": ts,
                            "thread_message_total": int(point.get("thread_message_total", 0) or 0),
                            "thread_participant_total": int(point.get("thread_participant_total", 0) or 0),
                            "instance_member_total": int(point.get("instance_member_total", 0) or 0),
                        }
                    )
                status_metrics_state = {"points": normalized_points[-10000:]}
    except Exception as exc:
        print("load_discord_status_metrics_state error: {}".format(exc))


def save_discord_status_metrics_state():
    try:
        with status_metrics_lock:
            points = list(status_metrics_state.get("points", []))[-10000:]
        with open(DISCORD_STATUS_METRICS_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"points": points}, f, ensure_ascii=False)
    except Exception as exc:
        print("save_discord_status_metrics_state error: {}".format(exc))


def _parse_instance_role_capacity_map(raw):
    capacity_map = {}
    for token in parse_csv_list(raw):
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        key = sanitize_text(key).lower()
        value = sanitize_text(value)
        if not key or not value:
            continue
        try:
            capacity = int(value)
        except Exception:
            continue
        if capacity > 0:
            capacity_map[key] = capacity
    return capacity_map


def _compute_delta24h_metrics(thread_message_total, thread_participant_total, instance_member_total):
    now = int(time.time())
    current_point = {
        "ts": now,
        "thread_message_total": int(thread_message_total or 0),
        "thread_participant_total": int(thread_participant_total or 0),
        "instance_member_total": int(instance_member_total or 0),
    }

    with status_metrics_lock:
        points = list(status_metrics_state.get("points", []))
        keep_after = now - (72 * 3600)
        points = [p for p in points if isinstance(p, dict) and int(p.get("ts", 0) or 0) >= keep_after]
        points.append(current_point)
        points = points[-10000:]
        status_metrics_state["points"] = points

        target_ts = now - (24 * 3600)
        baseline = None
        for point in reversed(points):
            point_ts = int(point.get("ts", 0) or 0)
            if point_ts <= target_ts:
                baseline = point
                break

    save_discord_status_metrics_state()

    if not baseline:
        return {
            "delta24h_available": False,
            "delta24h_hours_covered": 0,
            "thread_message_delta24h": 0,
            "thread_participant_delta24h": 0,
            "instance_member_delta24h": 0,
        }

    baseline_ts = int(baseline.get("ts", 0) or 0)
    hours_covered = max(0, int((now - baseline_ts) / 3600))
    return {
        "delta24h_available": True,
        "delta24h_hours_covered": hours_covered,
        "thread_message_delta24h": current_point["thread_message_total"] - int(baseline.get("thread_message_total", 0) or 0),
        "thread_participant_delta24h": current_point["thread_participant_total"] - int(baseline.get("thread_participant_total", 0) or 0),
        "instance_member_delta24h": current_point["instance_member_total"] - int(baseline.get("instance_member_total", 0) or 0),
    }


def now_iso_utc():
    return datetime.utcnow().isoformat() + "Z"


def parse_csv_list(raw):
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def sanitize_text(value):
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def strip_html_tags(value):
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return sanitize_text(text)


def truncate_text(value, limit):
    raw = str(value or "")
    if limit <= 0:
        return ""
    if len(raw) <= limit:
        return raw
    if limit <= 3:
        return raw[:limit]
    return raw[: limit - 3] + "..."


def infer_nexus_temporary_tags(*values, limit=4):
    haystack = " ".join([sanitize_text(value).lower() for value in values if sanitize_text(value)])
    if not haystack:
        return []

    tags = []
    max_tags = max(1, int(limit or 4))
    for tag_name, keywords in NEXUS_TEMPORARY_CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            if tag_name not in tags:
                tags.append(tag_name)
        if len(tags) >= max_tags:
            break
    return tags


def token_fingerprint(value):
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def bridge_debug(message):
    if WP_BRIDGE_DEBUG:
        print("[wp-bridge] {}".format(message))


def discord_request_json(path):
    return discord_api_request_json(path, method="GET")


def discord_api_request_json(path, method="GET", payload=None):
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")

    url = "https://discord.com/api/v10{}".format(path)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = Request(url, data=body, method=method)
    req.add_header("Authorization", "Bot {}".format(DISCORD_BOT_TOKEN))
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "DiscordBot (https://7daystodie.jp, 1.0)")

    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError("Discord API HTTPError {} {}".format(e.code, body))
    except URLError as e:
        raise RuntimeError("Discord API URLError {}".format(e))


def discord_post_json(path, payload):
    return discord_api_request_json(path, method="POST", payload=payload)


def discord_patch_json(path, payload):
    return discord_api_request_json(path, method="PATCH", payload=payload)


def discord_put_json(path, payload=None):
    return discord_api_request_json(path, method="PUT", payload=payload)


def discord_delete_json(path):
    return discord_api_request_json(path, method="DELETE")


def fetch_discord_channel_messages(channel_id, limit=100, before_message_id="", after_message_id=""):
    channel_text = sanitize_text(channel_id)
    if not channel_text or not channel_text.isdigit():
        raise RuntimeError("Discord channel_id is invalid")

    capped = max(1, min(int(limit or 100), 100))
    path = "/channels/{}/messages?limit={}".format(channel_text, capped)
    before_text = sanitize_text(before_message_id)
    if before_text:
        if not before_text.isdigit():
            raise RuntimeError("before_message_id is invalid")
        path += "&before={}".format(before_text)

    after_text = sanitize_text(after_message_id)
    if after_text:
        if not after_text.isdigit():
            raise RuntimeError("after_message_id is invalid")
        path += "&after={}".format(after_text)

    rows = discord_request_json(path)
    if not isinstance(rows, list):
        raise RuntimeError("Discord channel messages response is invalid")
    return [row for row in rows if isinstance(row, dict)]


def clamp_poll_seconds(value, default_value=60):
    min_floor = max(60, int(default_value or 60))
    try:
        resolved = int(value or 0)
    except Exception:
        resolved = min_floor
    return max(min_floor, resolved)


def load_social_notify_state(path, lock_obj, target_state):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                with lock_obj:
                    target_state["seen_ids"] = list(data.get("seen_ids", []))[-2000:]
                    target_state["last_run"] = data.get("last_run")
                    target_state["last_error"] = data.get("last_error", "")
                    target_state["primed"] = bool(data.get("primed", False))
                    for key, current_value in list(target_state.items()):
                        if key in ("seen_ids", "last_run", "last_error", "primed", "last_total", "poll_interval_seconds", "poll_interval_source"):
                            continue
                        if key not in data:
                            continue
                        loaded_value = data.get(key)
                        if isinstance(current_value, dict) and not isinstance(loaded_value, dict):
                            continue
                        if isinstance(current_value, list) and not isinstance(loaded_value, list):
                            continue
                        target_state[key] = loaded_value
                    if "last_total" in target_state:
                        target_state["last_total"] = int(data.get("last_total", target_state.get("last_total", 0)) or 0)
                    if "poll_interval_seconds" in target_state:
                        target_state["poll_interval_seconds"] = clamp_poll_seconds(
                            data.get("poll_interval_seconds", target_state.get("poll_interval_seconds", TWITTER_NOTIFY_POLL_SECONDS)),
                            target_state.get("poll_interval_seconds", TWITTER_NOTIFY_POLL_SECONDS),
                        )
                        target_state["poll_interval_source"] = str(data.get("poll_interval_source", target_state.get("poll_interval_source", "env")) or "env")
    except Exception as exc:
        print("load_social_notify_state error ({}): {}".format(path, exc))


def save_social_notify_state(path, lock_obj, source_state):
    try:
        with lock_obj:
            payload = {
                "seen_ids": list(source_state.get("seen_ids", []))[-2000:],
                "last_run": source_state.get("last_run"),
                "last_error": source_state.get("last_error", ""),
                "primed": bool(source_state.get("primed", False)),
            }
            if "last_total" in source_state:
                payload["last_total"] = int(source_state.get("last_total", 0) or 0)
            if "poll_interval_seconds" in source_state:
                payload["poll_interval_seconds"] = clamp_poll_seconds(
                    source_state.get("poll_interval_seconds", TWITTER_NOTIFY_POLL_SECONDS),
                    TWITTER_NOTIFY_POLL_SECONDS,
                )
                payload["poll_interval_source"] = str(source_state.get("poll_interval_source", "env") or "env")
            for key, value in source_state.items():
                if key in ("seen_ids", "last_run", "last_error", "primed", "last_total", "poll_interval_seconds", "poll_interval_source"):
                    continue
                payload[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as exc:
        print("save_social_notify_state error ({}): {}".format(path, exc))


def get_profile_notify_state_snapshot():
    with profile_notify_lock:
        return dict(profile_notify_state)


def save_profile_notify_state():
    save_social_notify_state(PROFILE_NOTIFY_STATE_FILE, profile_notify_lock, profile_notify_state)


def configure_profile_notify_state(voice_channel_id, voice_channel_name, post_channel_id, post_channel_name):
    with profile_notify_lock:
        profile_notify_state["enabled"] = True
        profile_notify_state["voice_channel_id"] = sanitize_text(voice_channel_id)
        profile_notify_state["voice_channel_name"] = truncate_text(sanitize_text(voice_channel_name), 100)
        profile_notify_state["post_channel_id"] = sanitize_text(post_channel_id)
        profile_notify_state["post_channel_name"] = truncate_text(sanitize_text(post_channel_name), 100)
        profile_notify_state["last_error"] = ""
    save_profile_notify_state()
    return get_profile_notify_state_snapshot()


def clear_profile_notify_state():
    with profile_notify_lock:
        profile_notify_state["enabled"] = False
        profile_notify_state["voice_channel_id"] = ""
        profile_notify_state["voice_channel_name"] = ""
        profile_notify_state["post_channel_id"] = ""
        profile_notify_state["post_channel_name"] = ""
        profile_notify_state["last_run"] = None
        profile_notify_state["last_error"] = ""
        profile_notify_state["last_notified_user_id"] = ""
        profile_notify_state["last_notified_message_id"] = ""
        profile_notify_state["last_voice_channel_id"] = ""
        profile_notify_state["last_voice_channel_name"] = ""
    save_profile_notify_state()
    return get_profile_notify_state_snapshot()


def record_profile_notify_result(error_message="", discord_user_id="", message_id="", voice_channel_id="", voice_channel_name=""):
    with profile_notify_lock:
        profile_notify_state["last_run"] = now_iso_utc()
        profile_notify_state["last_error"] = truncate_text(sanitize_text(error_message), 1800)
        resolved_user_id = normalize_discord_user_id(discord_user_id)
        if resolved_user_id:
            profile_notify_state["last_notified_user_id"] = resolved_user_id
        resolved_voice_channel_id = sanitize_text(voice_channel_id)
        resolved_voice_channel_name = truncate_text(sanitize_text(voice_channel_name), 100)
        if resolved_voice_channel_id:
            profile_notify_state["last_voice_channel_id"] = resolved_voice_channel_id
        if resolved_voice_channel_name:
            profile_notify_state["last_voice_channel_name"] = resolved_voice_channel_name
        if not error_message:
            profile_notify_state["last_notified_message_id"] = sanitize_text(message_id)
    save_profile_notify_state()


def get_effective_twitter_poll_seconds():
    with twitter_notify_lock:
        return clamp_poll_seconds(
            twitter_notify_state.get("poll_interval_seconds", TWITTER_NOTIFY_POLL_SECONDS),
            TWITTER_NOTIFY_POLL_SECONDS,
        )


def fetch_json_value_request(url, headers=None, timeout=10, method="GET", body=None):
    req = Request(url, method=method)
    if body is not None:
        req.data = body
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def fetch_json_request(url, headers=None, timeout=10, method="GET", body=None):
    data = fetch_json_value_request(url, headers=headers, timeout=timeout, method=method, body=body)
    if not isinstance(data, dict):
        raise RuntimeError("invalid json response")
    return data


def safe_int(value, default=0):
    try:
        return int(value or 0)
    except Exception:
        return int(default or 0)


def resolve_event_leaderboard_guild_id(raw_guild_id=""):
    guild_text = sanitize_text(raw_guild_id)
    if not guild_text:
        guild_text = sanitize_text(DISCORD_GUILD_ID)
    return guild_text


def fetch_event_points_leaderboard(limit=10, guild_id=""):
    resolved_limit = max(1, min(safe_int(limit, 10), 20))
    resolved_guild_id = resolve_event_leaderboard_guild_id(guild_id)
    if not resolved_guild_id or not resolved_guild_id.isdigit():
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": "guild_id is invalid",
        }

    if not EVENT_LEADERBOARD_DB_PATH:
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": "EVENT_LEADERBOARD_DB_PATH is not set",
        }

    if not os.path.exists(EVENT_LEADERBOARD_DB_PATH):
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": "leaderboard db not found",
        }

    conn = None
    try:
        conn = sqlite3.connect(EVENT_LEADERBOARD_DB_PATH)
        conn.row_factory = sqlite3.Row
        table_info = conn.execute("PRAGMA table_info(player_progress_snapshot)").fetchall()
        available_columns = {str(row[1]) for row in table_info if isinstance(row, (tuple, list)) and len(row) > 1}
        if not available_columns:
            available_columns = {str(row["name"]) for row in table_info if isinstance(row, sqlite3.Row) and "name" in row.keys()}

        select_columns = ["player_name", "steam_id", "event_points"]
        if "player_key" in available_columns:
            select_columns.append("player_key")
        if "entity_id" in available_columns:
            select_columns.append("entity_id")

        rows = conn.execute(
            "SELECT {} FROM player_progress_snapshot WHERE guild_id = ? AND COALESCE(event_points, 0) > 0 ORDER BY COALESCE(event_points, 0) DESC, player_name COLLATE NOCASE ASC LIMIT ?".format(
                ", ".join(select_columns)
            ),
            (int(resolved_guild_id), resolved_limit),
        ).fetchall()

        items = []
        for row in rows:
            row_keys = set(row.keys()) if isinstance(row, sqlite3.Row) else set()
            player_name = sanitize_text(row["player_name"] if "player_name" in row_keys else "")
            if not player_name:
                player_name = "Unknown Player"
            items.append(
                {
                    "player_name": player_name,
                    "steam_id": sanitize_text(row["steam_id"] if "steam_id" in row_keys else ""),
                    "player_key": sanitize_text(row["player_key"] if "player_key" in row_keys else ""),
                    "entity_id": sanitize_text(row["entity_id"] if "entity_id" in row_keys else ""),
                    "event_points": safe_int(row["event_points"] if "event_points" in row_keys else 0, 0),
                }
            )

        return {
            "ok": True,
            "guild_id": resolved_guild_id,
            "count": len(items),
            "items": items,
            "updated_at": now_iso_utc(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": str(exc),
        }
    finally:
        if conn is not None:
            conn.close()


def fetch_bear_party_leaderboard(limit=10, guild_id=""):
    resolved_limit = max(1, min(safe_int(limit, 10), 20))
    resolved_guild_id = resolve_event_leaderboard_guild_id(guild_id)
    if not resolved_guild_id or not resolved_guild_id.isdigit():
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": "guild_id is invalid",
        }

    if not EVENT_LEADERBOARD_DB_PATH or not os.path.exists(EVENT_LEADERBOARD_DB_PATH):
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": "leaderboard db not found",
        }

    conn = None
    try:
        conn = sqlite3.connect(EVENT_LEADERBOARD_DB_PATH)
        conn.row_factory = sqlite3.Row

        # テーブルが存在しない場合は空を返す
        tables = {
            str(r[0])
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "bear_party_points" not in tables:
            return {
                "ok": True,
                "guild_id": resolved_guild_id,
                "count": 0,
                "items": [],
                "updated_at": now_iso_utc(),
            }

        rows = conn.execute(
            """
            SELECT party_name, total_points, last_updated_at
            FROM bear_party_points
            WHERE guild_id = ? AND total_points > 0
            ORDER BY total_points DESC, party_name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (int(resolved_guild_id), resolved_limit),
        ).fetchall()

        items = []
        for rank_idx, row in enumerate(rows):
            items.append(
                {
                    "rank": rank_idx + 1,
                    "party_name": sanitize_text(row["party_name"] if "party_name" in row.keys() else ""),
                    "total_points": safe_int(row["total_points"] if "total_points" in row.keys() else 0, 0),
                    "last_updated_at": sanitize_text(row["last_updated_at"] if "last_updated_at" in row.keys() else ""),
                }
            )

        return {
            "ok": True,
            "guild_id": resolved_guild_id,
            "count": len(items),
            "items": items,
            "updated_at": now_iso_utc(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "guild_id": resolved_guild_id,
            "count": 0,
            "items": [],
            "updated_at": now_iso_utc(),
            "error": str(exc),
        }
    finally:
        if conn is not None:
            conn.close()
    return re.sub(r"[^0-9]", "", str(value or "").strip())


def parse_bool_text(value, default=False):
    text = sanitize_text(value).lower()
    if not text:
        return bool(default)
    if text in ("1", "true", "on", "yes"):
        return True
    if text in ("0", "false", "off", "no"):
        return False
    return bool(default)


def resolve_twitch_chat_owner_discord_user_id(auth_payload=None):
    if TWITCH_CHAT_OWNER_DISCORD_USER_ID:
        return TWITCH_CHAT_OWNER_DISCORD_USER_ID
    source = auth_payload if isinstance(auth_payload, dict) else get_twitch_chat_auth_state()
    return normalize_discord_user_id(source.get("owner_discord_user_id", ""))


def resolve_twitch_chat_owner_twitch_user_id(auth_payload=None):
    if sanitize_text(TWITCH_CHAT_BROADCASTER_USER_ID):
        return sanitize_text(TWITCH_CHAT_BROADCASTER_USER_ID)
    source = auth_payload if isinstance(auth_payload, dict) else get_twitch_chat_auth_state()
    return sanitize_text(source.get("owner_twitch_user_id", ""))


def resolve_twitch_chat_owner_twitch_login(auth_payload=None):
    if sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN):
        return sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN).lower()
    source = auth_payload if isinstance(auth_payload, dict) else get_twitch_chat_auth_state()
    return sanitize_text(source.get("owner_twitch_login", "")).lower()


def can_manage_twitch_chat_auth_user_id(discord_user_id):
    user_id = normalize_discord_user_id(discord_user_id)
    if not user_id:
        return False
    owner_user_id = resolve_twitch_chat_owner_discord_user_id()
    if owner_user_id:
        return user_id == owner_user_id
    return True


def can_manage_twitch_chat_auth_interaction(interaction):
    user_id = normalize_discord_user_id(getattr(getattr(interaction, "user", None), "id", ""))
    if not user_id:
        return False

    owner_user_id = resolve_twitch_chat_owner_discord_user_id()
    if owner_user_id:
        return user_id == owner_user_id
    return is_discord_admin_interaction(interaction)


def validate_twitch_chat_owner_binding(request_discord_user_id, twitch_user_id, twitch_login):
    discord_user_id = normalize_discord_user_id(request_discord_user_id)
    resolved_twitch_user_id = sanitize_text(twitch_user_id)
    resolved_twitch_login = sanitize_text(twitch_login).lower()

    owner_discord_user_id = resolve_twitch_chat_owner_discord_user_id()
    if owner_discord_user_id and discord_user_id and discord_user_id != owner_discord_user_id:
        raise RuntimeError("この Discord ユーザーは Twitch chat 認可を更新できません")

    owner_twitch_user_id = resolve_twitch_chat_owner_twitch_user_id()
    if owner_twitch_user_id and resolved_twitch_user_id and resolved_twitch_user_id != owner_twitch_user_id:
        raise RuntimeError("指定された Twitch アカウント以外では認可できません")

    owner_twitch_login = resolve_twitch_chat_owner_twitch_login()
    if owner_twitch_login and resolved_twitch_login and resolved_twitch_login != owner_twitch_login:
        raise RuntimeError("指定された Twitch login 以外では認可できません")

    return {
        "owner_discord_user_id": owner_discord_user_id or discord_user_id,
        "owner_twitch_user_id": owner_twitch_user_id or resolved_twitch_user_id,
        "owner_twitch_login": owner_twitch_login or resolved_twitch_login,
    }


def load_twitch_chat_auth_state():
    global twitch_chat_auth_state

    payload = {
        "access_token": sanitize_text(TWITCH_CHAT_USER_ACCESS_TOKEN),
        "refresh_token": sanitize_text(TWITCH_CHAT_REFRESH_TOKEN),
        "user_id": "",
        "login": "",
        "owner_discord_user_id": TWITCH_CHAT_OWNER_DISCORD_USER_ID,
        "owner_twitch_user_id": sanitize_text(TWITCH_CHAT_BROADCASTER_USER_ID),
        "owner_twitch_login": sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN).lower(),
        "scopes": [],
        "updated_at": None,
        "source": "env" if TWITCH_CHAT_USER_ACCESS_TOKEN else "file",
    }

    if not payload["access_token"] and os.path.exists(TWITCH_CHAT_AUTH_STATE_FILE):
        try:
            with open(TWITCH_CHAT_AUTH_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                payload.update(
                    {
                        "access_token": sanitize_text(data.get("access_token", "")),
                        "refresh_token": sanitize_text(data.get("refresh_token", "")),
                        "user_id": sanitize_text(data.get("user_id", "")),
                        "login": sanitize_text(data.get("login", "")),
                        "owner_discord_user_id": normalize_discord_user_id(data.get("owner_discord_user_id", "")) or payload.get("owner_discord_user_id", ""),
                        "owner_twitch_user_id": sanitize_text(data.get("owner_twitch_user_id", "")) or payload.get("owner_twitch_user_id", ""),
                        "owner_twitch_login": sanitize_text(data.get("owner_twitch_login", "")).lower() or payload.get("owner_twitch_login", ""),
                        "updated_at": data.get("updated_at"),
                        "source": sanitize_text(data.get("source", "file")) or "file",
                    }
                )
                scopes = data.get("scopes", []) if isinstance(data.get("scopes"), list) else []
                payload["scopes"] = [sanitize_text(item) for item in scopes if sanitize_text(item)]
        except Exception as exc:
            with twitch_chat_lock:
                twitch_chat_state["last_error"] = "twitch chat auth load error: {}".format(exc)

    with twitch_chat_auth_lock:
        twitch_chat_auth_state = dict(payload)

    with twitch_chat_lock:
        twitch_chat_state["auth_source"] = payload.get("source", "file")
        twitch_chat_state["sender_login"] = payload.get("login", "")
        twitch_chat_state["sender_user_id"] = payload.get("user_id", "")
        twitch_chat_state["owner_discord_user_id"] = payload.get("owner_discord_user_id", "")
        twitch_chat_state["owner_twitch_user_id"] = payload.get("owner_twitch_user_id", "")
        twitch_chat_state["owner_twitch_login"] = payload.get("owner_twitch_login", "")
        twitch_chat_state["token_scopes"] = list(payload.get("scopes", []))
        if payload.get("access_token"):
            twitch_chat_state["awaiting_authorization"] = False


def save_twitch_chat_auth_state(payload):
    normalized = {
        "access_token": sanitize_text(payload.get("access_token", "")),
        "refresh_token": sanitize_text(payload.get("refresh_token", "")),
        "user_id": sanitize_text(payload.get("user_id", "")),
        "login": sanitize_text(payload.get("login", "")),
        "owner_discord_user_id": normalize_discord_user_id(payload.get("owner_discord_user_id", "")) or TWITCH_CHAT_OWNER_DISCORD_USER_ID,
        "owner_twitch_user_id": sanitize_text(payload.get("owner_twitch_user_id", "")) or sanitize_text(TWITCH_CHAT_BROADCASTER_USER_ID),
        "owner_twitch_login": sanitize_text(payload.get("owner_twitch_login", "")).lower() or sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN).lower(),
        "updated_at": sanitize_text(payload.get("updated_at", "")) or now_iso_utc(),
        "source": sanitize_text(payload.get("source", "file")) or "file",
    }
    scopes = payload.get("scopes", []) if isinstance(payload.get("scopes"), list) else []
    normalized["scopes"] = [sanitize_text(item) for item in scopes if sanitize_text(item)]

    with twitch_chat_auth_lock:
        twitch_chat_auth_state.update(normalized)

    if TWITCH_CHAT_USER_ACCESS_TOKEN:
        return

    try:
        with open(TWITCH_CHAT_AUTH_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False)
    except Exception as exc:
        with twitch_chat_lock:
            twitch_chat_state["last_error"] = "twitch chat auth save error: {}".format(exc)


def clear_twitch_chat_auth_state():
    global twitch_chat_auth_state

    cleared = {
        "access_token": sanitize_text(TWITCH_CHAT_USER_ACCESS_TOKEN),
        "refresh_token": sanitize_text(TWITCH_CHAT_REFRESH_TOKEN),
        "user_id": "",
        "login": "",
        "owner_discord_user_id": TWITCH_CHAT_OWNER_DISCORD_USER_ID,
        "owner_twitch_user_id": sanitize_text(TWITCH_CHAT_BROADCASTER_USER_ID),
        "owner_twitch_login": sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN).lower(),
        "updated_at": now_iso_utc(),
        "source": "env" if TWITCH_CHAT_USER_ACCESS_TOKEN else "file",
        "scopes": [],
    }

    if not TWITCH_CHAT_USER_ACCESS_TOKEN and os.path.exists(TWITCH_CHAT_AUTH_STATE_FILE):
        try:
            os.remove(TWITCH_CHAT_AUTH_STATE_FILE)
        except Exception as exc:
            with twitch_chat_lock:
                twitch_chat_state["last_error"] = "twitch chat auth clear error: {}".format(exc)

    with twitch_chat_auth_lock:
        twitch_chat_auth_state = dict(cleared)

    with twitch_chat_lock:
        twitch_chat_state["auth_source"] = cleared.get("source", "file")
        twitch_chat_state["sender_login"] = ""
        twitch_chat_state["sender_user_id"] = ""
        twitch_chat_state["owner_discord_user_id"] = cleared.get("owner_discord_user_id", "")
        twitch_chat_state["owner_twitch_user_id"] = cleared.get("owner_twitch_user_id", "")
        twitch_chat_state["owner_twitch_login"] = cleared.get("owner_twitch_login", "")
        twitch_chat_state["token_scopes"] = []
        twitch_chat_state["relay_channel_id"] = TWITCH_CHAT_DISCORD_CHANNEL_ID
        twitch_chat_state["connected"] = False
        twitch_chat_state["running"] = False
        twitch_chat_state["awaiting_authorization"] = TWITCH_CHAT_ENABLED and not bool(cleared.get("access_token"))
        twitch_chat_state["session_id"] = ""
        twitch_chat_state["subscription_broadcasters"] = []
        twitch_chat_state["subscribed_types"] = []

    return dict(cleared)


def get_twitch_chat_auth_state():
    with twitch_chat_auth_lock:
        return dict(twitch_chat_auth_state)


def cleanup_twitch_chat_oauth_states():
    now = time.time()
    with twitch_chat_oauth_lock:
        expired_keys = [key for key, value in twitch_chat_oauth_states.items() if float(value.get("expires_at", 0) or 0) <= now]
        for key in expired_keys:
            twitch_chat_oauth_states.pop(key, None)


def build_twitch_chat_authorize_url(discord_user_id=""):
    if not TWITCH_CLIENT_ID:
        raise RuntimeError("TWITCH_CLIENT_ID is not set")
    if not BOT_PUBLIC_BASE_URL:
        raise RuntimeError("BOT_PUBLIC_BASE_URL is not set")

    cleanup_twitch_chat_oauth_states()
    state_token = secrets.token_urlsafe(24)
    normalized_discord_user_id = normalize_discord_user_id(discord_user_id)
    with twitch_chat_oauth_lock:
        twitch_chat_oauth_states[state_token] = {
            "discord_user_id": normalized_discord_user_id,
            "expires_at": time.time() + 900,
            "created_at": now_iso_utc(),
        }

    redirect_uri = "{}/oauth/twitch/callback".format(BOT_PUBLIC_BASE_URL)
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "user:read:chat user:write:chat",
        "force_verify": "true",
        "state": state_token,
    }
    return "https://id.twitch.tv/oauth2/authorize?{}".format(urlencode(params))


def complete_twitch_chat_oauth(code, state_token):
    cleanup_twitch_chat_oauth_states()
    with twitch_chat_oauth_lock:
        oauth_state = twitch_chat_oauth_states.pop(state_token, None)
    if not oauth_state:
        raise RuntimeError("OAuth state is invalid or expired")
    request_discord_user_id = normalize_discord_user_id(oauth_state.get("discord_user_id", ""))
    if not request_discord_user_id:
        raise RuntimeError("OAuth state に Discord user id がありません")
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set")

    redirect_uri = "{}/oauth/twitch/callback".format(BOT_PUBLIC_BASE_URL)
    token_url = "https://id.twitch.tv/oauth2/token?{}".format(
        urlencode(
            {
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
    )
    token_data = fetch_json_request(
        token_url,
        headers={"User-Agent": "DiscordBotBridge/1.0"},
        timeout=WP_BRIDGE_TIMEOUT,
        method="POST",
    )
    access_token = sanitize_text(token_data.get("access_token", ""))
    refresh_token = sanitize_text(token_data.get("refresh_token", ""))
    if not access_token:
        raise RuntimeError("Twitch OAuth response has no access_token")

    validate_data = fetch_json_request(
        "https://id.twitch.tv/oauth2/validate",
        headers={
            "Authorization": "OAuth {}".format(access_token),
            "User-Agent": "DiscordBotBridge/1.0",
        },
        timeout=WP_BRIDGE_TIMEOUT,
    )
    scopes = validate_data.get("scopes", []) if isinstance(validate_data.get("scopes"), list) else []
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": sanitize_text(validate_data.get("user_id", "")),
        "login": sanitize_text(validate_data.get("login", "")),
        "scopes": [sanitize_text(item) for item in scopes if sanitize_text(item)],
        "updated_at": now_iso_utc(),
        "source": "file",
    }
    owner_binding = validate_twitch_chat_owner_binding(
        request_discord_user_id,
        payload.get("user_id", ""),
        payload.get("login", ""),
    )
    payload["owner_discord_user_id"] = owner_binding.get("owner_discord_user_id", "")
    payload["owner_twitch_user_id"] = owner_binding.get("owner_twitch_user_id", "")
    payload["owner_twitch_login"] = owner_binding.get("owner_twitch_login", "")
    save_twitch_chat_auth_state(payload)
    with twitch_chat_lock:
        twitch_chat_state["last_error"] = ""
        twitch_chat_state["awaiting_authorization"] = False
        twitch_chat_state["auth_source"] = "file"
        twitch_chat_state["sender_login"] = payload.get("login", "")
        twitch_chat_state["sender_user_id"] = payload.get("user_id", "")
        twitch_chat_state["owner_discord_user_id"] = payload.get("owner_discord_user_id", "")
        twitch_chat_state["owner_twitch_user_id"] = payload.get("owner_twitch_user_id", "")
        twitch_chat_state["owner_twitch_login"] = payload.get("owner_twitch_login", "")
        twitch_chat_state["broadcaster_login"] = TWITCH_CHAT_BROADCASTER_LOGIN or payload.get("login", "")
        twitch_chat_state["broadcaster_user_id"] = TWITCH_CHAT_BROADCASTER_USER_ID or payload.get("user_id", "")
        twitch_chat_state["token_scopes"] = list(payload.get("scopes", []))
    return payload


def build_twitch_chat_oauth_result_html(ok, title, message, login="", scopes=None, follow_up_command="/notify mode:twitch"):
    scopes = scopes or []
    scope_text = ", ".join([sanitize_text(item) for item in scopes if sanitize_text(item)]) or "-"
    account_line = ""
    if login:
        account_line = "<p><strong>連携アカウント / Account:</strong> {}</p>".format(login)
    color = "#1f6feb" if ok else "#d1242f"
    return """<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title}</title>
  <style>
    body {{ font-family: sans-serif; background: #f4f6f8; color: #13202b; margin: 0; padding: 32px; }}
    main {{ max-width: 720px; margin: 0 auto; background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 16px 40px rgba(0,0,0,0.08); }}
    h1 {{ margin-top: 0; color: {color}; }}
    p {{ line-height: 1.6; }}
    code {{ background: #eef2f6; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>{message}</p>
    {account_line}
    <p><strong>付与 scope / Granted scopes:</strong> {scope_text}</p>
    <p>このページは閉じて問題ありません。Discord 側で <code>{follow_up_command}</code> を実行すると状態を確認できます。</p>
  </main>
</body>
</html>""".format(
        title=title,
        message=message,
        color=color,
        account_line=account_line,
        scope_text=scope_text,
        follow_up_command=follow_up_command,
    )


def connect_twitch_support_db():
    if not TWITCH_SUPPORT_DB_PATH:
        raise RuntimeError("TWITCH_SUPPORT_DB_PATH is not set")
    directory = os.path.dirname(TWITCH_SUPPORT_DB_PATH)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(TWITCH_SUPPORT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def parse_iso_datetime(value):
    text = sanitize_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def find_twitch_support_oauth_session(state_token):
    normalized_state = sanitize_text(state_token)
    if not normalized_state or not TWITCH_SUPPORT_DB_PATH:
        return None
    try:
        with connect_twitch_support_db() as connection:
            row = connection.execute(
                """
                SELECT
                    state_token,
                    discord_user_id,
                    guild_id,
                    requested_locale,
                    redirect_uri,
                    scopes,
                    status,
                    created_at,
                    expires_at
                FROM twitch_oauth_sessions
                WHERE state_token = ?
                """,
                (normalized_state,),
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return dict(row)


def complete_twitch_support_oauth(code, state_token):
    # helper DB の pending state を正本として検証する。
    oauth_state = find_twitch_support_oauth_session(state_token)
    if not oauth_state:
        raise RuntimeError("OAuth state is invalid or expired")
    if sanitize_text(oauth_state.get("status", "pending")) not in ("pending", "issued"):
        raise RuntimeError("OAuth state is already used")
    expires_at = parse_iso_datetime(oauth_state.get("expires_at", ""))
    if expires_at is not None and expires_at <= datetime.now(expires_at.tzinfo):
        with connect_twitch_support_db() as connection:
            connection.execute(
                "UPDATE twitch_oauth_sessions SET status = 'expired' WHERE state_token = ?",
                (sanitize_text(state_token),),
            )
            connection.commit()
        raise RuntimeError("OAuth state is invalid or expired")
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set")

    redirect_uri = sanitize_text(oauth_state.get("redirect_uri", "")) or "{}/oauth/twitch/callback".format(BOT_PUBLIC_BASE_URL)
    # Twitch 側で code を token に交換する。
    token_url = "https://id.twitch.tv/oauth2/token?{}".format(
        urlencode(
            {
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
    )
    token_data = fetch_json_request(
        token_url,
        headers={"User-Agent": "DiscordBotBridge/1.0"},
        timeout=WP_BRIDGE_TIMEOUT,
        method="POST",
    )
    access_token = sanitize_text(token_data.get("access_token", ""))
    refresh_token = sanitize_text(token_data.get("refresh_token", ""))
    if not access_token:
        raise RuntimeError("Twitch OAuth response has no access_token")

    validate_data = fetch_json_request(
        "https://id.twitch.tv/oauth2/validate",
        headers={
            "Authorization": "OAuth {}".format(access_token),
            "User-Agent": "DiscordBotBridge/1.0",
        },
        timeout=WP_BRIDGE_TIMEOUT,
    )
    broadcaster_user_id = sanitize_text(validate_data.get("user_id", ""))
    broadcaster_login = sanitize_text(validate_data.get("login", ""))
    if not broadcaster_user_id or not broadcaster_login:
        raise RuntimeError("Twitch validate response did not include broadcaster identity")
    scopes = [sanitize_text(item) for item in validate_data.get("scopes", []) if sanitize_text(item)]

    users_data = fetch_json_request(
        "https://api.twitch.tv/helix/users?id={}".format(quote(broadcaster_user_id)),
        headers={
            "Authorization": "Bearer {}".format(access_token),
            "Client-Id": TWITCH_CLIENT_ID,
            "User-Agent": "DiscordBotBridge/1.0",
        },
        timeout=WP_BRIDGE_TIMEOUT,
    )
    user_rows = users_data.get("data", []) if isinstance(users_data, dict) else []
    broadcaster_display_name = broadcaster_login
    if isinstance(user_rows, list) and user_rows:
        first_row = user_rows[0] if isinstance(user_rows[0], dict) else {}
        broadcaster_display_name = sanitize_text(first_row.get("display_name", "")) or broadcaster_login

    guild_id = sanitize_text(oauth_state.get("guild_id", ""))
    discord_user_id = sanitize_text(oauth_state.get("discord_user_id", ""))
    connection_id = "{}:{}".format(guild_id, broadcaster_user_id)
    now_text = now_iso_utc()

    with connect_twitch_support_db() as connection:
        # connection record を upsert して guild 側の正本にする。
        connection.execute(
            """
            INSERT INTO twitch_connections (
                connection_id,
                guild_id,
                discord_user_id,
                broadcaster_user_id,
                broadcaster_login,
                broadcaster_display_name,
                access_token,
                refresh_token,
                scopes,
                connected_at,
                updated_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connection_id) DO UPDATE SET
                discord_user_id = excluded.discord_user_id,
                broadcaster_login = excluded.broadcaster_login,
                broadcaster_display_name = excluded.broadcaster_display_name,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                scopes = excluded.scopes,
                updated_at = excluded.updated_at,
                status = excluded.status
            """,
            (
                connection_id,
                guild_id,
                discord_user_id,
                broadcaster_user_id,
                broadcaster_login,
                broadcaster_display_name,
                access_token,
                refresh_token,
                " ".join(scopes),
                now_text,
                now_text,
                "active",
            ),
        )
        existing_settings = connection.execute(
            "SELECT active_connection_id FROM discord_guild_settings WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
        active_connection_id = ""
        if existing_settings is not None:
            active_connection_id = sanitize_text(existing_settings["active_connection_id"])
        if not active_connection_id:
            active_connection_id = connection_id
        # active 未設定の guild だけ初回接続を自動採用する。
        connection.execute(
            """
            INSERT INTO discord_guild_settings (guild_id, active_connection_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                active_connection_id = CASE
                    WHEN discord_guild_settings.active_connection_id = '' THEN excluded.active_connection_id
                    ELSE discord_guild_settings.active_connection_id
                END,
                updated_at = excluded.updated_at
            """,
            (guild_id, active_connection_id, now_text),
        )
        connection.execute(
            "UPDATE twitch_oauth_sessions SET status = 'completed' WHERE state_token = ?",
            (sanitize_text(state_token),),
        )
        connection.commit()

    return {
        "login": broadcaster_login,
        "display_name": broadcaster_display_name,
        "user_id": broadcaster_user_id,
        "scopes": scopes,
        "guild_id": guild_id,
    }


def get_twitch_localization_map():
    global twitch_localization_cache
    with twitch_localization_lock:
        if twitch_localization_cache is not None:
            return twitch_localization_cache

        path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Joel", "data", "localization.json"))
        if not os.path.exists(path):
            twitch_localization_cache = {}
            return twitch_localization_cache

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            twitch_localization_cache = data if isinstance(data, dict) else {}
        except Exception as exc:
            print("load_twitch_localization error: {}".format(exc))
            twitch_localization_cache = {}
        return twitch_localization_cache


def resolve_twitch_localized_text(raw_value):
    text = sanitize_text(raw_value)
    if not text:
        return ""
    localization = get_twitch_localization_map()
    entry = localization.get(text)
    if not isinstance(entry, dict):
        return text

    for key in ("ja", "en"):
        value = sanitize_text(entry.get(key, ""))
        if value:
            return value
    for value in entry.values():
        resolved = sanitize_text(value)
        if resolved:
            return resolved
    return text


def _resolve_twitch_action_properties(action_name, raw_actions, cache, visiting=None):
    if action_name in cache:
        return dict(cache[action_name])
    if visiting is None:
        visiting = set()
    if action_name in visiting:
        return {}

    visiting.add(action_name)
    raw = raw_actions.get(action_name, {}) if isinstance(raw_actions.get(action_name, {}), dict) else {}
    props = {}
    parent_name = sanitize_text(raw.get("extends", ""))
    if parent_name and parent_name in raw_actions:
        props.update(_resolve_twitch_action_properties(parent_name, raw_actions, cache, visiting))
    props.update(raw.get("properties", {}) if isinstance(raw.get("properties"), dict) else {})
    props["_extends"] = parent_name
    props["_name"] = action_name
    cache[action_name] = dict(props)
    visiting.discard(action_name)
    return dict(props)


def build_twitch_action_catalog(xml_path=None):
    source_path = sanitize_text(xml_path or TWITCH_CHAT_XML_PATH)
    if not source_path:
        raise RuntimeError("TWITCH_CHAT_XML_PATH is not set")
    if not os.path.exists(source_path):
        raise RuntimeError("twitch.xml was not found: {}".format(source_path))

    tree = ET.parse(source_path)
    root = tree.getroot()

    categories = []
    category_index = {}
    for index, node in enumerate(root.findall("category")):
        name = sanitize_text(node.get("name", ""))
        if not name:
            continue
        label = resolve_twitch_localized_text(node.get("display_name", "")) or name
        meta = {
            "name": name,
            "label": label,
            "icon": sanitize_text(node.get("icon", "")),
            "order": index,
        }
        categories.append(meta)
        category_index[name] = meta

    if "Other" not in category_index:
        category_index["Other"] = {
            "name": "Other",
            "label": resolve_twitch_localized_text("xuiShapesOther") or "Other",
            "icon": "",
            "order": len(categories),
        }
        categories.append(dict(category_index["Other"]))

    command_permissions = {}
    for node in root.findall("command_permission"):
        command = sanitize_text(node.get("command", ""))
        permission = sanitize_text(node.get("permission", ""))
        if command and permission:
            command_permissions[command] = permission

    raw_actions = {}
    for node in root.findall("action"):
        name = sanitize_text(node.get("name", ""))
        if not name:
            continue
        properties = {}
        for prop in node.findall("property"):
            prop_name = sanitize_text(prop.get("name", ""))
            if not prop_name:
                continue
            properties[prop_name] = prop.get("value", "")
        raw_actions[name] = {
            "extends": sanitize_text(node.get("extends", "")),
            "properties": properties,
        }

    resolved_cache = {}
    actions = []
    visible_count = 0
    compatible_count = 0

    for action_name in sorted(raw_actions.keys()):
        props = _resolve_twitch_action_properties(action_name, raw_actions, resolved_cache)
        command = sanitize_text(props.get("command", ""))
        command_display = resolve_twitch_localized_text(props.get("command_key", "")) or command
        title = resolve_twitch_localized_text(props.get("title_key", "")) or sanitize_text(props.get("title", "")) or action_name
        description = resolve_twitch_localized_text(props.get("description_key", "")) or sanitize_text(props.get("description", ""))
        category_names = parse_csv_list(props.get("category", "")) or ["Other"]
        category_labels = []
        for category_name in category_names:
            meta = category_index.get(category_name) or category_index.get("Other")
            category_labels.append(meta.get("label", category_name))
        primary_category = category_names[0] if category_names else "Other"
        primary_category_meta = category_index.get(primary_category) or category_index.get("Other")
        point_type = sanitize_text(props.get("point_type", "PP")) or "PP"
        enabled = parse_bool_text(props.get("enabled", "true"), default=True)
        visible = parse_bool_text(props.get("show_in_action_list", "true"), default=True) and enabled
        permission = command_permissions.get(command, sanitize_text(props.get("only_usable_type", "")) or "Everyone")
        chat_compatible = bool(command) and point_type.upper() != "BITS"
        if visible:
            visible_count += 1
        if visible and chat_compatible:
            compatible_count += 1

        actions.append(
            {
                "name": action_name,
                "title": title,
                "description": description,
                "command": command,
                "command_display": command_display,
                "category": primary_category,
                "category_label": primary_category_meta.get("label", primary_category),
                "category_labels": category_labels,
                "category_order": int(primary_category_meta.get("order", 999) or 999),
                "point_type": point_type,
                "default_cost": safe_int(props.get("default_cost", 0)),
                "start_gamestage": safe_int(props.get("start_gamestage", 0)),
                "cooldown": safe_int(props.get("cooldown", 0)),
                "enabled": enabled,
                "visible": visible,
                "chat_compatible": chat_compatible,
                "permission": permission,
                "only_usable_type": sanitize_text(props.get("only_usable_type", "")) or permission,
                "presets": parse_csv_list(props.get("presets", "")),
                "special_requirements": parse_csv_list(props.get("special_requirement", "")),
                "only_usable_by": parse_csv_list(props.get("only_usable_by", "")),
                "cooldown_blocked": parse_bool_text(props.get("cooldown_blocked", "false"), default=False),
                "waiting_blocked": parse_bool_text(props.get("waiting_blocked", "false"), default=False),
                "single_day": parse_bool_text(props.get("single_day", "false"), default=False),
                "special_only": parse_bool_text(props.get("special_only", "false"), default=False),
                "streamer_only": parse_bool_text(props.get("streamer_only", "false"), default=False),
                "point_type_label": point_type,
                "extends": sanitize_text(props.get("_extends", "")),
            }
        )

    actions.sort(key=lambda item: (item.get("category_order", 999), item.get("start_gamestage", 0), item.get("title", "").lower(), item.get("name", "")))

    category_counts = {}
    for item in actions:
        if not item.get("visible"):
            continue
        key = item.get("category", "Other")
        category_counts[key] = category_counts.get(key, 0) + 1

    category_rows = []
    for item in categories:
        row = dict(item)
        row["visible_count"] = int(category_counts.get(item.get("name"), 0) or 0)
        category_rows.append(row)

    return {
        "ok": True,
        "source_path": source_path,
        "loaded_at": now_iso_utc(),
        "categories": category_rows,
        "actions": actions,
        "total_actions": len(actions),
        "visible_actions": visible_count,
        "chat_compatible_actions": compatible_count,
    }


def get_twitch_action_catalog(force_reload=False):
    source_path = sanitize_text(TWITCH_CHAT_XML_PATH)
    try:
        mtime = os.path.getmtime(source_path)
    except Exception:
        mtime = 0

    with twitch_action_catalog_lock:
        cached_catalog = twitch_action_catalog_cache.get("catalog")
        if (
            (not force_reload)
            and cached_catalog
            and twitch_action_catalog_cache.get("path") == source_path
            and float(twitch_action_catalog_cache.get("mtime", 0) or 0) == float(mtime)
        ):
            return dict(cached_catalog)

    try:
        catalog = build_twitch_action_catalog(source_path)
        with twitch_action_catalog_lock:
            twitch_action_catalog_cache["path"] = source_path
            twitch_action_catalog_cache["mtime"] = mtime
            twitch_action_catalog_cache["loaded_at"] = catalog.get("loaded_at")
            twitch_action_catalog_cache["catalog"] = dict(catalog)
            twitch_action_catalog_cache["error"] = ""
        return catalog
    except Exception as exc:
        error_text = sanitize_text(str(exc))
        with twitch_action_catalog_lock:
            twitch_action_catalog_cache["path"] = source_path
            twitch_action_catalog_cache["mtime"] = mtime
            twitch_action_catalog_cache["catalog"] = None
            twitch_action_catalog_cache["error"] = error_text
        return {
            "ok": False,
            "source_path": source_path,
            "loaded_at": now_iso_utc(),
            "categories": [],
            "actions": [],
            "total_actions": 0,
            "visible_actions": 0,
            "chat_compatible_actions": 0,
            "error": error_text,
        }


def find_twitch_action_entry(catalog, action_name):
    target_name = sanitize_text(action_name)
    if not target_name:
        return None
    for item in catalog.get("actions", []):
        if not isinstance(item, dict):
            continue
        if sanitize_text(item.get("name", "")) == target_name:
            return item
    return None


def filter_twitch_action_entries(catalog, category_name=""):
    selected_category = sanitize_text(category_name)
    filtered_actions = []
    for item in catalog.get("actions", []):
        if not isinstance(item, dict) or not item.get("visible"):
            continue
        if selected_category and sanitize_text(item.get("category", "")) != selected_category:
            continue
        filtered_actions.append(item)
    return filtered_actions


def get_twitch_action_page_slice(filtered_actions, page=1, page_size=12):
    normalized_page_size = max(1, safe_int(page_size, 12))
    total_items = len(filtered_actions or [])
    total_pages = max(1, (total_items + normalized_page_size - 1) // normalized_page_size)
    current_page = min(max(1, safe_int(page, 1)), total_pages)
    start_index = (current_page - 1) * normalized_page_size
    end_index = start_index + normalized_page_size
    return {
        "page": current_page,
        "page_size": normalized_page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": list(filtered_actions[start_index:end_index]),
        "start_index": start_index,
        "end_index": min(end_index, total_items),
    }


def get_twitch_action_sender_context(runtime_state=None, auth_state=None):
    state_payload = dict(runtime_state) if isinstance(runtime_state, dict) else {}
    auth_payload = dict(auth_state) if isinstance(auth_state, dict) else get_twitch_chat_auth_state()

    sender_login = sanitize_text(
        state_payload.get("sender_login", "")
        or auth_payload.get("login", "")
        or auth_payload.get("owner_twitch_login", "")
    ).lower()
    sender_user_id = sanitize_text(
        state_payload.get("sender_user_id", "")
        or auth_payload.get("user_id", "")
        or auth_payload.get("owner_twitch_user_id", "")
    )
    broadcaster_login = sanitize_text(
        state_payload.get("broadcaster_login", "")
        or resolve_twitch_chat_owner_twitch_login(auth_payload)
        or sender_login
    ).lower()
    broadcaster_user_id = sanitize_text(
        state_payload.get("broadcaster_user_id", "")
        or resolve_twitch_chat_owner_twitch_user_id(auth_payload)
        or sender_user_id
    )

    return {
        "sender_login": sender_login,
        "sender_user_id": sender_user_id,
        "broadcaster_login": broadcaster_login,
        "broadcaster_user_id": broadcaster_user_id,
        "sender_is_broadcaster": bool(sender_login and broadcaster_login and sender_login == broadcaster_login),
    }


def normalize_twitch_action_permission(value):
    raw_value = sanitize_text(value)
    lowered = raw_value.lower()
    mapping = {
        "": "Everyone",
        "everyone": "Everyone",
        "broadcaster": "Broadcaster",
        "mods": "Mods",
        "modsandbroadcaster": "Mods",
        "mods_and_broadcaster": "Mods",
        "vips": "VIPs",
        "vip": "VIPs",
        "subs": "Subs",
        "subscribers": "Subs",
        "subscriber": "Subs",
        "name": "Name",
    }
    return mapping.get(lowered, raw_value or "Everyone")


def get_twitch_action_special_requirement_label(value):
    requirement = sanitize_text(value)
    labels = {
        "HasSpawnedEntities": "出現中エンティティあり / spawned entities present",
        "NoSpawnedEntities": "出現中エンティティなし / no spawned entities",
        "Bloodmoon": "Bloodmoon 中",
        "NotBloodmoon": "Bloodmoon 以外",
        "NotBloodmoonDay": "Bloodmoon 日以外",
        "EarlyDay": "早朝のみ / early day",
        "Daytime": "昼のみ / daytime",
        "Night": "夜のみ / night",
        "IsCooldown": "クールダウン中",
        "InLandClaim": "Land Claim 内",
        "NotInLandClaim": "Land Claim 外",
        "NotSafe": "安全地帯外 / not safe",
        "Safe": "安全地帯のみ / safe",
        "NoFullProgression": "最大進行前 / no full progression",
        "NotOnVehicle": "乗り物外 / not on vehicle",
        "NotInTrader": "Trader 外",
        "Encumbrance": "Encumbrance 必須",
        "WeatherGracePeriod": "天候猶予中 / weather grace period",
        "NotOnQuest": "Quest 外",
        "OnQuest": "Quest 中",
        "None": "",
    }
    return labels.get(requirement, requirement)


def evaluate_twitch_action_execution(item, sender_context=None):
    action_item = item if isinstance(item, dict) else {}
    context = sender_context if isinstance(sender_context, dict) else get_twitch_action_sender_context()

    unsupported_reasons = []
    pending_reasons = []

    command = sanitize_text(action_item.get("command", ""))
    permission = normalize_twitch_action_permission(action_item.get("permission", "") or action_item.get("only_usable_type", ""))
    point_type = sanitize_text(action_item.get("point_type", "PP")).upper() or "PP"
    sender_login = sanitize_text(context.get("sender_login", "")).lower()
    sender_is_broadcaster = bool(context.get("sender_is_broadcaster"))
    allowed_names = [sanitize_text(entry).lower() for entry in action_item.get("only_usable_by", []) if sanitize_text(entry)]

    if not bool(action_item.get("enabled", False)):
        unsupported_reasons.append("無効化された action です。")
    if not command:
        unsupported_reasons.append("Twitch chat command が未定義です。")
    if point_type == "BITS":
        unsupported_reasons.append("Bits / Extension 専用 action のため Discord 送信に未対応です。")
    elif point_type not in ("PP", "SP"):
        unsupported_reasons.append("未対応の point_type です: {}".format(point_type))

    if permission == "Broadcaster":
        if not sender_is_broadcaster:
            unsupported_reasons.append("Broadcaster 限定 action です。")
    elif permission == "Name":
        if not sender_login:
            unsupported_reasons.append("Twitch owner login が未確定のため Name 制限を判定できません。")
        elif not allowed_names:
            unsupported_reasons.append("Name 制限ですが only_usable_by が空です。")
        elif sender_login not in allowed_names:
            unsupported_reasons.append("現在の Twitch login は only_usable_by に含まれていません。")
    elif permission in ("Mods", "VIPs", "Subs"):
        unsupported_reasons.append("{} 限定 action は現在の OAuth scope では事前確認できないため未対応です。".format(permission))
    elif permission != "Everyone":
        unsupported_reasons.append("未対応の only_usable_type です: {}".format(permission))

    start_gamestage = safe_int(action_item.get("start_gamestage", 0))
    if start_gamestage > 0:
        pending_reasons.append("開始 Gamestage {} 以上が必要です。".format(start_gamestage))

    presets = [sanitize_text(entry) for entry in action_item.get("presets", []) if sanitize_text(entry)]
    if presets:
        pending_reasons.append("Preset 条件があります: {}".format(", ".join(presets)))

    special_requirements = []
    for entry in action_item.get("special_requirements", []) if isinstance(action_item.get("special_requirements", []), list) else []:
        label = get_twitch_action_special_requirement_label(entry)
        if label:
            special_requirements.append(label)
    if special_requirements:
        pending_reasons.append("ゲーム側条件: {}".format(", ".join(special_requirements)))

    if bool(action_item.get("cooldown_blocked")):
        pending_reasons.append("クールダウン中は実行できません。")
    if bool(action_item.get("waiting_blocked")):
        pending_reasons.append("待機中は実行できません。")
    if bool(action_item.get("single_day")):
        pending_reasons.append("1 日 1 回制限があります。")
    if bool(action_item.get("special_only")):
        pending_reasons.append("Special points 限定です。")
    if bool(action_item.get("streamer_only")):
        pending_reasons.append("配信者のみ対象です。")

    status = "executable"
    if unsupported_reasons:
        status = "unsupported"
    elif pending_reasons:
        status = "pending"

    labels = {
        "executable": "実行可能 / Ready",
        "pending": "ゲーム側条件待ち / Waiting",
        "unsupported": "非対応 / Unsupported",
    }
    short_labels = {
        "executable": "実行可能",
        "pending": "条件待ち",
        "unsupported": "非対応",
    }
    if status == "unsupported":
        summary = unsupported_reasons[0]
    elif status == "pending":
        summary = pending_reasons[0]
    else:
        summary = "Discord から送信可能です。"

    return {
        "status": status,
        "status_label": labels.get(status, status),
        "status_short": short_labels.get(status, status),
        "summary": summary,
        "unsupported_reasons": unsupported_reasons,
        "pending_reasons": pending_reasons,
        "can_execute": status == "executable",
        "permission": permission,
        "sender_login": sender_login,
        "sender_is_broadcaster": sender_is_broadcaster,
    }


async def gateway_send_channel_message(channel_id, content, delete_after=None):
    if discord is None:
        raise RuntimeError("discord.py is not installed")

    runtime = ensure_gateway_runtime()
    if not runtime.get("runtime_ok"):
        raise RuntimeError("Discord gateway not connected")

    channel_text = sanitize_text(channel_id)
    if not channel_text or not channel_text.isdigit():
        raise RuntimeError("Discord channel_id is invalid")

    async def _send():
        channel = _discord_client.get_channel(int(channel_text))
        if channel is None:
            channel = await _discord_client.fetch_channel(int(channel_text))

        kwargs = {
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if delete_after is not None:
            kwargs["delete_after"] = float(delete_after)
        return await channel.send(content, **kwargs)

    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except Exception:
        current_loop = None

    if _discord_loop is not None and current_loop is not _discord_loop:
        future = asyncio.run_coroutine_threadsafe(_send(), _discord_loop)
        return await asyncio.wrap_future(future)

    return await _send()


async def gateway_delete_channel_messages(channel_id, message_ids, reason=""):
    if discord is None:
        raise RuntimeError("discord.py is not installed")

    runtime = ensure_gateway_runtime()
    if not runtime.get("runtime_ok"):
        raise RuntimeError("Discord gateway not connected")

    channel_text = sanitize_text(channel_id)
    if not channel_text or not channel_text.isdigit():
        raise RuntimeError("Discord channel_id is invalid")

    normalized_message_ids = []
    seen_message_ids = set()
    for raw_message_id in message_ids or []:
        message_text = sanitize_text(raw_message_id)
        if not message_text or not message_text.isdigit() or message_text in seen_message_ids:
            continue
        normalized_message_ids.append(message_text)
        seen_message_ids.add(message_text)

    if not normalized_message_ids:
        return {
            "requested": 0,
            "deleted": 0,
            "missing": 0,
            "failed": 0,
            "deleted_ids": [],
            "missing_ids": [],
            "failed_ids": [],
            "error": "",
        }

    async def _delete():
        channel = _discord_client.get_channel(int(channel_text))
        if channel is None:
            channel = await _discord_client.fetch_channel(int(channel_text))

        deleted_ids = []
        missing_ids = []
        failed_ids = []
        last_error = ""
        audit_reason = truncate_text(sanitize_text(reason), 480)

        # partial message を使い、既に消えているものは NotFound として同期だけ進める。
        for message_text in normalized_message_ids:
            try:
                if hasattr(channel, "get_partial_message"):
                    partial_message = channel.get_partial_message(int(message_text))
                    await partial_message.delete(reason=audit_reason or None)
                else:
                    full_message = await channel.fetch_message(int(message_text))
                    await full_message.delete(reason=audit_reason or None)
                deleted_ids.append(message_text)
            except discord.NotFound:
                missing_ids.append(message_text)
            except discord.Forbidden as exc:
                failed_ids.append(message_text)
                last_error = sanitize_text(str(exc)) or "discord forbidden"
            except discord.HTTPException as exc:
                failed_ids.append(message_text)
                last_error = sanitize_text(str(exc)) or "discord http exception"

        return {
            "requested": len(normalized_message_ids),
            "deleted": len(deleted_ids),
            "missing": len(missing_ids),
            "failed": len(failed_ids),
            "deleted_ids": deleted_ids,
            "missing_ids": missing_ids,
            "failed_ids": failed_ids,
            "error": last_error,
        }

    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except Exception:
        current_loop = None

    if _discord_loop is not None and current_loop is not _discord_loop:
        future = asyncio.run_coroutine_threadsafe(_delete(), _discord_loop)
        return await asyncio.wrap_future(future)

    return await _delete()


def get_twitch_chat_subscription_logins():
    logins = []
    seen = set()
    for raw_login in parse_csv_list(TWITCH_CHAT_BROADCASTER_LOGINS):
        normalized = sanitize_text(raw_login).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        logins.append(normalized)

    # テスト中は WordPress 側の Twitch watch item に載る streamer も購読対象へ含める。
    # これにより現在 live の creator thread 群で chat relay を確認しやすくする。
    try:
        items, _source = get_twitch_watcher().fetch_latest_items(limit=100)
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = sanitize_text(item.get("user_login", "")).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            logins.append(normalized)
    except Exception:
        pass

    return logins


def get_twitch_chat_allowed_game_names():
    allowed = []
    seen = set()
    for raw_name in parse_csv_list(TWITCH_CHAT_ALLOWED_GAME_NAMES):
        normalized = sanitize_text(raw_name).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        allowed.append(normalized)
    return allowed


def fetch_twitch_chat_stream_context_index(force_refresh=False):
    now_ts = time.time()
    with twitch_chat_stream_context_lock:
        if (
            (not force_refresh)
            and float(twitch_chat_stream_context_cache.get("expires_at", 0) or 0) > now_ts
            and isinstance(twitch_chat_stream_context_cache.get("by_login"), dict)
        ):
            return dict(twitch_chat_stream_context_cache.get("by_login", {}))

    by_login = {}
    source = ""
    last_error = ""
    try:
        watcher = get_twitch_watcher()
        items, source = watcher.fetch_latest_items(limit=100)
        for item in items:
            if not isinstance(item, dict):
                continue
            user_login = sanitize_text(item.get("user_login", "")).lower()
            if not user_login:
                continue
            by_login[user_login] = dict(item)

        missing_game_logins = []
        for user_login, item in by_login.items():
            if not isinstance(item, dict):
                continue
            if sanitize_text(item.get("game_name", "")):
                continue
            missing_game_logins.append(user_login)

        if missing_game_logins:
            for stream in watcher.fetch_live_streams(missing_game_logins):
                if not isinstance(stream, dict):
                    continue
                user_login = sanitize_text(stream.get("user_login", "")).lower()
                if not user_login:
                    continue
                current = dict(by_login.get(user_login, {})) if isinstance(by_login.get(user_login), dict) else {}
                current["user_login"] = user_login
                current["user_name"] = sanitize_text(stream.get("user_name", "")) or current.get("user_name", "")
                current["game_name"] = sanitize_text(stream.get("game_name", "")) or current.get("game_name", "")
                current["broadcast_state"] = sanitize_text(stream.get("type", "")).lower() or current.get("broadcast_state", "")
                if current.get("broadcast_state") == "live":
                    current["broadcast_state"] = "live"
                by_login[user_login] = current
    except Exception as exc:
        last_error = sanitize_text(str(exc))

    with twitch_chat_stream_context_lock:
        twitch_chat_stream_context_cache["expires_at"] = now_ts + TWITCH_CHAT_STREAM_CONTEXT_CACHE_SECONDS
        twitch_chat_stream_context_cache["source"] = source
        twitch_chat_stream_context_cache["last_error"] = last_error
        twitch_chat_stream_context_cache["by_login"] = dict(by_login)
    return dict(by_login)


def resolve_twitch_chat_stream_context(event, force_refresh=False):
    event_payload = event if isinstance(event, dict) else {}
    broadcaster_login = sanitize_text(event_payload.get("broadcaster_user_login", "")).lower()
    if not broadcaster_login:
        return {}

    by_login = fetch_twitch_chat_stream_context_index(force_refresh=force_refresh)
    context = by_login.get(broadcaster_login)
    if isinstance(context, dict):
        return dict(context)

    return {
        "user_login": broadcaster_login,
        "user_name": sanitize_text(event_payload.get("broadcaster_user_name", "")) or broadcaster_login,
        "member_display_name": "",
        "game_name": "",
        "broadcast_state": "live",
    }


def resolve_twitch_chat_thread_name(event, stream_context=None):
    event_payload = event if isinstance(event, dict) else {}
    context = stream_context if isinstance(stream_context, dict) else {}
    candidates = []
    seen = set()
    for raw_value in (
        context.get("member_display_name", ""),
        context.get("user_name", ""),
        event_payload.get("broadcaster_user_name", ""),
        context.get("user_login", ""),
        event_payload.get("broadcaster_user_login", ""),
    ):
        text = sanitize_text(raw_value)
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(text)
    return normalize_nexus_thread_name(candidates[0] if candidates else "Twitch", "Twitch")


def is_twitch_chat_game_allowed(stream_context=None):
    allowed_games = get_twitch_chat_allowed_game_names()
    if not allowed_games:
        return True
    context = stream_context if isinstance(stream_context, dict) else {}
    game_name = sanitize_text(context.get("game_name", "")).lower()
    if not game_name:
        return False
    return game_name in set(allowed_games)


def build_twitch_chat_thread_starter_payload(thread_name, stream_context=None):
    context = stream_context if isinstance(stream_context, dict) else {}
    lines = [
        "このスレッドへ Twitch chat relay を投稿します。",
        "配信通知と同じストリーマー単位でメッセージを追跡します。",
    ]
    game_name = sanitize_text(context.get("game_name", ""))
    if game_name:
        lines.append("現在のゲーム: {}".format(game_name))
    return {
        "content": truncate_text("\n".join(lines), 1900),
    }


async def post_twitch_chat_event_to_discord(event_type, event, content, delete_after=None):
    event_payload = event if isinstance(event, dict) else {}
    content_text = truncate_text(content, 1900)
    if not content_text:
        return None

    stream_context = resolve_twitch_chat_stream_context(event_payload)
    if not is_twitch_chat_game_allowed(stream_context):
        with twitch_chat_lock:
            twitch_chat_state["last_error"] = "twitch chat relay skipped by game filter"
        return None

    if TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS and DISCORD_TWITCH_MEDIA_CHANNEL_ID:
        thread_name = resolve_twitch_chat_thread_name(event_payload, stream_context=stream_context)
        thread_result = ensure_nexus_media_thread(
            DISCORD_TWITCH_MEDIA_CHANNEL_ID,
            thread_name,
            build_twitch_chat_thread_starter_payload(thread_name, stream_context=stream_context),
        )
        thread_id = sanitize_text(thread_result.get("thread_id", ""))
        if not thread_id:
            raise RuntimeError("Twitch creator thread could not be resolved")
        message = await gateway_send_channel_message(thread_id, content_text, delete_after=delete_after)
        with twitch_chat_lock:
            twitch_chat_state["relay_channel_id"] = thread_id
        return message

    return await gateway_send_channel_message(TWITCH_CHAT_DISCORD_CHANNEL_ID, content_text, delete_after=delete_after)


async def post_twitch_chat_message_to_discord(content, delete_after=None):
    return await gateway_send_channel_message(TWITCH_CHAT_DISCORD_CHANNEL_ID, content, delete_after=delete_after)


async def delete_twitch_chat_messages_from_discord(records, reason=""):
    reason_text = sanitize_text(reason) or "eventsub"
    audit_reason = "Twitch moderation sync: {}".format(reason_text)
    grouped_message_ids = {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        channel_id = sanitize_text(record.get("discord_channel_id", "")) or TWITCH_CHAT_DISCORD_CHANNEL_ID
        message_id = sanitize_text(record.get("discord_message_id", ""))
        if not channel_id or not channel_id.isdigit() or not message_id or not message_id.isdigit():
            continue
        grouped_message_ids.setdefault(channel_id, []).append(message_id)

    deleted_ids = []
    missing_ids = []
    failed_ids = []
    last_error = ""
    requested = 0

    for channel_id, message_ids in grouped_message_ids.items():
        requested += len(message_ids)
        result = await gateway_delete_channel_messages(channel_id, message_ids, reason=audit_reason)
        deleted_ids.extend(result.get("deleted_ids", []))
        missing_ids.extend(result.get("missing_ids", []))
        failed_ids.extend(result.get("failed_ids", []))
        if result.get("error"):
            last_error = sanitize_text(result.get("error", ""))

    return {
        "requested": requested,
        "deleted": len(deleted_ids),
        "missing": len(missing_ids),
        "failed": len(failed_ids),
        "deleted_ids": deleted_ids,
        "missing_ids": missing_ids,
        "failed_ids": failed_ids,
        "error": last_error,
    }


def normalize_nexus_thread_name(value, fallback):
    text = sanitize_text(value)
    if not text or text == "-":
        text = fallback
    return truncate_text(text, 90)


def normalize_nexus_tag_name(value, fallback="その他"):
    text = sanitize_text(value)
    if not text or text == "-":
        text = fallback
    return truncate_text(text, 20)


def normalize_nexus_tag_names(values, fallback="", limit=5):
    normalized = []
    max_names = max(1, min(int(limit or 5), 5))
    for raw_value in values or []:
        name = normalize_nexus_tag_name(raw_value, fallback=fallback)
        if not name or name in normalized:
            continue
        normalized.append(name)
        if len(normalized) >= max_names:
            break
    return normalized


def get_nexus_embed_field_value(embed_payload, field_name):
    if not isinstance(embed_payload, dict):
        return ""
    for field in embed_payload.get("fields", []):
        if not isinstance(field, dict):
            continue
        name = sanitize_text(field.get("name", ""))
        if name.lower() == sanitize_text(field_name).lower():
            return sanitize_text(field.get("value", ""))
    return ""


def get_nexus_embed_tag_names(embed_payload, limit=4):
    max_tags = max(1, min(int(limit or 4), 4))
    resolved = []

    def append_tag_candidates(raw_values):
        for tag_name in normalize_nexus_tag_names(raw_values, fallback="", limit=max_tags):
            if tag_name in resolved:
                continue
            resolved.append(tag_name)
            if len(resolved) >= max_tags:
                break

    tags_value = sanitize_text(get_nexus_embed_field_value(embed_payload, "Tags"))
    if tags_value:
        for raw_name in re.split(r"\s*/\s*", tags_value):
            tag_name = sanitize_text(raw_name)
            if not tag_name or tag_name == "-":
                continue
            if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", tag_name):
                append_tag_candidates([tag_name])
            else:
                append_tag_candidates(infer_nexus_temporary_tags(tag_name, limit=2))
            if len(resolved) >= max_tags:
                return resolved[:max_tags]

    raw_category = sanitize_text(get_nexus_embed_field_value(embed_payload, "Category"))
    if raw_category and raw_category != "-":
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", raw_category):
            append_tag_candidates([raw_category])
        else:
            append_tag_candidates(infer_nexus_temporary_tags(raw_category, limit=1))
        if len(resolved) >= max_tags:
            return resolved[:max_tags]

    append_tag_candidates(
        infer_nexus_temporary_tags(
            raw_category,
            sanitize_text(embed_payload.get("title", "")),
            sanitize_text(embed_payload.get("description", "")),
            sanitize_text(embed_payload.get("url", "")),
            limit=max_tags,
        )
    )

    if not resolved:
        append_tag_candidates(["その他"])

    return resolved[:max_tags]


def get_nexus_embed_category_name(embed_payload):
    tag_names = get_nexus_embed_tag_names(embed_payload, limit=1)
    if tag_names:
        return normalize_nexus_thread_name(tag_names[0], "その他")
    return "その他"


def get_nexus_embed_creator_name(embed_payload):
    creator_name = sanitize_text(get_nexus_embed_field_value(embed_payload, "Author"))
    if not creator_name or creator_name == "-":
        creator_name = sanitize_text(get_nexus_embed_field_value(embed_payload, "Creator"))
    if not creator_name or creator_name == "-":
        creator_name = get_nexus_embed_category_name(embed_payload)
    return normalize_nexus_thread_name(creator_name, "作者不明")


def build_nexus_jump_url(channel_id, message_id=None):
    if not DISCORD_GUILD_ID:
        return ""
    channel_text = sanitize_text(channel_id)
    message_text = sanitize_text(message_id or channel_id)
    if not channel_text.isdigit() or not message_text.isdigit():
        return ""
    return "https://discord.com/channels/{}/{}/{}".format(DISCORD_GUILD_ID, channel_text, message_text)


def build_nexus_open_components(url):
    link = sanitize_text(url)
    if not link:
        return []
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "Nexus Mods で開く / Open",
                    "url": link,
                }
            ],
        }
    ]


def extract_discord_message_update_payload(payload):
    if not isinstance(payload, dict):
        return {}
    result = {}
    if "content" in payload:
        result["content"] = payload.get("content")
    if "embeds" in payload:
        result["embeds"] = payload.get("embeds")
    if "components" in payload:
        result["components"] = payload.get("components")
    return result


def update_discord_thread_starter_message(thread_id, payload):
    return update_discord_thread_message(thread_id, thread_id, payload)


def update_discord_thread_message(thread_id, message_id, payload):
    thread_text = sanitize_text(thread_id)
    message_text = sanitize_text(message_id)
    if not thread_text or not thread_text.isdigit() or not message_text or not message_text.isdigit():
        return {}
    update_payload = extract_discord_message_update_payload(payload)
    if not update_payload:
        return {}
    return discord_patch_json(
        "/channels/{}/messages/{}".format(thread_text, message_text),
        update_payload,
    )


class ProfileCardThreadRecreationRequired(RuntimeError):
    pass


def create_discord_thread_message(thread_id, payload):
    thread_text = sanitize_text(thread_id)
    if not thread_text or not thread_text.isdigit():
        return {}
    create_payload = extract_discord_message_update_payload(payload)
    if not create_payload:
        return {}
    return discord_post_json("/channels/{}/messages".format(thread_text), create_payload)


def is_discord_old_message_edit_limit_error(exc):
    error_text = sanitize_text(str(exc))
    return "30046" in error_text or "Maximum number of edits to messages older than 1 hour reached" in error_text


def sync_profile_card_message(thread_id, payload, existing_message_id=""):
    thread_text = sanitize_text(thread_id)
    if not thread_text or not thread_text.isdigit():
        raise RuntimeError("Discord profile thread_id is invalid")

    existing_message_text = sanitize_text(existing_message_id)
    if existing_message_text.isdigit() and existing_message_text != thread_text:
        raise ProfileCardThreadRecreationRequired("profile preview is no longer backed by the forum starter message")

    try:
        update_discord_thread_message(thread_text, thread_text, payload)
        return thread_text
    except Exception as exc:
        error_text = sanitize_text(str(exc))
        if is_discord_old_message_edit_limit_error(exc):
            raise ProfileCardThreadRecreationRequired(error_text)
        if "404" in error_text or "10008" in error_text:
            raise ProfileCardThreadRecreationRequired(error_text)
        raise


def extract_discord_component_dicts(components):
    rows = []
    for component in components or []:
        row = component
        if not isinstance(row, dict) and hasattr(component, "to_dict"):
            try:
                row = component.to_dict()
            except Exception:
                row = None
        if isinstance(row, dict):
            rows.append(row)
    return rows


def extract_link_button_components(components):
    rows = []
    for row in extract_discord_component_dicts(components):
        if int(row.get("type", 0) or 0) != 1:
            continue
        buttons = []
        for button in row.get("components", []):
            if not isinstance(button, dict):
                continue
            if int(button.get("type", 0) or 0) != 2:
                continue
            url = sanitize_text(button.get("url", ""))
            if not url:
                continue
            label = truncate_text(sanitize_text(button.get("label", "Open")) or "Open", 80)
            buttons.append(
                {
                    "type": 2,
                    "style": 5,
                    "label": label,
                    "url": url,
                }
            )
        if buttons:
            rows.append({"type": 1, "components": buttons[:5]})
    return rows[:5]


def build_twitch_open_components(stream_url, member_profile_url="", member_profile_label=""):
    buttons = []
    watch_url = sanitize_text(stream_url)
    if watch_url:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "視聴する / Watch",
                "url": watch_url,
            }
        )
    profile_url = sanitize_text(member_profile_url)
    profile_label_text = truncate_text(sanitize_text(member_profile_label) or "メンバー / Member", 80)
    if profile_url:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": profile_label_text,
                "url": profile_url,
            }
        )
    if not buttons:
        return []
    return [{"type": 1, "components": buttons[:5]}]


def build_twitter_open_components(tweet_url, profile_url="", profile_label="", link_url="", link_label=""):
    buttons = []
    post_url = sanitize_text(tweet_url)
    if post_url:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "投稿を見る / Open Post",
                "url": post_url,
            }
        )
    target_link = sanitize_text(link_url)
    if target_link:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": truncate_text(sanitize_text(link_label) or "リンク先 / Link", 80),
                "url": target_link,
            }
        )
    resolved_profile_url = sanitize_text(profile_url)
    if resolved_profile_url:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": truncate_text(sanitize_text(profile_label) or "アカウント / Profile", 80),
                "url": resolved_profile_url,
            }
        )
    if not buttons:
        return []
    return [{"type": 1, "components": buttons[:5]}]


def normalize_profile_card_contact_labels(raw_labels):
    labels = []
    if not isinstance(raw_labels, list):
        return labels
    for raw_label in raw_labels[:5]:
        label = truncate_text(sanitize_text(raw_label), 24)
        if not label or label in labels:
            continue
        labels.append(label)
    return labels[:3]


def build_profile_card_recruitment_lines(raw_recruitments):
    lines = []
    if not isinstance(raw_recruitments, list):
        return lines

    for raw_entry in raw_recruitments[:3]:
        if not isinstance(raw_entry, dict):
            continue
        label = truncate_text(sanitize_text(raw_entry.get("type_label") or raw_entry.get("type") or "募集"), 24) or "募集"
        title = truncate_text(sanitize_text(raw_entry.get("title", "")), 80)
        summary = truncate_text(sanitize_text(raw_entry.get("summary", "")), 120)
        if title:
            line = "{}: {}".format(label, title)
            if summary and summary not in title:
                line = "{} / {}".format(line, summary)
        elif summary:
            line = "{}: {}".format(label, summary)
        else:
            continue
        lines.append(truncate_text(line, 240))
    return lines[:3]


def normalize_profile_card_tags(raw_values):
    if isinstance(raw_values, str):
        values = re.split(r"[\r\n,、]+", raw_values)
    elif isinstance(raw_values, list):
        values = raw_values
    else:
        values = []

    labels = []
    seen = set()
    for raw in values:
        label = truncate_text(sanitize_text(raw), 24)
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= 8:
            break
    return labels


def normalize_profile_card_linked_accounts(raw_values):
    values = raw_values if isinstance(raw_values, list) else []
    links = []
    seen = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        label = truncate_text(sanitize_text(raw.get("label", "")), 40)
        url = sanitize_text(raw.get("url", ""))
        value = truncate_text(sanitize_text(raw.get("value", "")), 120)
        if not label or not url:
            continue
        key = "{}:{}".format(label.casefold(), url.casefold())
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "label": label,
                "url": url,
                "value": value,
            }
        )
        if len(links) >= 8:
            break
    return links


def build_wordpress_account_link_url(anchor=""):
    base_url = sanitize_text(WORDPRESS_ACCOUNT_LINK_URL).rstrip("/")
    if not base_url:
        return ""
    anchor_text = sanitize_text(anchor).lstrip("#")
    if anchor_text:
        return "{}/#{}".format(base_url, anchor_text)
    return base_url + "/"


def build_profile_card_action_button(label, custom_id, style=2):
    resolved_id = sanitize_text(custom_id)
    if not resolved_id:
        return None
    return {
        "type": 2,
        "style": int(style),
        "label": truncate_text(sanitize_text(label), 80),
        "custom_id": resolved_id,
    }


def build_profile_card_link_button(label, url):
    resolved_url = sanitize_text(url)
    if not resolved_url:
        return None
    return {
        "type": 2,
        "style": 5,
        "label": truncate_text(sanitize_text(label), 80),
        "url": resolved_url,
    }


def build_profile_card_link_components(payload, include_primary_links=False):
    if not isinstance(payload, dict):
        return []

    buttons = []
    seen_urls = set()

    def append_link_button(label, url):
        button = build_profile_card_link_button(label, url)
        resolved_url = sanitize_text(url)
        if button is None or resolved_url in seen_urls:
            return
        seen_urls.add(resolved_url)
        buttons.append(button)

    if include_primary_links:
        append_link_button("Discordプロフィールを見る", payload.get("discord_profile_url", ""))
        append_link_button("Discord専用スレッドを見る", payload.get("thread_url", ""))

    linked_accounts = normalize_profile_card_linked_accounts(payload.get("linked_account_links"))
    for entry in linked_accounts:
        label = truncate_text(sanitize_text(entry.get("label", "連携先")), 40) or "連携先"
        if not label.endswith("を見る"):
            label = "{}を見る".format(label)
        append_link_button(label, entry.get("url", ""))

    if include_primary_links:
        append_link_button("Discordサーバーを見る", payload.get("owned_discord_server_invite_url", ""))

    rows = []
    for index in range(0, len(buttons), 5):
        rows.append({"type": 1, "components": buttons[index:index + 5]})
    return rows


def build_profile_card_open_components(payload):
    if not isinstance(payload, dict):
        return []

    owner_user_id = normalize_discord_user_id(payload.get("user_id", ""))

    first_row = [
        {
            "type": 2,
            "style": 1,
            "label": "入室 / 退室",
            "custom_id": PROFILE_CARD_THREAD_TOGGLE_CUSTOM_ID,
        }
    ]

    for button in (
        build_profile_card_action_button("プロフィール編集", "{}:{}".format(PROFILE_CARD_EDIT_BUTTON_PREFIX, owner_user_id)),
        build_profile_card_action_button("Discord招待設定", "{}:{}".format(PROFILE_CARD_INVITE_BUTTON_PREFIX, owner_user_id)),
        build_profile_card_action_button("画像設定", "{}:{}".format(PROFILE_CARD_IMAGE_BUTTON_PREFIX, owner_user_id)),
        build_profile_card_action_button("タグ設定", "{}:{}".format(PROFILE_CARD_TAG_BUTTON_PREFIX, owner_user_id)),
    ):
        if button is not None:
            first_row.append(button)
        if len(first_row) >= 5:
            break

    rows = []
    if first_row:
        rows.append({"type": 1, "components": first_row[:5]})

    second_row = []
    create_channel_button = build_profile_card_action_button(
        "公開設定",
        "{}:{}".format(PROFILE_CARD_CHANNEL_BUTTON_PREFIX, owner_user_id),
    )
    if create_channel_button is not None:
        second_row.append(create_channel_button)
    workspace_button = build_profile_card_action_button(
        "チャンネル作成",
        "{}:{}".format(PROFILE_CARD_WORKSPACE_BUTTON_PREFIX, owner_user_id),
    )
    if workspace_button is not None:
        second_row.append(workspace_button)
    if owner_user_id:
        second_row.append(
            {
                "type": 2,
                "style": 4,
                "label": "スレッド削除",
                "custom_id": "{}:{}".format(PROFILE_CARD_DELETE_BUTTON_PREFIX, owner_user_id),
            }
        )
    if second_row:
        rows.append({"type": 1, "components": second_row[:5]})

    rows.extend(build_profile_card_link_components(payload))

    return rows


def normalize_discord_message_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def is_http_url(value):
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def extract_google_drive_file_id(url):
    raw = sanitize_text(url)
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except Exception:
        return ""

    host = str(parsed.netloc or "").lower()
    if "drive.google.com" not in host:
        return ""

    path = str(parsed.path or "")
    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", path)
    if match:
        return sanitize_text(match.group(1))

    query_map = parse_qs(parsed.query or "")
    file_ids = query_map.get("id", [])
    if file_ids:
        return sanitize_text(file_ids[0])
    return ""


def normalize_embed_image_url(url):
    raw = sanitize_text(url)
    if not raw:
        return ""

    drive_file_id = extract_google_drive_file_id(raw)
    if drive_file_id:
        # Discord 側の取得失敗を避けるため、リダイレクト不要の直接配信URLへ正規化する。
        return "https://drive.usercontent.google.com/download?id={}&export=view".format(quote(drive_file_id, safe=""))

    return raw


def build_discord_avatar_url(user_id, avatar_hash, size=128):
    user_text = sanitize_text(user_id)
    avatar_text = sanitize_text(avatar_hash)
    if not user_text or not avatar_text:
        return ""
    extension = "gif" if avatar_text.startswith("a_") else "png"
    return "https://cdn.discordapp.com/avatars/{}/{}.{}?size={}".format(user_text, avatar_text, extension, int(size or 128))


def get_discord_message_author_name(message):
    if not isinstance(message, dict):
        return "Unknown"
    member = message.get("member", {}) if isinstance(message.get("member", {}), dict) else {}
    author = message.get("author", {}) if isinstance(message.get("author", {}), dict) else {}
    return truncate_text(
        str(
            member.get("nick")
            or author.get("global_name")
            or author.get("username")
            or "Unknown"
        ).strip(),
        80,
    ) or "Unknown"


def get_discord_message_author_icon_url(message):
    if not isinstance(message, dict):
        return ""
    author = message.get("author", {}) if isinstance(message.get("author", {}), dict) else {}
    return build_discord_avatar_url(author.get("id", ""), author.get("avatar", ""), size=128)


def extract_discord_message_primary_image_url(message):
    if not isinstance(message, dict):
        return ""

    for attachment in message.get("attachments", []) if isinstance(message.get("attachments", []), list) else []:
        if not isinstance(attachment, dict):
            continue
        # proxy_url は失効しやすいため、再投稿 embed では attachment の url を優先する。
        candidate_url = sanitize_text(attachment.get("url", "") or attachment.get("proxy_url", ""))
        if not candidate_url:
            continue
        content_type = str(attachment.get("content_type", "") or "").strip().lower()
        filename = str(attachment.get("filename", "") or "").strip().lower()
        width = int(attachment.get("width", 0) or 0)
        height = int(attachment.get("height", 0) or 0)
        if (
            content_type.startswith("image/")
            or filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".avif"))
            or (width > 0 and height > 0)
        ):
            return candidate_url

    for embed in message.get("embeds", []) if isinstance(message.get("embeds", []), list) else []:
        if not isinstance(embed, dict):
            continue
        for block_name in ("image", "thumbnail"):
            block = embed.get(block_name, {}) if isinstance(embed.get(block_name, {}), dict) else {}
            candidate_url = sanitize_text(block.get("url", ""))
            if candidate_url.startswith("attachment://"):
                attachment_name = sanitize_text(candidate_url.replace("attachment://", "", 1)).lower()
                if attachment_name:
                    for attachment in message.get("attachments", []) if isinstance(message.get("attachments", []), list) else []:
                        if not isinstance(attachment, dict):
                            continue
                        filename = sanitize_text(attachment.get("filename", "")).lower()
                        if filename != attachment_name:
                            continue
                        resolved = sanitize_text(attachment.get("url", "") or attachment.get("proxy_url", ""))
                        if is_http_url(resolved):
                            return resolved
            if is_http_url(candidate_url):
                return candidate_url

    return ""


def extract_first_image_url_from_embed_fields(embed_payload):
    if not isinstance(embed_payload, dict):
        return ""

    fields = embed_payload.get("fields", []) if isinstance(embed_payload.get("fields", []), list) else []
    for field in fields:
        if not isinstance(field, dict):
            continue
        value = str(field.get("value", "") or "")
        for match in re.finditer(r"\((https?://[^)\s]+)\)", value, flags=re.IGNORECASE):
            candidate_url = sanitize_text(match.group(1))
            lowered = candidate_url.lower()
            if not is_http_url(candidate_url):
                continue
            if any(ext in lowered for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".avif")):
                return candidate_url
            if "cdn.discordapp.com/attachments/" in lowered:
                return candidate_url
    return ""


def replace_first_markdown_link_url(text, new_url):
    source = str(text or "")
    target_url = sanitize_text(new_url)
    if not source or not target_url:
        return source, False

    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)([^\n]*)", flags=re.IGNORECASE)

    def _replace(match):
        label = sanitize_text(match.group(1)) or "image"
        suffix = str(match.group(3) or "")
        return "[{}]({}){}".format(label, target_url, suffix)

    replaced, count = pattern.subn(_replace, source, count=1)
    return replaced, count > 0


def sync_embed_attachment_field_image_url(embed_payload, image_url):
    if not isinstance(embed_payload, dict):
        return

    target_url = sanitize_text(image_url)
    if not target_url:
        return

    fields = embed_payload.get("fields", []) if isinstance(embed_payload.get("fields", []), list) else []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if sanitize_text(field.get("name", "")) != "添付ファイル":
            continue

        current_value = str(field.get("value", "") or "")
        updated_value, replaced = replace_first_markdown_link_url(current_value, target_url)
        if replaced:
            field["value"] = updated_value
        elif not current_value.strip():
            field["value"] = "[image]({})".format(target_url)
        return


def build_discord_message_attachment_lines(message, excluded_url=""):
    if not isinstance(message, dict):
        return []

    lines = []
    excluded_text = sanitize_text(excluded_url)
    for attachment in message.get("attachments", []) if isinstance(message.get("attachments", []), list) else []:
        if not isinstance(attachment, dict):
            continue
        candidate_url = sanitize_text(attachment.get("url", ""))
        if not candidate_url or candidate_url == excluded_text:
            continue
        label = truncate_text(sanitize_text(attachment.get("filename", "attachment")) or "attachment", 80)
        size = int(attachment.get("size", 0) or 0)
        size_text = " ({} KB)".format(max(1, int(size / 1024))) if size > 0 else ""
        lines.append("[{}]({}){}".format(label, candidate_url, size_text))
        if len(lines) >= 5:
            break
    return lines


def build_channel_repost_components(source_channel_id, source_message_id):
    buttons = []

    jump_url = build_nexus_jump_url(source_channel_id, source_message_id)
    open_button = build_profile_card_link_button("元メッセージを開く", jump_url)
    if open_button is not None:
        buttons.append(open_button)

    edit_button = build_profile_card_action_button("管理者投稿編集", CHANNEL_REPOST_EDIT_BUTTON_CUSTOM_ID)
    if edit_button is not None:
        buttons.append(edit_button)

    if not buttons:
        return []
    return [{"type": 1, "components": buttons[:5]}]


def normalize_channel_repost_components_for_admin_edit(components):
    if not isinstance(components, list):
        return [], False

    normalized_rows = []
    changed = False
    for row in components:
        if not isinstance(row, dict):
            continue
        if int(row.get("type", 0) or 0) != 1:
            continue

        row_components = row.get("components", []) if isinstance(row.get("components", []), list) else []
        normalized_components = []
        for component in row_components:
            if not isinstance(component, dict):
                continue

            updated_component = dict(component)
            custom_id = sanitize_text(updated_component.get("custom_id", ""))
            if custom_id == CHANNEL_REPOST_LEGACY_IMAGE_BUTTON_CUSTOM_ID:
                updated_component["custom_id"] = CHANNEL_REPOST_EDIT_BUTTON_CUSTOM_ID
                updated_component["label"] = "管理者投稿編集"
                changed = True
            elif custom_id == CHANNEL_REPOST_EDIT_BUTTON_CUSTOM_ID:
                if sanitize_text(updated_component.get("label", "")) != "管理者投稿編集":
                    updated_component["label"] = "管理者投稿編集"
                    changed = True

            normalized_components.append(updated_component)

        if normalized_components:
            normalized_rows.append({"type": 1, "components": normalized_components[:5]})

    return normalized_rows, changed


def promote_channel_repost_legacy_button(channel_id, message_id):
    channel_text = sanitize_text(channel_id)
    message_text = sanitize_text(message_id)
    if not channel_text or not channel_text.isdigit():
        return False
    if not message_text or not message_text.isdigit():
        return False

    path = "/channels/{}/messages/{}".format(channel_text, message_text)
    message_payload = discord_request_json(path)
    if not isinstance(message_payload, dict):
        return False

    normalized_components, changed = normalize_channel_repost_components_for_admin_edit(message_payload.get("components", []))
    if not changed or not normalized_components:
        return False

    discord_patch_json(path, {"components": normalized_components})
    return True


def build_channel_repost_embed(source_message, source_channel_id, source_channel_name="", image_url=""):
    if not isinstance(source_message, dict):
        return {}

    message_id = sanitize_text(source_message.get("id", ""))
    description = normalize_discord_message_text(source_message.get("content", ""))
    if not description:
        description = discord_message_embed_text(source_message, mode="full")
    description = description or "本文なしのメッセージです。"

    resolved_image_url = sanitize_text(image_url) or extract_discord_message_primary_image_url(source_message)
    attachment_lines = build_discord_message_attachment_lines(source_message, excluded_url=resolved_image_url)
    jump_url = build_nexus_jump_url(source_channel_id, message_id)

    footer_parts = []
    channel_name = sanitize_text(source_channel_name)
    if channel_name:
        footer_parts.append("#{}".format(channel_name))
    if message_id:
        footer_parts.append("message {}".format(message_id))

    embed = {
        "description": truncate_text(description, 4096),
        "color": 0x5865F2,
        "author": {
            "name": get_discord_message_author_name(source_message),
        },
        "footer": {
            "text": truncate_text(" | ".join(footer_parts) or "Discord message repost", 200),
        },
    }

    author_icon_url = get_discord_message_author_icon_url(source_message)
    if author_icon_url:
        embed["author"]["icon_url"] = author_icon_url

    timestamp = str(source_message.get("timestamp", "") or "").strip()
    if timestamp:
        embed["timestamp"] = timestamp

    if jump_url:
        embed["url"] = jump_url

    if resolved_image_url:
        embed["image"] = {"url": resolved_image_url}

    fields = []
    if attachment_lines:
        fields.append(
            {
                "name": "添付ファイル",
                "value": "\n".join(attachment_lines),
                "inline": False,
            }
        )
    if len(description) > 4096:
        fields.append(
            {
                "name": "本文メモ",
                "value": "本文が長いため embed 内では先頭のみ表示しています。",
                "inline": False,
            }
        )
    if fields:
        embed["fields"] = fields[:25]

    return embed


def build_channel_repost_message_payload(source_message, source_channel_id, source_channel_name=""):
    embed = build_channel_repost_embed(source_message, source_channel_id, source_channel_name=source_channel_name)
    if not embed:
        return {}

    message_id = sanitize_text(source_message.get("id", ""))
    payload = {
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }
    components = build_channel_repost_components(source_channel_id, message_id)
    if components:
        payload["components"] = components
    return payload


def repost_discord_channel_messages_as_embeds(
    source_channel_id,
    destination_channel_id,
    limit=10,
    before_message_id="",
    after_message_id="",
    include_bots=False,
    source_channel_name="",
):
    source_text = sanitize_text(source_channel_id)
    destination_text = sanitize_text(destination_channel_id)
    if not source_text or not source_text.isdigit():
        raise RuntimeError("source_channel_id is invalid")
    if not destination_text or not destination_text.isdigit():
        raise RuntimeError("destination_channel_id is invalid")

    requested_limit = max(1, min(int(limit or 10), 20))
    messages = fetch_discord_channel_messages(
        source_text,
        limit=requested_limit,
        before_message_id=before_message_id,
        after_message_id=after_message_id,
    )
    messages.sort(key=lambda item: int(str(item.get("id", "0") or "0")))

    posted_message_ids = []
    skipped_bot_messages = 0
    skipped_empty_messages = 0

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue

        author = message.get("author", {}) if isinstance(message.get("author", {}), dict) else {}
        if not include_bots and bool(author.get("bot", False)):
            skipped_bot_messages += 1
            continue

        payload = build_channel_repost_message_payload(message, source_text, source_channel_name=source_channel_name)
        embeds = payload.get("embeds", []) if isinstance(payload.get("embeds", []), list) else []
        if not embeds:
            skipped_empty_messages += 1
            continue

        result = discord_post_json("/channels/{}/messages".format(destination_text), payload)
        if not isinstance(result, dict):
            raise RuntimeError("Discord repost message response is invalid")
        posted_message_id = sanitize_text(result.get("id", ""))
        if posted_message_id:
            posted_message_ids.append(posted_message_id)

        # 一括 repost でも Discord REST の 429 を避けるため少し間隔を空ける。
        if index < len(messages) - 1:
            time.sleep(0.35)

    return {
        "requested": requested_limit,
        "fetched": len(messages),
        "posted": len(posted_message_ids),
        "posted_message_ids": posted_message_ids,
        "skipped_bots": skipped_bot_messages,
        "skipped_empty": skipped_empty_messages,
    }


def update_channel_repost_message_embed(channel_id, message_id, embed_payload, title=None, description=None, image_url=None):
    channel_text = sanitize_text(channel_id)
    message_text = sanitize_text(message_id)
    if not channel_text or not channel_text.isdigit():
        raise RuntimeError("channel_id is invalid")
    if not message_text or not message_text.isdigit():
        raise RuntimeError("message_id is invalid")
    if not isinstance(embed_payload, dict):
        raise RuntimeError("embed payload is invalid")

    updated_embed = dict(embed_payload)
    if title is not None:
        resolved_title = truncate_text(sanitize_text(title), 256)
        if resolved_title:
            updated_embed["title"] = resolved_title
        else:
            updated_embed.pop("title", None)

    if description is not None:
        normalized_description = normalize_discord_message_text(description)
        if normalized_description:
            updated_embed["description"] = truncate_text(normalized_description, 4096)
        else:
            updated_embed.pop("description", None)

        current_fields = updated_embed.get("fields", []) if isinstance(updated_embed.get("fields", []), list) else []
        filtered_fields = []
        for field in current_fields:
            if not isinstance(field, dict):
                continue
            if sanitize_text(field.get("name", "")) == "本文メモ":
                continue
            filtered_fields.append(field)

        if len(normalized_description) > 4096 and len(filtered_fields) < 25:
            filtered_fields.append(
                {
                    "name": "本文メモ",
                    "value": "本文が長いため embed 内では先頭のみ表示しています。",
                    "inline": False,
                }
            )

        if filtered_fields:
            updated_embed["fields"] = filtered_fields[:25]
        else:
            updated_embed.pop("fields", None)

    if image_url is not None:
        resolved_image_url = normalize_embed_image_url(str(image_url or "").strip())
        if resolved_image_url:
            if not is_http_url(resolved_image_url):
                raise RuntimeError("image_url must be an http or https URL")
            updated_embed["image"] = {"url": resolved_image_url}
            # 管理者編集時に image と 添付リンクのURLを同じ値へ揃える。
            sync_embed_attachment_field_image_url(updated_embed, resolved_image_url)
        else:
            updated_embed.pop("image", None)

    return discord_patch_json(
        "/channels/{}/messages/{}".format(channel_text, message_text),
        {"embeds": [updated_embed]},
    )


def update_channel_repost_message_image(channel_id, message_id, embed_payload, image_url=""):
    return update_channel_repost_message_embed(
        channel_id,
        message_id,
        embed_payload,
        image_url=image_url,
    )


def build_profile_card_embed(payload):
    display_name = truncate_text(sanitize_text(payload.get("display_name", "")) or "Member", 100)
    owner_user_id = normalize_discord_user_id(payload.get("user_id", ""))
    discord_profile_url = sanitize_text(payload.get("discord_profile_url", ""))
    discord_avatar_url = sanitize_text(payload.get("discord_avatar_url", ""))
    discord_banner_url = sanitize_text(payload.get("discord_banner_url", ""))
    visibility = "public" if sanitize_text(payload.get("intro_card_visibility", "")).lower() == "public" else "private"
    visibility_label = "公開 / Public" if visibility == "public" else "非公開 / Private"
    summary = truncate_text(sanitize_text(payload.get("intro_card_summary", "")), 3200)
    if not summary:
        summary = (
            "中央プロフィールの公開カードです。"
            if visibility == "public"
            else "中央プロフィールは登録済みですが、現在は非公開設定です。Discord 専用スレッド側のみ更新されています。"
        )

    fields = [
        {
            "name": "利用フロー / Flow",
            "value": "入室 / 退室で参加を切り替え、プロフィール編集・公開設定・招待設定・画像設定・タグ設定・チャンネル作成をこのスレッド内から操作できます。",
            "inline": False,
        },
        {
            "name": "公開設定 / Visibility",
            "value": visibility_label,
            "inline": True,
        }
    ]

    if owner_user_id:
        fields.append(
            {
                "name": "作成者 / Creator",
                "value": "<@{}>".format(owner_user_id),
                "inline": True,
            }
        )

    member_status_label = truncate_text(sanitize_text(payload.get("member_status_label", "")), 120)
    if member_status_label:
        fields.append(
            {
                "name": "会員状況 / Status",
                "value": member_status_label,
                "inline": True,
            }
        )

    contact_labels = normalize_profile_card_contact_labels(payload.get("contact_preference_labels"))
    fields.append(
        {
            "name": "連絡方法 / Contact",
            "value": " / ".join(contact_labels) if contact_labels else "未設定 / Not set",
            "inline": False,
        }
    )

    recruitment_lines = build_profile_card_recruitment_lines(payload.get("recruitments"))
    if recruitment_lines:
        fields.append(
            {
                "name": "募集中 / Looking For",
                "value": "\n".join(recruitment_lines),
                "inline": False,
            }
        )

    tag_labels = normalize_profile_card_tags(payload.get("tags"))
    if tag_labels:
        fields.append(
            {
                "name": "タグ / Tags",
                "value": " / ".join(tag_labels),
                "inline": False,
            }
        )

    linked_accounts = normalize_profile_card_linked_accounts(payload.get("linked_account_links"))
    if linked_accounts:
        account_lines = []
        for entry in linked_accounts[:5]:
            label = truncate_text(sanitize_text(entry.get("label", "連携先")), 40)
            value = truncate_text(sanitize_text(entry.get("value", "")), 120)
            if value:
                account_lines.append("{}: {}".format(label, value))
            else:
                account_lines.append("{}: {}".format(label, truncate_text(sanitize_text(entry.get("url", "")), 120)))
        fields.append(
            {
                "name": "連携アカウント / Linked Accounts",
                "value": "\n".join(account_lines),
                "inline": False,
            }
        )

    server_name = truncate_text(sanitize_text(payload.get("owned_discord_server_name", "")), 100)
    invite_url = sanitize_text(payload.get("owned_discord_server_invite_url", ""))
    if server_name or invite_url:
        server_lines = []
        if server_name:
            server_lines.append(server_name)
        if invite_url:
            server_lines.append(invite_url)
        fields.append(
            {
                "name": "Discordサーバー / Discord Server",
                "value": "\n".join(server_lines),
                "inline": False,
            }
        )

    workspace_lines = []
    workspace_category_name = truncate_text(sanitize_text(payload.get("workspace_category_name", "")), 100)
    workspace_text_channel_id = sanitize_text(payload.get("workspace_text_channel_id", ""))
    workspace_text_channel_name = truncate_text(sanitize_text(payload.get("workspace_text_channel_name", "")), 100)
    workspace_voice_channel_id = sanitize_text(payload.get("workspace_voice_channel_id", ""))
    workspace_voice_channel_name = truncate_text(sanitize_text(payload.get("workspace_voice_channel_name", "")), 100)
    if workspace_category_name:
        workspace_lines.append("カテゴリ: {}".format(workspace_category_name))
    if workspace_text_channel_id.isdigit():
        workspace_lines.append("テキスト: <#{}>".format(workspace_text_channel_id))
    elif workspace_text_channel_name:
        workspace_lines.append("テキスト: {}".format(workspace_text_channel_name))
    if workspace_voice_channel_id.isdigit():
        workspace_lines.append("ボイス: <#{}>".format(workspace_voice_channel_id))
    elif workspace_voice_channel_name:
        workspace_lines.append("ボイス: {}".format(workspace_voice_channel_name))
    if workspace_lines:
        fields.append(
            {
                "name": "ワークスペース / Workspace",
                "value": "\n".join(workspace_lines),
                "inline": False,
            }
        )

    room_name = truncate_text(sanitize_text(payload.get("room_name", "")), 100)
    if room_name:
        fields.append(
            {
                "name": "セットアップ / Setup",
                "value": room_name,
                "inline": True,
            }
        )

    embed = {
        "title": "📇 {} のプロフィール".format(display_name),
        "description": summary,
        "color": 0x3BA55C if visibility == "public" else 0x5F6B7A,
        "fields": fields[:25],
        "footer": {"text": "7DTD プロフィールスレッド / WordPress"},
    }

    if discord_profile_url:
        embed["url"] = discord_profile_url

    if discord_avatar_url:
        embed["thumbnail"] = {"url": discord_avatar_url}

    image_url = sanitize_text(payload.get("image_url", ""))
    if discord_banner_url:
        embed["image"] = {"url": discord_banner_url}
    elif image_url:
        embed["image"] = {"url": image_url}

    updated_at = sanitize_text(payload.get("updated_at", ""))
    if updated_at:
        embed["timestamp"] = updated_at
    return embed


def build_profile_card_message_payload(payload):
    discord_user_id = sanitize_text(payload.get("user_id", ""))
    display_name = truncate_text(sanitize_text(payload.get("display_name", "")) or "Member", 100)
    if discord_user_id.isdigit():
        content = "<@{}> さんのプロフィール専用スレッド / Profile thread".format(discord_user_id)
    else:
        content = "{} さんのプロフィール専用スレッド / Profile thread".format(display_name)

    return {
        "content": truncate_text(content, 1800),
        "embeds": [build_profile_card_embed(payload)],
        "components": build_profile_card_open_components(payload),
    }


def build_profile_card_voice_notify_message_payload(payload, voice_channel_id="", voice_channel_name=""):
    display_name = truncate_text(sanitize_text(payload.get("display_name", "")) or "Member", 100)
    resolved_voice_channel_id = sanitize_text(voice_channel_id)
    resolved_voice_channel_name = truncate_text(sanitize_text(voice_channel_name), 100)
    if resolved_voice_channel_id.isdigit():
        content = "{} さんが <#{}> に入室しました / Joined voice".format(display_name, resolved_voice_channel_id)
        voice_value = "<#{}>".format(resolved_voice_channel_id)
    elif resolved_voice_channel_name:
        content = "{} さんが {} に入室しました / Joined voice".format(display_name, resolved_voice_channel_name)
        voice_value = resolved_voice_channel_name
    else:
        content = "{} さんのプロフィールカード / Profile card".format(display_name)
        voice_value = ""

    embed = build_profile_card_embed(payload)
    filtered_fields = []
    for field in embed.get("fields", []):
        if sanitize_text(field.get("name", "")) == "利用フロー / Flow":
            continue
        filtered_fields.append(field)
    if voice_value:
        filtered_fields.insert(
            0,
            {
                "name": "入室VC / Joined Voice",
                "value": voice_value,
                "inline": True,
            },
        )
    embed["fields"] = filtered_fields[:25]
    embed["footer"] = {"text": "VC 入室プロフィール通知 / WordPress"}

    return {
        "content": truncate_text(content, 1800),
        "embeds": [embed],
        "components": build_profile_card_link_components(payload, include_primary_links=True),
    }


def disable_profile_card_thread(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    thread_id = sanitize_text(payload.get("thread_id", ""))
    parent_channel_id = sanitize_text(payload.get("thread_channel_id", "") or DISCORD_THREAD_CHANNEL_ID)
    if thread_id and thread_id.isdigit():
        try:
            discord_patch_json("/channels/{}".format(thread_id), {"archived": True})
        except Exception as exc:
            exc_text = sanitize_text(str(exc))
            if "404" not in exc_text and "10003" not in exc_text:
                raise

    thread_url = ""
    if thread_id and thread_id.isdigit() and parent_channel_id.isdigit():
        thread_url = build_profile_card_thread_url(parent_channel_id, thread_id)

    return {
        "ok": True,
        "thread_id": thread_id if thread_id.isdigit() else "",
        "thread_url": thread_url,
        "thread_disabled": True,
        "created": False,
        "note": "Discord専用スレッドはOFFのため同期を停止しました。",
    }


def list_discord_threads_for_parent(parent_channel_id):
    parent_id = sanitize_text(parent_channel_id)
    if not parent_id or not parent_id.isdigit():
        return []

    threads = []
    seen_ids = set()

    active_data = discord_request_json("/guilds/{}/threads/active".format(DISCORD_GUILD_ID))
    active_rows = active_data.get("threads", []) if isinstance(active_data, dict) else []
    for row in active_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("parent_id", "")) != parent_id:
            continue
        thread_id = str(row.get("id", ""))
        if not thread_id or thread_id in seen_ids:
            continue
        seen_ids.add(thread_id)
        threads.append(row)

    archived_data = discord_request_json("/channels/{}/threads/archived/public?limit=100".format(parent_id))
    archived_rows = archived_data.get("threads", []) if isinstance(archived_data, dict) else []
    for row in archived_rows:
        if not isinstance(row, dict):
            continue
        thread_id = str(row.get("id", ""))
        if not thread_id or thread_id in seen_ids:
            continue
        seen_ids.add(thread_id)
        threads.append(row)

    return threads


def find_discord_thread_by_name(parent_channel_id, thread_name):
    normalized = sanitize_text(thread_name).lower()
    if not normalized:
        return None
    for row in list_discord_threads_for_parent(parent_channel_id):
        name = sanitize_text(row.get("name", "")).lower()
        if name == normalized:
            return row
    return None


def ensure_discord_thread_unarchived(thread_payload):
    if not isinstance(thread_payload, dict):
        return
    thread_id = sanitize_text(thread_payload.get("id", ""))
    metadata = thread_payload.get("thread_metadata", {}) if isinstance(thread_payload.get("thread_metadata"), dict) else {}
    if not thread_id or not bool(metadata.get("archived", False)):
        return
    try:
        discord_patch_json("/channels/{}".format(thread_id), {"archived": False})
    except Exception:
        return


def build_profile_card_thread_url(parent_channel_id, thread_id):
    return build_nexus_jump_url(parent_channel_id, thread_id)


def fetch_discord_current_bot_user_id():
    data = discord_request_json("/users/@me")
    if not isinstance(data, dict):
        raise RuntimeError("Discord bot user response is invalid")
    user_id = sanitize_text(data.get("id", ""))
    if not user_id or not user_id.isdigit():
        raise RuntimeError("Discord bot user id is invalid")
    return user_id


def fetch_discord_guild_channels():
    rows = discord_request_json("/guilds/{}/channels".format(DISCORD_GUILD_ID))
    if not isinstance(rows, list):
        raise RuntimeError("Discord guild channels response is invalid")
    return [row for row in rows if isinstance(row, dict)]


def build_profile_card_workspace_category_name(payload):
    display_name = truncate_text(sanitize_text(payload.get("display_name", "")) or "Member", 84)
    return truncate_text("⬛ Instance | {}".format(display_name), 100)


def build_profile_card_workspace_permission_overwrites(owner_user_id):
    owner_text = normalize_discord_user_id(owner_user_id)
    if not owner_text:
        raise RuntimeError("profile workspace owner user id is invalid")

    owner_allow = (
        DISCORD_PERMISSION_MANAGE_CHANNELS
        | DISCORD_PERMISSION_VIEW_CHANNEL
        | DISCORD_PERMISSION_SEND_MESSAGES
        | DISCORD_PERMISSION_READ_MESSAGE_HISTORY
        | DISCORD_PERMISSION_CONNECT
        | DISCORD_PERMISSION_SPEAK
        | DISCORD_PERMISSION_USE_APPLICATION_COMMANDS
        | DISCORD_PERMISSION_MANAGE_THREADS
    )
    bot_allow = owner_allow | DISCORD_PERMISSION_MANAGE_MESSAGES
    bot_user_id = fetch_discord_current_bot_user_id()

    return [
        {
            "id": DISCORD_GUILD_ID,
            "type": 0,
            "allow": "0",
            "deny": str(DISCORD_PERMISSION_VIEW_CHANNEL),
        },
        {
            "id": owner_text,
            "type": 1,
            "allow": str(owner_allow),
            "deny": "0",
        },
        {
            "id": bot_user_id,
            "type": 1,
            "allow": str(bot_allow),
            "deny": "0",
        },
    ]


def find_discord_guild_channel_by_id(channels, channel_id, channel_type=None):
    channel_text = sanitize_text(channel_id)
    if not channel_text or not channel_text.isdigit():
        return None
    for row in channels or []:
        if not isinstance(row, dict):
            continue
        if sanitize_text(row.get("id", "")) != channel_text:
            continue
        if channel_type is not None and int(row.get("type", -1) or -1) != int(channel_type):
            continue
        return row
    return None


def find_discord_profile_workspace_category(channels, category_id="", category_name=""):
    row = find_discord_guild_channel_by_id(channels, category_id, channel_type=4)
    if isinstance(row, dict):
        return row

    normalized_name = truncate_text(sanitize_text(category_name), 100)
    if not normalized_name:
        return None
    for candidate in channels or []:
        if not isinstance(candidate, dict):
            continue
        if int(candidate.get("type", -1) or -1) != 4:
            continue
        if truncate_text(sanitize_text(candidate.get("name", "")), 100) == normalized_name:
            return candidate
    return None


def find_discord_profile_workspace_child_channel(channels, category_id, channel_type, channel_id="", channel_name=""):
    row = find_discord_guild_channel_by_id(channels, channel_id, channel_type=channel_type)
    if isinstance(row, dict):
        return row

    parent_text = sanitize_text(category_id)
    normalized_name = truncate_text(sanitize_text(channel_name), 100)
    if not parent_text or not parent_text.isdigit() or not normalized_name:
        return None
    for candidate in channels or []:
        if not isinstance(candidate, dict):
            continue
        if int(candidate.get("type", -1) or -1) != int(channel_type):
            continue
        if sanitize_text(candidate.get("parent_id", "")) != parent_text:
            continue
        if truncate_text(sanitize_text(candidate.get("name", "")), 100) == normalized_name:
            return candidate
    return None


def create_discord_guild_channel(name, channel_type, parent_id="", permission_overwrites=None):
    resolved_name = truncate_text(sanitize_text(name), 100)
    if not resolved_name:
        raise RuntimeError("Discord channel name is required")
    if not DISCORD_GUILD_ID:
        raise RuntimeError("DISCORD_GUILD_ID is not set")

    payload = {
        "name": resolved_name,
        "type": int(channel_type),
    }
    parent_text = sanitize_text(parent_id)
    if parent_text and parent_text.isdigit():
        payload["parent_id"] = parent_text
    if isinstance(permission_overwrites, list) and permission_overwrites:
        payload["permission_overwrites"] = permission_overwrites

    return discord_post_json("/guilds/{}/channels".format(DISCORD_GUILD_ID), payload)


def ensure_profile_card_workspace(payload):
    if not isinstance(payload, dict):
        return {}

    owner_user_id = normalize_discord_user_id(payload.get("user_id", ""))
    if not owner_user_id or not DISCORD_GUILD_ID:
        return {}

    guild_channels = fetch_discord_guild_channels()
    category_name = build_profile_card_workspace_category_name(payload)
    category = find_discord_profile_workspace_category(
        guild_channels,
        category_id=payload.get("workspace_category_id", ""),
        category_name=category_name,
    )
    permission_overwrites = build_profile_card_workspace_permission_overwrites(owner_user_id)

    if isinstance(category, dict):
        category_id = sanitize_text(category.get("id", ""))
        patch_payload = {
            "name": category_name,
            "permission_overwrites": permission_overwrites,
        }
        discord_patch_json("/channels/{}".format(category_id), patch_payload)
    else:
        created_category = create_discord_guild_channel(
            category_name,
            4,
            permission_overwrites=permission_overwrites,
        )
        category_id = sanitize_text(created_category.get("id", ""))
        if not category_id or not category_id.isdigit():
            raise RuntimeError("Discord profile workspace category create returned no id")

    return {
        "workspace_category_id": category_id,
        "workspace_category_name": category_name,
        "workspace_text_channel_id": sanitize_text(payload.get("workspace_text_channel_id", "")),
        "workspace_text_channel_name": truncate_text(sanitize_text(payload.get("workspace_text_channel_name", "")), 100),
        "workspace_voice_channel_id": sanitize_text(payload.get("workspace_voice_channel_id", "")),
        "workspace_voice_channel_name": truncate_text(sanitize_text(payload.get("workspace_voice_channel_name", "")), 100),
    }


def create_or_update_profile_card_workspace_channels(owner_user_id, current_state, text_channel_name="", voice_channel_name=""):
    resolved_owner_id = normalize_discord_user_id(owner_user_id)
    if not resolved_owner_id:
        raise RuntimeError("profile workspace owner user id is invalid")

    payload = dict(current_state or {})
    payload["user_id"] = resolved_owner_id
    workspace_state = ensure_profile_card_workspace(payload)
    category_id = sanitize_text(workspace_state.get("workspace_category_id", ""))
    if not category_id or not category_id.isdigit():
        raise RuntimeError("プロフィール用カテゴリを作成できませんでした。")

    requested_text_name = truncate_text(sanitize_text(text_channel_name), 100)
    requested_voice_name = truncate_text(sanitize_text(voice_channel_name), 100)
    if not requested_text_name and not requested_voice_name:
        raise RuntimeError("テキストまたはボイスのどちらかにチャンネル名を入力してください。")

    guild_channels = fetch_discord_guild_channels()
    results = []

    if requested_text_name:
        text_channel = find_discord_profile_workspace_child_channel(
            guild_channels,
            category_id,
            0,
            channel_id=workspace_state.get("workspace_text_channel_id", ""),
            channel_name=requested_text_name,
        )
        if isinstance(text_channel, dict):
            text_channel_id = sanitize_text(text_channel.get("id", ""))
            patch_payload = {}
            if truncate_text(sanitize_text(text_channel.get("name", "")), 100) != requested_text_name:
                patch_payload["name"] = requested_text_name
            if sanitize_text(text_channel.get("parent_id", "")) != category_id:
                patch_payload["parent_id"] = category_id
            if patch_payload:
                discord_patch_json("/channels/{}".format(text_channel_id), patch_payload)
                results.append("✅ テキストを更新: <#{}>".format(text_channel_id))
            else:
                results.append("ℹ️ テキストは既に設定済み: <#{}>".format(text_channel_id))
        else:
            created_text_channel = create_discord_guild_channel(requested_text_name, 0, parent_id=category_id)
            text_channel_id = sanitize_text(created_text_channel.get("id", ""))
            if not text_channel_id or not text_channel_id.isdigit():
                raise RuntimeError("テキストチャンネルの作成に失敗しました。")
            results.append("✅ テキストを作成: <#{}>".format(text_channel_id))

        workspace_state["workspace_text_channel_id"] = text_channel_id
        workspace_state["workspace_text_channel_name"] = requested_text_name

    if requested_voice_name:
        voice_channel = find_discord_profile_workspace_child_channel(
            guild_channels,
            category_id,
            2,
            channel_id=workspace_state.get("workspace_voice_channel_id", ""),
            channel_name=requested_voice_name,
        )
        if isinstance(voice_channel, dict):
            voice_channel_id = sanitize_text(voice_channel.get("id", ""))
            patch_payload = {}
            if truncate_text(sanitize_text(voice_channel.get("name", "")), 100) != requested_voice_name:
                patch_payload["name"] = requested_voice_name
            if sanitize_text(voice_channel.get("parent_id", "")) != category_id:
                patch_payload["parent_id"] = category_id
            if patch_payload:
                discord_patch_json("/channels/{}".format(voice_channel_id), patch_payload)
                results.append("✅ ボイスを更新: <#{}>".format(voice_channel_id))
            else:
                results.append("ℹ️ ボイスは既に設定済み: <#{}>".format(voice_channel_id))
        else:
            created_voice_channel = create_discord_guild_channel(requested_voice_name, 2, parent_id=category_id)
            voice_channel_id = sanitize_text(created_voice_channel.get("id", ""))
            if not voice_channel_id or not voice_channel_id.isdigit():
                raise RuntimeError("ボイスチャンネルの作成に失敗しました。")
            results.append("✅ ボイスを作成: <#{}>".format(voice_channel_id))

        workspace_state["workspace_voice_channel_id"] = voice_channel_id
        workspace_state["workspace_voice_channel_name"] = requested_voice_name

    sync_result = update_wordpress_profile_from_discord(resolved_owner_id, "workspace", workspace_state)
    return {
        "results": results,
        "sync_result": sync_result,
        "workspace": workspace_state,
    }


def recreate_profile_card_thread(parent_channel_id, thread_name, starter_payload, previous_thread_id=""):
    parent_id = sanitize_text(parent_channel_id or DISCORD_THREAD_CHANNEL_ID)
    if not parent_id or not parent_id.isdigit():
        raise RuntimeError("DISCORD_THREAD_CHANNEL_ID is not set")

    normalized_name = normalize_nexus_thread_name(thread_name, "profile-card")
    create_payload = {
        "name": normalized_name,
        "auto_archive_duration": 10080,
        "message": starter_payload,
    }
    created = discord_post_json("/channels/{}/threads".format(parent_id), create_payload)
    if not isinstance(created, dict):
        raise RuntimeError("Discord profile thread recreate response is invalid")

    new_thread_id = sanitize_text(created.get("id", ""))
    if not new_thread_id or not new_thread_id.isdigit():
        raise RuntimeError("Discord profile thread recreate returned no id")

    new_thread_url = build_profile_card_thread_url(parent_id, new_thread_id)
    previous_thread_text = sanitize_text(previous_thread_id)
    if previous_thread_text and previous_thread_text.isdigit() and previous_thread_text != new_thread_id:
        try:
            create_discord_thread_message(
                previous_thread_text,
                {
                    "content": truncate_text(
                        "新しいプロフィールスレッドへ移動しました: {}".format(new_thread_url),
                        1800,
                    )
                },
            )
        except Exception:
            pass
        try:
            discord_patch_json("/channels/{}".format(previous_thread_text), {"archived": True})
        except Exception:
            pass

    return {
        "thread_id": new_thread_id,
        "message_id": new_thread_id,
        "thread_name": normalized_name,
        "thread_url": new_thread_url,
        "created": False,
        "recreated": True,
        "parent_channel_id": parent_id,
    }


def ensure_profile_card_thread(parent_channel_id, thread_name, starter_payload, existing_thread_id="", existing_message_id=""):
    parent_id = sanitize_text(parent_channel_id or DISCORD_THREAD_CHANNEL_ID)
    if not parent_id or not parent_id.isdigit():
        raise RuntimeError("DISCORD_THREAD_CHANNEL_ID is not set")

    existing_thread_text = sanitize_text(existing_thread_id)
    fallback_name = "user-{}".format(existing_thread_text) if existing_thread_text.isdigit() else "profile-card"
    normalized_name = normalize_nexus_thread_name(thread_name, fallback_name)

    thread_payload = None
    if existing_thread_text.isdigit():
        try:
            existing_thread = discord_request_json("/channels/{}".format(existing_thread_text))
            if isinstance(existing_thread, dict) and sanitize_text(existing_thread.get("parent_id", "")) == parent_id:
                thread_payload = existing_thread
        except Exception:
            thread_payload = None

    if not isinstance(thread_payload, dict):
        thread_payload = find_discord_thread_by_name(parent_id, normalized_name)

    if isinstance(thread_payload, dict):
        ensure_discord_thread_unarchived(thread_payload)
        thread_id = sanitize_text(thread_payload.get("id", ""))
        patch_payload = {}
        if sanitize_text(thread_payload.get("name", "")) != normalized_name:
            patch_payload["name"] = normalized_name
        metadata = thread_payload.get("thread_metadata", {}) if isinstance(thread_payload.get("thread_metadata"), dict) else {}
        if bool(metadata.get("archived", False)):
            patch_payload["archived"] = False
        if patch_payload:
            discord_patch_json("/channels/{}".format(thread_id), patch_payload)
        try:
            message_id = sync_profile_card_message(thread_id, starter_payload, existing_message_id=existing_message_id)
            return {
                "thread_id": thread_id,
                "message_id": message_id,
                "thread_name": normalized_name,
                "thread_url": build_profile_card_thread_url(parent_id, thread_id),
                "created": False,
                "recreated": False,
                "parent_channel_id": parent_id,
            }
        except ProfileCardThreadRecreationRequired:
            return recreate_profile_card_thread(
                parent_id,
                normalized_name,
                starter_payload,
                previous_thread_id=thread_id,
            )

    create_payload = {
        "name": normalized_name,
        "auto_archive_duration": 10080,
        "message": starter_payload,
    }
    created = discord_post_json("/channels/{}/threads".format(parent_id), create_payload)
    if not isinstance(created, dict):
        raise RuntimeError("Discord profile thread create response is invalid")
    thread_id = sanitize_text(created.get("id", ""))
    if not thread_id:
        raise RuntimeError("Discord profile thread create returned no id")

    return {
        "thread_id": thread_id,
        "message_id": thread_id,
        "thread_name": normalized_name,
        "thread_url": build_profile_card_thread_url(parent_id, thread_id),
        "created": True,
        "recreated": False,
        "parent_channel_id": parent_id,
    }


def sync_profile_card_to_discord(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    discord_user_id = sanitize_text(payload.get("user_id", ""))
    if not discord_user_id or not discord_user_id.isdigit():
        raise ValueError("user_id is required")

    if not parse_bool_text(payload.get("profile_thread_enabled", ""), default=False):
        return disable_profile_card_thread(payload)

    parent_channel_id = sanitize_text(payload.get("thread_channel_id", "") or DISCORD_THREAD_CHANNEL_ID)
    display_name = truncate_text(sanitize_text(payload.get("display_name", "")) or "user-{}".format(discord_user_id), 100)
    workspace_update = {}
    workspace_error = ""
    try:
        workspace_update = ensure_profile_card_workspace(payload)
    except Exception as exc:
        workspace_error = sanitize_text(str(exc))

    render_payload = dict(payload)
    if workspace_update:
        render_payload.update(workspace_update)

    starter_payload = build_profile_card_message_payload(render_payload)
    thread_result = ensure_profile_card_thread(
        parent_channel_id,
        display_name,
        starter_payload,
        existing_thread_id=payload.get("thread_id", ""),
        existing_message_id=payload.get("message_id", ""),
    )

    note = "プロフィールカードを作成しました。" if bool(thread_result.get("created", False)) else "プロフィールカードを更新しました。"
    if bool(thread_result.get("recreated", False)):
        note = "プロフィールカードを差し替えて preview を更新しました。"
    if workspace_error:
        note = "{} ワークスペース同期は失敗しました: {}".format(note, workspace_error)

    return {
        "ok": True,
        "user_id": discord_user_id,
        "thread_id": thread_result.get("thread_id", ""),
        "message_id": thread_result.get("message_id", ""),
        "thread_name": thread_result.get("thread_name", ""),
        "thread_url": thread_result.get("thread_url", ""),
        "created": bool(thread_result.get("created", False)),
        "workspace_category_id": workspace_update.get("workspace_category_id", render_payload.get("workspace_category_id", "")),
        "workspace_category_name": workspace_update.get("workspace_category_name", render_payload.get("workspace_category_name", "")),
        "workspace_text_channel_id": workspace_update.get("workspace_text_channel_id", render_payload.get("workspace_text_channel_id", "")),
        "workspace_text_channel_name": workspace_update.get("workspace_text_channel_name", render_payload.get("workspace_text_channel_name", "")),
        "workspace_voice_channel_id": workspace_update.get("workspace_voice_channel_id", render_payload.get("workspace_voice_channel_id", "")),
        "workspace_voice_channel_name": workspace_update.get("workspace_voice_channel_name", render_payload.get("workspace_voice_channel_name", "")),
        "note": note,
    }


async def send_profile_card_ephemeral(interaction, message):
    text = truncate_text(sanitize_text(message), 1900)
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


def parse_profile_card_action_owner_id(custom_id, prefix):
    custom_text = sanitize_text(custom_id)
    expected_prefix = sanitize_text(prefix)
    if not custom_text or not expected_prefix:
        return ""
    marker = expected_prefix + ":"
    if not custom_text.startswith(marker):
        return ""
    return normalize_discord_user_id(custom_text[len(marker):])


def can_manage_profile_card_interaction(interaction, owner_user_id=""):
    owner_text = normalize_discord_user_id(owner_user_id)
    member = getattr(interaction, "user", None)
    if owner_text and getattr(member, "id", None) is not None and str(member.id) == owner_text:
        return True
    return is_discord_admin_interaction(interaction)


def format_profile_card_visibility_input(value):
    return "public" if sanitize_text(value).lower() == "public" else "private"


def format_profile_card_bool_input(value, default=False):
    return "on" if parse_bool_text(value, default=default) else "off"


async def submit_profile_card_modal_update(interaction, owner_user_id, section, payload, success_message):
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass

    try:
        result = await asyncio.to_thread(update_wordpress_profile_from_discord, owner_user_id, section, payload)
        message = sanitize_text(result.get("note", "")) or sanitize_text(success_message)
        await interaction.followup.send("✅ {}".format(truncate_text(message, 1900)), ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(
            "❌ 保存に失敗しました: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
            ephemeral=True,
        )


async def submit_profile_card_workspace_modal_update(interaction, owner_user_id, current_state, text_channel_name, voice_channel_name):
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass

    try:
        result = await asyncio.to_thread(
            create_or_update_profile_card_workspace_channels,
            owner_user_id,
            current_state,
            str(text_channel_name or "").strip(),
            str(voice_channel_name or "").strip(),
        )
        messages = []
        for line in result.get("results", []) if isinstance(result.get("results", []), list) else []:
            message = truncate_text(sanitize_text(line), 300)
            if message:
                messages.append(message)
        sync_result = result.get("sync_result", {}) if isinstance(result.get("sync_result"), dict) else {}
        sync_note = truncate_text(sanitize_text(sync_result.get("note", "")), 500)
        if sync_note:
            messages.append(sync_note)
        response_text = "\n".join(messages) if messages else "プロフィール用チャンネルを更新しました。"
        await interaction.followup.send("✅ {}".format(truncate_text(response_text, 1900)), ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(
            "❌ チャンネル作成に失敗しました: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
            ephemeral=True,
        )


if discord is not None:
    class ProfileCardModalBase(discord.ui.Modal):
        def __init__(self, owner_user_id, current_state):
            super().__init__()
            self.owner_user_id = normalize_discord_user_id(owner_user_id)
            self.current_state = current_state if isinstance(current_state, dict) else {}


    class ProfileCardEditModal(ProfileCardModalBase, title="プロフィール本文編集"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            self.summary = discord.ui.TextInput(
                label="自己紹介 / Summary",
                default=truncate_text(sanitize_text(self.current_state.get("intro_card_summary", "")), 280),
                placeholder="例: 夜21時以降に遊んでいます。VC歓迎です。",
                required=False,
                max_length=280,
                style=discord.TextStyle.paragraph,
            )
            self.add_item(self.summary)

        async def on_submit(self, interaction):
            await submit_profile_card_modal_update(
                interaction,
                self.owner_user_id,
                "profile",
                {"summary": str(self.summary.value or "").strip()},
                "プロフィール本文を更新しました。",
            )


    class ProfileCardDisplayModal(ProfileCardModalBase, title="公開設定"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            contact_preferences = self.current_state.get("contact_preferences", {}) if isinstance(self.current_state.get("contact_preferences", {}), dict) else {}
            self.visibility = discord.ui.TextInput(
                label="プロフィール公開",
                default=format_profile_card_visibility_input(self.current_state.get("intro_card_visibility", "private")),
                placeholder="public で公開 / private で非公開",
                required=True,
                max_length=10,
            )
            self.thread_enabled = discord.ui.TextInput(
                label="専用スレッド作成",
                default=format_profile_card_bool_input(self.current_state.get("profile_thread_enabled", False)),
                placeholder="on で作成継続 / off で停止",
                required=True,
                max_length=10,
            )
            self.dm_ok = discord.ui.TextInput(
                label="DM連絡",
                default=format_profile_card_bool_input(contact_preferences.get("dm_ok", False)),
                placeholder="on で許可 / off で非表示",
                required=True,
                max_length=10,
            )
            self.friend_request_ok = discord.ui.TextInput(
                label="フレンド申請",
                default=format_profile_card_bool_input(contact_preferences.get("friend_request_ok", False)),
                placeholder="on で許可 / off で非表示",
                required=True,
                max_length=10,
            )
            self.voice_request_ok = discord.ui.TextInput(
                label="通話招待",
                default=format_profile_card_bool_input(contact_preferences.get("voice_request_ok", False)),
                placeholder="on で許可 / off で非表示",
                required=True,
                max_length=10,
            )
            self.add_item(self.visibility)
            self.add_item(self.thread_enabled)
            self.add_item(self.dm_ok)
            self.add_item(self.friend_request_ok)
            self.add_item(self.voice_request_ok)

        async def on_submit(self, interaction):
            await submit_profile_card_modal_update(
                interaction,
                self.owner_user_id,
                "display",
                {
                    "visibility": str(self.visibility.value or "").strip(),
                    "thread_enabled": str(self.thread_enabled.value or "").strip(),
                    "dm_ok": str(self.dm_ok.value or "").strip(),
                    "friend_request_ok": str(self.friend_request_ok.value or "").strip(),
                    "voice_request_ok": str(self.voice_request_ok.value or "").strip(),
                },
                "表示設定を更新しました。",
            )


    class ProfileCardServerModal(ProfileCardModalBase, title="招待サーバー設定"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            self.server_name = discord.ui.TextInput(
                label="募集サーバー名",
                default=truncate_text(sanitize_text(self.current_state.get("owned_discord_server_name", "")), 80),
                placeholder="例: 7DAYSTODIE.JP 交流サーバー",
                required=False,
                max_length=80,
            )
            self.invite_url = discord.ui.TextInput(
                label="招待URL",
                default=truncate_text(sanitize_text(self.current_state.get("owned_discord_server_invite_url", "")), 1000),
                placeholder="https://discord.gg/... 未入力でリンク削除",
                required=False,
                max_length=1000,
            )
            self.guild_id = discord.ui.TextInput(
                label="Guild ID",
                default=truncate_text(sanitize_text(self.current_state.get("owned_discord_server_guild_id", "")), 32),
                placeholder="招待先サーバーの Guild ID",
                required=False,
                max_length=32,
            )
            self.server_description = discord.ui.TextInput(
                label="サーバー紹介文",
                default=truncate_text(str(self.current_state.get("owned_discord_server_description", "") or "").strip(), 1000),
                placeholder="サーバーの雰囲気や募集内容を記入。空欄でクリア。",
                required=False,
                max_length=1000,
                style=discord.TextStyle.paragraph,
            )
            self.add_item(self.server_name)
            self.add_item(self.invite_url)
            self.add_item(self.guild_id)
            self.add_item(self.server_description)

        async def on_submit(self, interaction):
            await submit_profile_card_modal_update(
                interaction,
                self.owner_user_id,
                "server",
                {
                    "server_name": str(self.server_name.value or "").strip(),
                    "invite_url": str(self.invite_url.value or "").strip(),
                    "guild_id": str(self.guild_id.value or "").strip(),
                    "server_description": str(self.server_description.value or "").strip(),
                },
                "Discordサーバー設定を更新しました。",
            )


    class ProfileCardImageModal(ProfileCardModalBase, title="プロフィール画像"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            self.image_url = discord.ui.TextInput(
                label="プロフィール画像URL",
                default=truncate_text(sanitize_text(self.current_state.get("image_url", "")), 1000),
                placeholder="プロフィールカードに表示する画像 URL。空欄で削除。",
                required=False,
                max_length=1000,
            )
            self.add_item(self.image_url)

        async def on_submit(self, interaction):
            await submit_profile_card_modal_update(
                interaction,
                self.owner_user_id,
                "image",
                {"image_url": str(self.image_url.value or "").strip()},
                "画像設定を更新しました。",
            )


    class ProfileCardTagsModal(ProfileCardModalBase, title="募集タグ"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            current_tags = normalize_profile_card_tags(self.current_state.get("tags"))
            self.tags = discord.ui.TextInput(
                label="タグ一覧",
                default=truncate_text(", ".join(current_tags), 200),
                placeholder="例: PVE, VC歓迎, 夜型",
                required=False,
                max_length=200,
            )
            self.add_item(self.tags)

        async def on_submit(self, interaction):
            await submit_profile_card_modal_update(
                interaction,
                self.owner_user_id,
                "tags",
                {"tags": str(self.tags.value or "").strip()},
                "タグ設定を更新しました。",
            )


    class ProfileCardWorkspaceModal(ProfileCardModalBase, title="チャンネル作成"):
        def __init__(self, owner_user_id, current_state):
            super().__init__(owner_user_id, current_state)
            self.text_channel_name = discord.ui.TextInput(
                label="テキストチャンネル名",
                default=truncate_text(sanitize_text(self.current_state.get("workspace_text_channel_name", "")), 100),
                placeholder="例: kojyuro-chat",
                required=False,
                max_length=100,
            )
            self.voice_channel_name = discord.ui.TextInput(
                label="ボイスチャンネル名",
                default=truncate_text(sanitize_text(self.current_state.get("workspace_voice_channel_name", "")), 100),
                placeholder="例: kojyuro-voice",
                required=False,
                max_length=100,
            )
            self.add_item(self.text_channel_name)
            self.add_item(self.voice_channel_name)

        async def on_submit(self, interaction):
            await submit_profile_card_workspace_modal_update(
                interaction,
                self.owner_user_id,
                self.current_state,
                self.text_channel_name.value,
                self.voice_channel_name.value,
            )


    class ChannelRepostEditModal(discord.ui.Modal, title="Embed投稿編集"):
        def __init__(self, channel_id, message_id, embed_payload):
            super().__init__()
            self.channel_id = sanitize_text(channel_id)
            self.message_id = sanitize_text(message_id)
            self.embed_payload = dict(embed_payload) if isinstance(embed_payload, dict) else {}

            current_title = sanitize_text(self.embed_payload.get("title", ""))
            current_description = normalize_discord_message_text(self.embed_payload.get("description", ""))
            image_block = self.embed_payload.get("image", {}) if isinstance(self.embed_payload.get("image", {}), dict) else {}
            current_image_url = sanitize_text(image_block.get("url", ""))
            if not current_image_url:
                current_image_url = extract_first_image_url_from_embed_fields(self.embed_payload)
            self.embed_title = discord.ui.TextInput(
                label="タイトル",
                default=truncate_text(current_title, 256),
                placeholder="空欄でタイトルなし",
                required=False,
                max_length=256,
            )
            self.embed_description_default = truncate_text(current_description, 4000)
            self.embed_description_original = current_description
            self.embed_description = discord.ui.TextInput(
                label="本文",
                default=self.embed_description_default,
                placeholder="空欄で本文なし",
                required=False,
                max_length=4000,
                style=discord.TextStyle.paragraph,
            )
            self.image_url = discord.ui.TextInput(
                label="画像URL",
                default=truncate_text(current_image_url, 1000),
                placeholder="https://... 空欄で画像を削除",
                required=False,
                max_length=1000,
            )
            self.add_item(self.embed_title)
            self.add_item(self.embed_description)
            self.add_item(self.image_url)

        async def on_submit(self, interaction):
            if not is_discord_admin_interaction(interaction):
                await send_profile_card_ephemeral(interaction, "❌ Discord 管理者のみ投稿内容を編集できます。")
                return

            title = str(self.embed_title.value or "")
            description = str(self.embed_description.value or "")
            if len(self.embed_description_original) > 4000 and description == self.embed_description_default:
                description = self.embed_description_original
            image_url = str(self.image_url.value or "").strip()
            if image_url and not is_http_url(image_url):
                await send_profile_card_ephemeral(interaction, "❌ http / https の画像URLを指定してください。")
                return

            try:
                await interaction.response.defer(ephemeral=True, thinking=True)
            except Exception:
                pass

            try:
                await asyncio.to_thread(
                    update_channel_repost_message_embed,
                    self.channel_id,
                    self.message_id,
                    self.embed_payload,
                    title,
                    description,
                    image_url,
                )
                await interaction.followup.send("✅ 投稿内容を更新しました。", ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(
                    "❌ 投稿内容の更新に失敗しました: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
                    ephemeral=True,
                )
else:
    ProfileCardEditModal = None
    ProfileCardDisplayModal = None
    ProfileCardServerModal = None
    ProfileCardImageModal = None
    ProfileCardTagsModal = None
    ProfileCardWorkspaceModal = None
    ChannelRepostEditModal = None


async def open_profile_card_modal_interaction(interaction, owner_user_id, modal_class):
    if discord is None or modal_class is None:
        await send_profile_card_ephemeral(interaction, "❌ Discord モーダルを利用できません。")
        return

    resolved_owner_id = normalize_discord_user_id(owner_user_id)
    if not resolved_owner_id:
        await send_profile_card_ephemeral(interaction, "❌ 作成者情報を取得できませんでした。")
        return
    if not can_manage_profile_card_interaction(interaction, resolved_owner_id):
        await send_profile_card_ephemeral(interaction, "❌ 作成者または管理者のみ利用できます。")
        return

    try:
        current_state = await asyncio.to_thread(fetch_wordpress_profile_member_status, resolved_owner_id)
    except Exception as exc:
        await send_profile_card_ephemeral(
            interaction,
            "❌ 現在のプロフィール設定を取得できませんでした: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
        )
        return

    if not bool(current_state.get("user_exists", False)):
        await send_profile_card_ephemeral(interaction, "❌ WordPress 側の連携ユーザーが見つかりません。")
        return

    try:
        await interaction.response.send_modal(modal_class(resolved_owner_id, current_state))
    except Exception as exc:
        await send_profile_card_ephemeral(
            interaction,
            "❌ モーダルを開けませんでした: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
        )


async def handle_profile_card_edit_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_EDIT_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardEditModal)


async def handle_profile_card_invite_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_INVITE_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardServerModal)


async def handle_profile_card_image_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_IMAGE_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardImageModal)


async def handle_profile_card_tag_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_TAG_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardTagsModal)


async def handle_profile_card_channel_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_CHANNEL_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardDisplayModal)


async def handle_profile_card_workspace_interaction(interaction):
    data = getattr(interaction, "data", {}) or {}
    owner_user_id = parse_profile_card_action_owner_id(str(data.get("custom_id", "") or ""), PROFILE_CARD_WORKSPACE_BUTTON_PREFIX)
    await open_profile_card_modal_interaction(interaction, owner_user_id, ProfileCardWorkspaceModal)


async def handle_profile_card_thread_toggle_interaction(interaction):
    thread = getattr(interaction, "channel", None)
    member = getattr(interaction, "user", None)
    if discord is None or not isinstance(thread, discord.Thread) or not isinstance(member, discord.Member):
        await send_profile_card_ephemeral(interaction, "❌ スレッド情報を取得できませんでした。")
        return

    await interaction.response.defer(ephemeral=True)

    joined = False
    try:
        await thread.fetch_member(member.id)
        joined = True
    except discord.NotFound:
        joined = False
    except Exception as exc:
        await interaction.followup.send("❌ 参加状態の確認に失敗しました: {}".format(exc), ephemeral=True)
        return

    try:
        if joined:
            await thread.remove_user(member)
            message = "✅ 退室しました。{} のスレッド参加を解除しました。".format(thread.name)
        else:
            await thread.add_user(member)
            message = "✅ 入室しました。{} のスレッド参加を追加しました。".format(thread.name)
    except discord.Forbidden:
        message = "❌ スレッド参加の更新に失敗しました。Bot の権限を確認してください。"
    except Exception as exc:
        message = "❌ スレッド参加の更新に失敗しました: {}".format(exc)

    await interaction.followup.send(truncate_text(message, 1900), ephemeral=True)


async def handle_profile_card_thread_delete_interaction(interaction):
    thread = getattr(interaction, "channel", None)
    member = getattr(interaction, "user", None)
    data = getattr(interaction, "data", {}) or {}
    custom_id = str(data.get("custom_id", "") or "")
    owner_user_id = normalize_discord_user_id(custom_id.rsplit(":", 1)[-1])

    if discord is None or not isinstance(thread, discord.Thread) or not isinstance(member, discord.Member):
        await send_profile_card_ephemeral(interaction, "❌ スレッド情報を取得できませんでした。")
        return

    if owner_user_id and str(member.id) != owner_user_id and not is_discord_admin_interaction(interaction):
        await send_profile_card_ephemeral(interaction, "❌ 作成者または管理者のみスレッドを終了できます。")
        return

    await interaction.response.defer(ephemeral=True)
    try:
        await thread.edit(archived=True, reason="profile thread archived by owner")
        message = "✅ スレッドをアーカイブしました。再作成を止めるには WordPress 側の Discord専用スレッド UI も OFF にしてください。"
    except discord.Forbidden:
        message = "❌ スレッドのアーカイブに失敗しました。Bot の権限を確認してください。"
    except Exception as exc:
        message = "❌ スレッドのアーカイブに失敗しました: {}".format(exc)

    await interaction.followup.send(truncate_text(message, 1900), ephemeral=True)


async def handle_channel_repost_edit_interaction(interaction):
    message = getattr(interaction, "message", None)
    if message is None or not getattr(message, "embeds", None):
        await send_profile_card_ephemeral(interaction, "❌ 編集対象の embed が見つかりません。")
        return
    if discord is None or ChannelRepostEditModal is None:
        await send_profile_card_ephemeral(interaction, "❌ Discord モーダルを利用できません。")
        return
    if not is_discord_admin_interaction(interaction):
        await send_profile_card_ephemeral(interaction, "❌ Discord 管理者のみ投稿内容を編集できます。")
        return

    channel_id = str(getattr(getattr(message, "channel", None), "id", "") or "")
    message_id = str(getattr(message, "id", "") or "")
    if not channel_id.isdigit() or not message_id.isdigit():
        await send_profile_card_ephemeral(interaction, "❌ 編集対象メッセージの ID を取得できませんでした。")
        return

    data = getattr(interaction, "data", {}) or {}
    custom_id = str(data.get("custom_id", "") or "")
    if custom_id == CHANNEL_REPOST_LEGACY_IMAGE_BUTTON_CUSTOM_ID:
        try:
            await asyncio.to_thread(promote_channel_repost_legacy_button, channel_id, message_id)
        except Exception:
            pass

    try:
        await interaction.response.send_modal(ChannelRepostEditModal(channel_id, message_id, message.embeds[0].to_dict()))
    except Exception as exc:
        await send_profile_card_ephemeral(
            interaction,
            "❌ 投稿編集モーダルを開けませんでした: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
        )


def ensure_discord_media_tag_id(channel_id, tag_name):
    media_channel_id = sanitize_text(channel_id)
    normalized_tag = normalize_nexus_tag_name(tag_name)
    if not media_channel_id or not normalized_tag:
        return ""

    channel_data = discord_request_json("/channels/{}".format(media_channel_id))
    if not isinstance(channel_data, dict):
        return ""
    if int(channel_data.get("type", 0) or 0) not in (15, 16):
        return ""

    available_tags = channel_data.get("available_tags", []) if isinstance(channel_data.get("available_tags"), list) else []
    for tag in available_tags:
        if not isinstance(tag, dict):
            continue
        if normalize_nexus_tag_name(tag.get("name", "")) == normalized_tag:
            return str(tag.get("id", "") or "")

    if len(available_tags) >= 20:
        return ""

    updated_tags = []
    for tag in available_tags:
        if not isinstance(tag, dict):
            continue
        item = {
            "id": str(tag.get("id", "") or ""),
            "name": normalize_nexus_tag_name(tag.get("name", ""), fallback="tag"),
            "moderated": bool(tag.get("moderated", False)),
        }
        emoji_id = tag.get("emoji_id")
        emoji_name = sanitize_text(tag.get("emoji_name", ""))
        if emoji_id not in (None, ""):
            item["emoji_id"] = str(emoji_id)
        elif emoji_name:
            item["emoji_name"] = emoji_name
        updated_tags.append(item)

    updated_tags.append({"name": normalized_tag, "moderated": False})
    patched = discord_patch_json("/channels/{}".format(media_channel_id), {"available_tags": updated_tags})
    patched_tags = patched.get("available_tags", []) if isinstance(patched, dict) else []
    for tag in patched_tags:
        if not isinstance(tag, dict):
            continue
        if normalize_nexus_tag_name(tag.get("name", "")) == normalized_tag:
            return str(tag.get("id", "") or "")
    return ""


def resolve_discord_media_tag_ids(channel_id, tag_names):
    media_channel_id = sanitize_text(channel_id)
    if not media_channel_id:
        return []

    tag_ids = []
    for raw_name in tag_names or []:
        name = sanitize_text(raw_name)
        if not name:
            continue
        tag_id = ensure_discord_media_tag_id(media_channel_id, name)
        if tag_id and tag_id not in tag_ids:
            tag_ids.append(tag_id)
    return tag_ids[:5]


def update_discord_media_thread_tags(parent_channel_id, thread_id, required_tag_names=None, append_tag_names=None, preserve_current_tag_names=None):
    media_channel_id = sanitize_text(parent_channel_id)
    thread_text = sanitize_text(thread_id)
    if not media_channel_id or not thread_text:
        return []

    required_tag_names = normalize_nexus_tag_names(required_tag_names or [], fallback="", limit=5)
    append_tag_names = normalize_nexus_tag_names(append_tag_names or [], fallback="", limit=5)
    preserve_names = set()
    for raw_name in preserve_current_tag_names or []:
        name = normalize_nexus_tag_name(raw_name, fallback="")
        if name:
            preserve_names.add(name)

    channel_data = discord_request_json("/channels/{}".format(media_channel_id))
    available_tags = channel_data.get("available_tags", []) if isinstance(channel_data, dict) else []
    id_to_name = {}
    for tag in available_tags:
        if not isinstance(tag, dict):
            continue
        tag_id = str(tag.get("id", "") or "")
        if not tag_id:
            continue
        id_to_name[tag_id] = normalize_nexus_tag_name(tag.get("name", ""), fallback="")

    current_thread = discord_request_json("/channels/{}".format(thread_text))
    current_ids = [str(value) for value in current_thread.get("applied_tags", []) if str(value).strip()] if isinstance(current_thread, dict) else []
    target_ids = resolve_discord_media_tag_ids(media_channel_id, list(required_tag_names) + list(append_tag_names))

    preserved_ids = []
    for current_id in current_ids:
        current_name = id_to_name.get(current_id, "")
        if current_name in preserve_names and current_id not in preserved_ids:
            preserved_ids.append(current_id)

    if preserved_ids:
        base_ids = [tag_id for tag_id in target_ids if tag_id not in preserved_ids]
        available_slots = max(0, 5 - len(preserved_ids))
        final_ids = (base_ids[:available_slots] + preserved_ids)[:5]
    else:
        final_ids = target_ids[:5]

    if set(current_ids) != set(final_ids):
        discord_patch_json("/channels/{}".format(thread_text), {"applied_tags": final_ids})
    return final_ids


def add_favorite_tag_to_media_thread(parent_channel_id, thread_id, required_tag_name="", required_tag_names=None):
    required_names = normalize_nexus_tag_names(required_tag_names or [], fallback="", limit=4)
    if sanitize_text(required_tag_name):
        required_names = normalize_nexus_tag_names(required_names + [required_tag_name], fallback="", limit=4)
    return update_discord_media_thread_tags(
        parent_channel_id,
        thread_id,
        required_tag_names=required_names,
        append_tag_names=[FAVORITE_MEDIA_TAG_NAME],
        preserve_current_tag_names=[FAVORITE_MEDIA_TAG_NAME],
    )


def fetch_wordpress_nexus_categories():
    if not WP_NEXUS_WATCH_TOKEN:
        raise RuntimeError("WP_NEXUS_WATCH_TOKEN is not set")

    categories = []
    seen = set()

    if WP_NEXUS_CATEGORIES_ENDPOINT:
        categories_url = "{}{}ts={}".format(
            WP_NEXUS_CATEGORIES_ENDPOINT,
            "&" if "?" in WP_NEXUS_CATEGORIES_ENDPOINT else "?",
            int(time.time()),
        )
        headers = build_wordpress_watch_headers(WP_NEXUS_WATCH_TOKEN, WP_NEXUS_CATEGORIES_ENDPOINT)
        data = fetch_json_request(categories_url, headers=headers, timeout=WP_BRIDGE_TIMEOUT)
        rows = data.get("categories", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            raise RuntimeError("WP nexus categories response is invalid")

        for row in rows:
            if not isinstance(row, dict):
                continue
            name = normalize_nexus_tag_name(row.get("name", ""), fallback="")
            if not name or name in seen:
                continue
            seen.add(name)
            categories.append(name)

    if not WP_NEXUS_WATCH_ENDPOINT:
        return categories

    headers = build_wordpress_watch_headers(WP_NEXUS_WATCH_TOKEN, WP_NEXUS_WATCH_ENDPOINT)
    watch_data = fetch_json_request(WP_NEXUS_WATCH_ENDPOINT, headers=headers, timeout=WP_BRIDGE_TIMEOUT)
    watch_rows = watch_data.get("items", []) if isinstance(watch_data, dict) else []
    if not isinstance(watch_rows, list):
        raise RuntimeError("WP nexus watch response is invalid")

    for row in watch_rows:
        if not isinstance(row, dict):
            continue
        name = normalize_nexus_tag_name(row.get("category", ""), fallback="")
        if not name or name in seen:
            tag_rows = row.get("tags_ja", []) if isinstance(row.get("tags_ja"), list) else []
            for tag_name in tag_rows:
                normalized_tag = normalize_nexus_tag_name(tag_name, fallback="")
                if not normalized_tag or normalized_tag in seen:
                    continue
                seen.add(normalized_tag)
                categories.append(normalized_tag)
            continue
        seen.add(name)
        categories.append(name)

    return categories


def initialize_nexus_media_tags():
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return {"ok": True, "enabled": False, "created": [], "existing": [], "skipped": []}

    ordered_names = []
    seen = set()
    for raw_name in (DISCORD_NEXUS_NOTIFY_TAG_NAME, FAVORITE_MEDIA_TAG_NAME, "その他"):
        name = normalize_nexus_tag_name(raw_name, fallback="")
        if name and name not in seen:
            seen.add(name)
            ordered_names.append(name)

    categories = fetch_wordpress_nexus_categories()
    for raw_name in categories:
        name = normalize_nexus_tag_name(raw_name, fallback="")
        if name and name not in seen:
            seen.add(name)
            ordered_names.append(name)

    existing = []
    created = []
    skipped = []
    for name in ordered_names:
        before = discord_request_json("/channels/{}".format(media_channel_id))
        before_tags = before.get("available_tags", []) if isinstance(before, dict) else []
        before_id = ""
        for tag in before_tags:
            if not isinstance(tag, dict):
                continue
            if normalize_nexus_tag_name(tag.get("name", ""), fallback="") == name:
                before_id = str(tag.get("id", "") or "")
                break

        tag_id = ensure_discord_media_tag_id(media_channel_id, name)
        if tag_id:
            if before_id:
                existing.append(name)
            else:
                created.append(name)
        else:
            skipped.append(name)

    return {
        "ok": True,
        "enabled": True,
        "created": created,
        "existing": existing,
        "skipped": skipped,
        "total_requested": len(ordered_names),
    }


def initialize_twitch_media_tags():
    media_channel_id = sanitize_text(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return {"ok": True, "enabled": False, "created": [], "existing": [], "skipped": []}

    return {
        "ok": True,
        "enabled": False,
        "created": [],
        "existing": [],
        "skipped": [],
        "reason": "twitch media forum tags are disabled",
    }


def initialize_twitter_media_tags():
    media_channel_id = sanitize_text(DISCORD_TWITTER_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return {"ok": True, "enabled": False, "created": [], "existing": [], "skipped": []}

    return {
        "ok": True,
        "enabled": False,
        "created": [],
        "existing": [],
        "skipped": [],
        "reason": "twitter media forum tags are disabled",
    }


def ensure_nexus_media_thread(parent_channel_id, thread_name, starter_payload, preferred_tag_name="", fallback_tag_name="", required_tag_names=None):
    parent_id = sanitize_text(parent_channel_id)
    normalized_name = normalize_nexus_thread_name(thread_name, "その他")
    if not parent_id or not parent_id.isdigit():
        raise RuntimeError("DISCORD_NEXUS_MEDIA_CHANNEL_ID is not set")

    required_tag_names = normalize_nexus_tag_names(
        list(required_tag_names or []) + [preferred_tag_name, fallback_tag_name],
        fallback="",
        limit=5,
    )
    tag_ids = resolve_discord_media_tag_ids(parent_id, required_tag_names)

    existing = find_discord_thread_by_name(parent_id, normalized_name)
    if isinstance(existing, dict):
        ensure_discord_thread_unarchived(existing)
        thread_id = sanitize_text(existing.get("id", ""))
        try:
            update_discord_media_thread_tags(
                parent_id,
                thread_id,
                required_tag_names=required_tag_names,
                preserve_current_tag_names=[FAVORITE_MEDIA_TAG_NAME],
            )
        except Exception:
            pass
        return {"thread_id": thread_id, "created": False}

    create_payload = {
        "name": normalized_name,
        "auto_archive_duration": 10080,
        "message": starter_payload,
    }
    if tag_ids:
        create_payload["applied_tags"] = tag_ids[:5]

    created = discord_post_json("/channels/{}/threads".format(parent_id), create_payload)
    if not isinstance(created, dict):
        raise RuntimeError("Discord media thread create response is invalid")
    thread_id = sanitize_text(created.get("id", ""))
    if not thread_id:
        raise RuntimeError("Discord media thread create returned no id")
    return {"thread_id": thread_id, "created": True}


def post_message_to_media_thread(parent_channel_id, thread_name, message_payload, preferred_tag_name="", fallback_tag_name="", required_tag_names=None):
    thread_result = ensure_nexus_media_thread(
        parent_channel_id,
        thread_name,
        message_payload,
        preferred_tag_name=preferred_tag_name,
        fallback_tag_name=fallback_tag_name,
    required_tag_names=required_tag_names,
    )
    thread_id = sanitize_text(thread_result.get("thread_id", ""))
    created = bool(thread_result.get("created", False))

    if created:
        message_id = thread_id
    else:
        created_message = discord_post_json("/channels/{}/messages".format(thread_id), message_payload)
        if not isinstance(created_message, dict):
            raise RuntimeError("Discord thread message response is invalid")
        message_id = sanitize_text(created_message.get("id", ""))
        try:
            update_discord_thread_starter_message(thread_id, message_payload)
        except Exception:
            pass

    return {
        "thread_id": thread_id,
        "message_id": message_id,
        "thread_name": normalize_nexus_thread_name(thread_name, "thread"),
        "created": created,
        "jump_url": build_nexus_jump_url(thread_id, message_id),
    }


def ensure_nexus_notification_thread():
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return ""

    starter_payload = {
        "content": "このスレッドへ Nexus MOD の新着通知を投稿します。作成者別スレッドへも自動投稿され、投稿タグを更新します。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    }
    result = ensure_nexus_media_thread(
        media_channel_id,
        DISCORD_NEXUS_NOTIFY_THREAD_NAME,
        starter_payload,
        preferred_tag_name=DISCORD_NEXUS_NOTIFY_TAG_NAME,
        fallback_tag_name="新着通知",
    )
    return str(result.get("thread_id", "") or "")


def post_nexus_notification_message(item, payload):
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if media_channel_id:
        thread_id = ensure_nexus_notification_thread()
        if not thread_id:
            raise RuntimeError("Nexus notification thread could not be resolved")
        result = discord_post_json("/channels/{}/messages".format(thread_id), payload)
        try:
            update_discord_thread_starter_message(thread_id, payload)
        except Exception:
            pass
        try:
            save_nexus_message_to_creator_thread(
                payload.get("content", ""),
                (payload.get("embeds", [{}])[0] if isinstance(payload.get("embeds"), list) and payload.get("embeds") else {}),
                payload.get("components", []),
            )
        except Exception:
            pass
        return result
    return discord_post_json("/channels/{}/messages".format(DISCORD_NEXUS_NOTIFY_CHANNEL_ID), payload)


def save_nexus_message_to_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_NEXUS_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_nexus_embed_creator_name(source_embed_payload)
    tag_names = get_nexus_embed_tag_names(source_embed_payload, limit=4)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_nexus_open_components(link_url)
    if components:
        message_payload["components"] = components

    result = post_message_to_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
        required_tag_names=tag_names,
    )
    result["thread_name"] = creator_name
    return result


def favorite_nexus_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_NEXUS_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_nexus_embed_creator_name(source_embed_payload)
    tag_names = get_nexus_embed_tag_names(source_embed_payload, limit=4)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_nexus_open_components(link_url)
    if components:
        message_payload["components"] = components

    thread_result = ensure_nexus_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
        required_tag_names=tag_names,
    )
    thread_id = sanitize_text(thread_result.get("thread_id", ""))
    add_favorite_tag_to_media_thread(media_channel_id, thread_id, required_tag_names=tag_names)
    return {
        "thread_id": thread_id,
        "message_id": thread_id,
        "thread_name": creator_name,
        "created": bool(thread_result.get("created", False)),
        "jump_url": build_nexus_jump_url(thread_id, thread_id),
    }


async def handle_nexus_favorite_interaction(interaction):
    message = getattr(interaction, "message", None)
    if message is None or not getattr(message, "embeds", None):
        if interaction.response.is_done():
            await interaction.followup.send("保存対象の埋め込みが見つかりません。", ephemeral=True)
        else:
            await interaction.response.send_message("保存対象の埋め込みが見つかりません。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    source_embed = message.embeds[0].to_dict()
    source_content = truncate_text(message.content or "", 1900)
    source_components = list(getattr(message, "components", []) or [])

    try:
        result = await asyncio.to_thread(
            favorite_nexus_creator_thread,
            source_content,
            source_embed,
            source_components,
        )
        thread_name = sanitize_text(result.get("thread_name", "作成者不明"))
        jump_url = sanitize_text(result.get("jump_url", ""))
        text = "お気に入りへ追加しました: {}".format(thread_name)
        if jump_url:
            text += "\n{}".format(jump_url)
        await interaction.followup.send(text, ephemeral=True)
    except Exception as exc:
        await interaction.followup.send("お気に入り処理に失敗しました: {}".format(exc), ephemeral=True)


def rebucket_existing_nexus_messages_to_creator_threads(limit=100, before_message_id="", force=False, source_channel_id=""):
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_NEXUS_MEDIA_CHANNEL_ID is not set")

    source_channel_text = sanitize_text(source_channel_id)
    if source_channel_text:
        if not source_channel_text.isdigit():
            raise RuntimeError("source_channel_id is invalid")
    else:
        source_channel_text = ensure_nexus_notification_thread()

    if not source_channel_text:
        raise RuntimeError("Nexus notification source thread could not be resolved")

    requested_limit = max(1, min(int(limit or 100), 1000))
    before_text = sanitize_text(before_message_id)
    if before_text and not before_text.isdigit():
        raise RuntimeError("before_message_id is invalid")

    messages = []
    next_before_message_id = before_text
    remaining = requested_limit

    while remaining > 0:
        page_size = min(remaining, 100)
        page_rows = fetch_discord_channel_messages(
            source_channel_text,
            limit=page_size,
            before_message_id=next_before_message_id,
        )
        if not page_rows:
            next_before_message_id = ""
            break

        messages.extend(page_rows)
        remaining -= len(page_rows)

        oldest_message_id = sanitize_text(page_rows[-1].get("id", ""))
        if len(page_rows) < page_size or not oldest_message_id:
            next_before_message_id = ""
            break
        next_before_message_id = oldest_message_id

    messages.sort(key=lambda row: str(row.get("id", "0")))

    with nexus_notify_lock:
        processed_ids = set([str(value) for value in nexus_notify_state.get("rebucketed_message_ids", []) if str(value).strip()])

    scanned = 0
    sorted_count = 0
    skipped_processed = 0
    skipped_invalid = 0
    skipped_starter = 0
    target_thread_ids = set()

    try:
        for message in messages:
            scanned += 1
            message_id = sanitize_text(message.get("id", ""))
            if message_id == source_channel_text:
                skipped_starter += 1
                continue
            if (not force) and message_id in processed_ids:
                skipped_processed += 1
                continue

            embeds = message.get("embeds", []) if isinstance(message.get("embeds"), list) else []
            source_embed = embeds[0] if embeds and isinstance(embeds[0], dict) else None
            if not isinstance(source_embed, dict):
                skipped_invalid += 1
                continue

            result = save_nexus_message_to_creator_thread(
                sanitize_text(message.get("content", "")),
                source_embed,
                message.get("components", []),
            )
            processed_ids.add(message_id)
            sorted_count += 1

            thread_id = sanitize_text(result.get("thread_id", ""))
            if thread_id:
                target_thread_ids.add(thread_id)

        has_more = bool(next_before_message_id and len(messages) >= requested_limit)
        result = {
            "ok": True,
            "source_channel_id": source_channel_text,
            "requested_limit": requested_limit,
            "fetched_messages": len(messages),
            "scanned": scanned,
            "sorted": sorted_count,
            "skipped_processed": skipped_processed,
            "skipped_invalid": skipped_invalid,
            "skipped_starter": skipped_starter,
            "target_thread_count": len(target_thread_ids),
            "force": bool(force),
            "before_message_id": before_text,
            "next_before_message_id": next_before_message_id,
            "has_more": has_more,
            "updated_at": now_iso_utc(),
        }
        with nexus_notify_lock:
            nexus_notify_state["rebucketed_message_ids"] = list(processed_ids)[-5000:]
            nexus_notify_state["last_rebucket_run"] = result["updated_at"]
            nexus_notify_state["last_rebucket_error"] = ""
            nexus_notify_state["last_rebucket_scanned"] = scanned
            nexus_notify_state["last_rebucket_sorted"] = sorted_count
        save_nexus_notify_state()
        return result
    except Exception as exc:
        with nexus_notify_lock:
            nexus_notify_state["last_rebucket_run"] = now_iso_utc()
            nexus_notify_state["last_rebucket_error"] = str(exc)
            nexus_notify_state["last_rebucket_scanned"] = scanned
            nexus_notify_state["last_rebucket_sorted"] = sorted_count
        save_nexus_notify_state()
        raise


def retag_existing_nexus_creator_threads(limit=200):
    media_channel_id = sanitize_text(DISCORD_NEXUS_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_NEXUS_MEDIA_CHANNEL_ID is not set")

    max_threads = max(1, min(int(limit or 200), 500))
    notify_thread_id = ensure_nexus_notification_thread()

    channel_data = discord_request_json("/channels/{}".format(media_channel_id))
    available_tags = channel_data.get("available_tags", []) if isinstance(channel_data, dict) else []
    skip_names = set()
    for tag in available_tags:
        if not isinstance(tag, dict):
            continue
        tag_name = normalize_nexus_thread_name(tag.get("name", ""), "")
        if tag_name:
            skip_names.add(tag_name)

    notify_thread_name = normalize_nexus_thread_name(DISCORD_NEXUS_NOTIFY_THREAD_NAME, "")
    if notify_thread_name:
        skip_names.add(notify_thread_name)

    scanned = 0
    changed = 0
    skipped_notify = 0
    skipped_tag_threads = 0
    skipped_invalid = 0
    errors = []

    for thread_payload in list_discord_threads_for_parent(media_channel_id):
        thread_id = sanitize_text(thread_payload.get("id", ""))
        thread_name = normalize_nexus_thread_name(thread_payload.get("name", ""), "")
        if not thread_id or not thread_name:
            continue
        if thread_id == notify_thread_id:
            skipped_notify += 1
            continue
        if thread_name in skip_names:
            skipped_tag_threads += 1
            continue
        if scanned >= max_threads:
            break

        scanned += 1
        try:
            current_thread = discord_request_json("/channels/{}".format(thread_id))
            starter_message = discord_request_json("/channels/{}/messages/{}".format(thread_id, thread_id))
            embeds = starter_message.get("embeds", []) if isinstance(starter_message, dict) else []
            source_embed = embeds[0] if embeds and isinstance(embeds[0], dict) else None
            if not isinstance(source_embed, dict):
                skipped_invalid += 1
                continue

            current_ids = [str(value) for value in current_thread.get("applied_tags", []) if str(value).strip()] if isinstance(current_thread, dict) else []
            tag_names = get_nexus_embed_tag_names(source_embed, limit=4)
            updated_ids = update_discord_media_thread_tags(
                media_channel_id,
                thread_id,
                required_tag_names=tag_names,
                preserve_current_tag_names=[FAVORITE_MEDIA_TAG_NAME],
            )
            if set(current_ids) != set(updated_ids):
                changed += 1
        except Exception as exc:
            errors.append("{}: {}".format(thread_name, sanitize_text(str(exc))))

    return {
        "ok": True,
        "media_channel_id": media_channel_id,
        "scanned": scanned,
        "changed": changed,
        "skipped_notify": skipped_notify,
        "skipped_tag_threads": skipped_tag_threads,
        "skipped_invalid": skipped_invalid,
        "errors": errors[:20],
        "updated_at": now_iso_utc(),
    }


def get_twitch_embed_creator_name(embed_payload):
    creator_name = get_nexus_embed_field_value(embed_payload, "Creator")
    if not creator_name:
        creator_name = get_nexus_embed_field_value(embed_payload, "Streamer")
    return normalize_nexus_thread_name(creator_name, "Twitch")


def ensure_twitch_notification_thread():
    media_channel_id = sanitize_text(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return ""

    starter_payload = {
        "content": "このスレッドへ Twitch の新着通知を投稿します。クリエイター別スレッドへも自動投稿されます。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    }
    result = ensure_nexus_media_thread(
        media_channel_id,
        DISCORD_TWITCH_NOTIFY_THREAD_NAME,
        starter_payload,
    )
    return str(result.get("thread_id", "") or "")


def post_twitch_notification_message(item, payload):
    media_channel_id = sanitize_text(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    if media_channel_id:
        thread_id = ensure_twitch_notification_thread()
        if not thread_id:
            raise RuntimeError("Twitch notification thread could not be resolved")
        result = discord_post_json("/channels/{}/messages".format(thread_id), payload)
        try:
            update_discord_thread_starter_message(thread_id, payload)
        except Exception:
            pass
        try:
            save_twitch_message_to_creator_thread(
                payload.get("content", ""),
                (payload.get("embeds", [{}])[0] if isinstance(payload.get("embeds"), list) and payload.get("embeds") else {}),
                payload.get("components", []),
            )
        except Exception:
            pass
        return result
    return discord_post_json("/channels/{}/messages".format(TWITCH_NOTIFY_CHANNEL_ID), payload)


def save_twitch_message_to_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_TWITCH_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_twitch_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_twitch_open_components(link_url)
    if components:
        message_payload["components"] = components

    result = post_message_to_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    result["thread_name"] = creator_name
    return result


def favorite_twitch_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_TWITCH_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_twitch_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_twitch_open_components(link_url)
    if components:
        message_payload["components"] = components

    thread_result = ensure_nexus_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    thread_id = sanitize_text(thread_result.get("thread_id", ""))
    add_favorite_tag_to_media_thread(media_channel_id, thread_id, required_tag_name="")
    return {
        "thread_id": thread_id,
        "message_id": thread_id,
        "thread_name": creator_name,
        "created": bool(thread_result.get("created", False)),
        "jump_url": build_nexus_jump_url(thread_id, thread_id),
    }


async def handle_twitch_favorite_interaction(interaction):
    message = getattr(interaction, "message", None)
    if message is None or not getattr(message, "embeds", None):
        if interaction.response.is_done():
            await interaction.followup.send("保存対象の埋め込みが見つかりません。", ephemeral=True)
        else:
            await interaction.response.send_message("保存対象の埋め込みが見つかりません。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    source_embed = message.embeds[0].to_dict()
    source_content = truncate_text(message.content or "", 1900)
    source_components = list(getattr(message, "components", []) or [])

    try:
        result = await asyncio.to_thread(
            favorite_twitch_creator_thread,
            source_content,
            source_embed,
            source_components,
        )
        thread_name = sanitize_text(result.get("thread_name", "クリエイター不明"))
        jump_url = sanitize_text(result.get("jump_url", ""))
        text = "お気に入りへ追加しました: {}".format(thread_name)
        if jump_url:
            text += "\n{}".format(jump_url)
        await interaction.followup.send(text, ephemeral=True)
    except Exception as exc:
        await interaction.followup.send("お気に入り処理に失敗しました: {}".format(exc), ephemeral=True)


def get_twitter_embed_creator_name(embed_payload):
    creator_name = get_nexus_embed_field_value(embed_payload, "Creator")
    if not creator_name:
        creator_name = get_nexus_embed_field_value(embed_payload, "Account")
    return normalize_nexus_thread_name(creator_name, "Twitter")


def ensure_twitter_notification_thread():
    media_channel_id = sanitize_text(DISCORD_TWITTER_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return ""

    starter_payload = {
        "content": "このスレッドへ Twitter/X の新着通知を投稿します。クリエイター別スレッドへも自動投稿されます。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    }
    result = ensure_nexus_media_thread(
        media_channel_id,
        DISCORD_TWITTER_NOTIFY_THREAD_NAME,
        starter_payload,
    )
    return str(result.get("thread_id", "") or "")


def post_twitter_notification_message(item, payload):
    media_channel_id = sanitize_text(DISCORD_TWITTER_MEDIA_CHANNEL_ID)
    if media_channel_id:
        thread_id = ensure_twitter_notification_thread()
        if not thread_id:
            raise RuntimeError("Twitter notification thread could not be resolved")
        result = discord_post_json("/channels/{}/messages".format(thread_id), payload)
        try:
            update_discord_thread_starter_message(thread_id, payload)
        except Exception:
            pass
        try:
            save_twitter_message_to_creator_thread(
                payload.get("content", ""),
                (payload.get("embeds", [{}])[0] if isinstance(payload.get("embeds"), list) and payload.get("embeds") else {}),
                payload.get("components", []),
            )
        except Exception:
            pass
        return result
    return discord_post_json("/channels/{}/messages".format(TWITTER_NOTIFY_CHANNEL_ID), payload)


def save_twitter_message_to_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_TWITTER_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_TWITTER_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_twitter_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_link_button_components(source_components)
    if not components:
        components = build_twitter_open_components(link_url)
    if components:
        message_payload["components"] = components

    result = post_message_to_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    result["thread_name"] = creator_name
    return result


def favorite_twitter_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_TWITTER_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_TWITTER_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_twitter_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_link_button_components(source_components)
    if not components:
        components = build_twitter_open_components(link_url)
    if components:
        message_payload["components"] = components

    thread_result = ensure_nexus_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    thread_id = sanitize_text(thread_result.get("thread_id", ""))
    add_favorite_tag_to_media_thread(media_channel_id, thread_id, required_tag_name="")
    return {
        "thread_id": thread_id,
        "message_id": thread_id,
        "thread_name": creator_name,
        "created": bool(thread_result.get("created", False)),
        "jump_url": build_nexus_jump_url(thread_id, thread_id),
    }


async def handle_twitter_favorite_interaction(interaction):
    message = getattr(interaction, "message", None)
    if message is None or not getattr(message, "embeds", None):
        if interaction.response.is_done():
            await interaction.followup.send("保存対象の埋め込みが見つかりません。", ephemeral=True)
        else:
            await interaction.response.send_message("保存対象の埋め込みが見つかりません。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    source_embed = message.embeds[0].to_dict()
    source_content = truncate_text(message.content or "", 1900)
    source_components = list(getattr(message, "components", []) or [])

    try:
        result = await asyncio.to_thread(
            favorite_twitter_creator_thread,
            source_content,
            source_embed,
            source_components,
        )
        thread_name = sanitize_text(result.get("thread_name", "投稿者不明"))
        jump_url = sanitize_text(result.get("jump_url", ""))
        text = "お気に入りへ追加しました: {}".format(thread_name)
        if jump_url:
            text += "\n{}".format(jump_url)
        await interaction.followup.send(text, ephemeral=True)
    except Exception as exc:
        await interaction.followup.send("お気に入り処理に失敗しました: {}".format(exc), ephemeral=True)


def get_nexus_watcher():
    global _nexus_watcher
    if _nexus_watcher is not None:
        return _nexus_watcher

    with _nexus_watcher_factory_lock:
        if _nexus_watcher is None:
            _nexus_watcher = NexusWatcher(
                config=NexusWatcherConfig(
                    channel_id=DISCORD_NEXUS_NOTIFY_CHANNEL_ID,
                    state_file=NEXUS_NOTIFY_STATE_FILE,
                    prime_on_start=NEXUS_NOTIFY_PRIME_ON_START,
                    request_timeout=WP_BRIDGE_TIMEOUT,
                    watch_endpoint=WP_NEXUS_WATCH_ENDPOINT,
                    watch_token=WP_NEXUS_WATCH_TOKEN,
                    watch_limit=20,
                    fallback_enabled=WP_NEXUS_FALLBACK_ENABLED,
                    fallback_posts_endpoint=WP_NEXUS_FALLBACK_POSTS_ENDPOINT,
                    fallback_category_ids=WP_NEXUS_FALLBACK_CATEGORY_IDS,
                    fallback_max_age_hours=WP_NEXUS_FALLBACK_MAX_AGE_HOURS,
                ),
                state_lock=nexus_notify_lock,
                state=nexus_notify_state,
                fetch_json_request=fetch_json_request,
                fetch_json_value_request=fetch_json_value_request,
                discord_post_json=discord_post_json,
                save_state=save_nexus_notify_state,
                sanitize_text=sanitize_text,
                strip_html_tags=strip_html_tags,
                now_iso_utc=now_iso_utc,
                build_watch_headers=build_wordpress_watch_headers,
                post_message=post_nexus_notification_message,
            )
    return _nexus_watcher


def get_twitch_watcher():
    global _twitch_watcher
    if _twitch_watcher is not None:
        return _twitch_watcher

    with _twitch_watcher_factory_lock:
        if _twitch_watcher is None:
            # Twitch 通知状態は既存 state ファイル互換のまま watcher に委譲する。
            _twitch_watcher = TwitchWatcher(
                config=TwitchWatcherConfig(
                    channel_id=TWITCH_NOTIFY_CHANNEL_ID,
                    client_id=TWITCH_CLIENT_ID,
                    client_secret=TWITCH_CLIENT_SECRET,
                    user_logins_csv=TWITCH_NOTIFY_USER_LOGINS,
                    state_file=TWITCH_NOTIFY_STATE_FILE,
                    prime_on_start=TWITCH_NOTIFY_PRIME_ON_START,
                    request_timeout=WP_BRIDGE_TIMEOUT,
                    watch_endpoint=WP_TWITCH_WATCH_ENDPOINT,
                    watch_token=WP_TWITCH_WATCH_TOKEN,
                    watch_limit=TWITCH_NOTIFY_FETCH_LIMIT,
                    save_button_custom_id=TWITCH_FAVORITE_BUTTON_CUSTOM_ID if DISCORD_TWITCH_MEDIA_CHANNEL_ID else "",
                ),
                state_lock=twitch_notify_lock,
                state=twitch_notify_state,
                fetch_json_request=fetch_json_request,
                discord_post_json=discord_post_json,
                save_state=lambda: save_social_notify_state(TWITCH_NOTIFY_STATE_FILE, twitch_notify_lock, twitch_notify_state),
                parse_csv_list=parse_csv_list,
                sanitize_text=sanitize_text,
                now_iso_utc=now_iso_utc,
                build_watch_headers=build_wordpress_watch_headers,
                post_message=post_twitch_notification_message if DISCORD_TWITCH_MEDIA_CHANNEL_ID else None,
            )
    return _twitch_watcher


def get_twitch_chat_bridge():
    global _twitch_chat_bridge
    if _twitch_chat_bridge is not None:
        return _twitch_chat_bridge

    with _twitch_chat_bridge_factory_lock:
        if _twitch_chat_bridge is None:
            _twitch_chat_bridge = TwitchChatBridge(
                config=TwitchChatBridgeConfig(
                    enabled=TWITCH_CHAT_ENABLED,
                    client_id=TWITCH_CLIENT_ID,
                    client_secret=TWITCH_CLIENT_SECRET,
                    discord_channel_id=TWITCH_CHAT_DISCORD_CHANNEL_ID,
                    broadcaster_login=TWITCH_CHAT_BROADCASTER_LOGIN,
                    broadcaster_user_id=TWITCH_CHAT_BROADCASTER_USER_ID,
                    subscription_user_logins=tuple(get_twitch_chat_subscription_logins()),
                    user_access_token=TWITCH_CHAT_USER_ACCESS_TOKEN,
                    refresh_token=TWITCH_CHAT_REFRESH_TOKEN,
                    request_timeout=WP_BRIDGE_TIMEOUT,
                    relay_delete_after_seconds=TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS,
                ),
                state_lock=twitch_chat_lock,
                state=twitch_chat_state,
                load_authorization=get_twitch_chat_auth_state,
                save_authorization=save_twitch_chat_auth_state,
                post_discord_message=post_twitch_chat_event_to_discord,
                delete_discord_messages=delete_twitch_chat_messages_from_discord,
                sanitize_text=sanitize_text,
                truncate_text=truncate_text,
                now_iso_utc=now_iso_utc,
            )
    return _twitch_chat_bridge


def start_twitch_chat_bridge():
    return get_twitch_chat_bridge().start()


def stop_twitch_chat_bridge():
    bridge = get_twitch_chat_bridge()
    bridge.stop()
    return bridge.state_snapshot()


def reconnect_twitch_chat_bridge():
    stop_twitch_chat_bridge()
    return start_twitch_chat_bridge()


def get_twitter_watcher():
    global _twitter_watcher
    if _twitter_watcher is not None:
        return _twitter_watcher

    with _twitter_watcher_factory_lock:
        if _twitter_watcher is None:
            _twitter_watcher = TwitterWatcher(
                config=TwitterWatcherConfig(
                    channel_id=TWITTER_NOTIFY_CHANNEL_ID,
                    state_file=TWITTER_NOTIFY_STATE_FILE,
                    prime_on_start=TWITTER_NOTIFY_PRIME_ON_START,
                    request_timeout=WP_BRIDGE_TIMEOUT,
                    watch_endpoint=WP_TWITTER_WATCH_ENDPOINT,
                    watch_token=WP_TWITTER_WATCH_TOKEN,
                    watch_limit=TWITTER_NOTIFY_FETCH_LIMIT,
                    save_button_custom_id=TWITTER_FAVORITE_BUTTON_CUSTOM_ID if DISCORD_TWITTER_MEDIA_CHANNEL_ID else "",
                    default_poll_seconds=TWITTER_NOTIFY_POLL_SECONDS,
                ),
                state_lock=twitter_notify_lock,
                state=twitter_notify_state,
                fetch_json_request=fetch_json_request,
                discord_post_json=discord_post_json,
                save_state=lambda: save_social_notify_state(TWITTER_NOTIFY_STATE_FILE, twitter_notify_lock, twitter_notify_state),
                sanitize_text=sanitize_text,
                now_iso_utc=now_iso_utc,
                build_watch_headers=build_wordpress_watch_headers,
                post_message=post_twitter_notification_message if DISCORD_TWITTER_MEDIA_CHANNEL_ID else None,
            )
    return _twitter_watcher


def fetch_twitch_app_token():
    return get_twitch_watcher().fetch_app_token()


def fetch_twitch_live_streams(user_logins):
    return get_twitch_watcher().fetch_live_streams(user_logins)


def _fetch_twitch_streams_chunk(headers, user_logins):
    return get_twitch_watcher().fetch_streams_chunk(headers, user_logins)


def format_twitch_notification(stream):
    return get_twitch_watcher().format_plaintext_notification(stream)


def sync_twitch_notifications(limit=None, force_send_seen=False, min_timestamp=None):
    return get_twitch_watcher().poll_once(
        limit=limit,
        force_send_seen=force_send_seen,
        min_timestamp=min_timestamp,
    )


def build_twitch_vrc_playlist(limit=None):
    return get_twitch_watcher().build_vrc_playlist_payload(limit=limit)


def sync_twitter_notifications(limit=None, force_send_seen=False, min_timestamp=None):
    return get_twitter_watcher().poll_once(
        limit=limit,
        force_send_seen=force_send_seen,
        min_timestamp=min_timestamp,
    )


def fetch_youtube_api_result(path, params=None, timeout=None):
    if not YOUTUBE_NOTIFY_API_KEY:
        raise RuntimeError("YOUTUBE_NOTIFY_API_KEY is not set")

    cleaned_params = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned_params[str(key)] = "true" if value else "false"
        else:
            cleaned_params[str(key)] = str(value)
    cleaned_params["key"] = YOUTUBE_NOTIFY_API_KEY

    url = "https://www.googleapis.com/youtube/v3/{}?{}".format(path.lstrip("/"), urlencode(cleaned_params))
    req = Request(url)
    req.add_header("User-Agent", "DiscordBotBridge/1.0")

    try:
        with urlopen(req, timeout=timeout or WP_BRIDGE_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""

        detail = ""
        if body:
            try:
                parsed = json.loads(body)
                error_node = parsed.get("error", {}) if isinstance(parsed, dict) else {}
                detail = sanitize_text(error_node.get("message", "") if isinstance(error_node, dict) else "")
            except Exception:
                detail = sanitize_text(body)
        if not detail:
            detail = sanitize_text(getattr(exc, "reason", "") or str(exc))
        raise RuntimeError("YouTube API {} failed: HTTP {} {}".format(path.lstrip("/"), exc.code, detail)) from exc
    except URLError as exc:
        raise RuntimeError("YouTube API {} failed: {}".format(path.lstrip("/"), exc)) from exc

    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise RuntimeError("YouTube API {} response is invalid".format(path.lstrip("/")))
    return data


def extract_youtube_thumbnail_url(thumbnails):
    thumbs = thumbnails if isinstance(thumbnails, dict) else {}
    for size_key in ("maxres", "standard", "high", "medium", "default"):
        node = thumbs.get(size_key, {}) if isinstance(thumbs.get(size_key), dict) else {}
        url = sanitize_text(node.get("url", ""))
        if url:
            return url
    return ""


def build_youtube_comment_url(video_url, comment_id):
    base_url = sanitize_text(video_url)
    comment_text = sanitize_text(comment_id)
    if not base_url or not comment_text:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return "{}{}lc={}".format(base_url, separator, quote(comment_text))


def chunk_list(values, size):
    rows = list(values or [])
    chunk_size = max(1, int(size or 1))
    for start in range(0, len(rows), chunk_size):
        yield rows[start:start + chunk_size]


def fetch_youtube_recent_upload_entries(channel_id, limit=5):
    channel_text = sanitize_text(channel_id)
    max_results = max(1, min(int(limit or 5), 20))
    if not channel_text:
        return []

    channel_data = fetch_youtube_api_result(
        "channels",
        {
            "part": "contentDetails,snippet",
            "id": channel_text,
            "maxResults": 1,
        },
    )
    channel_rows = channel_data.get("items", []) if isinstance(channel_data.get("items"), list) else []
    channel_row = channel_rows[0] if channel_rows and isinstance(channel_rows[0], dict) else {}
    uploads_playlist_id = sanitize_text(
        ((channel_row.get("contentDetails", {}) if isinstance(channel_row.get("contentDetails"), dict) else {}).get("relatedPlaylists", {}) if isinstance((channel_row.get("contentDetails", {}) if isinstance(channel_row.get("contentDetails"), dict) else {}).get("relatedPlaylists"), dict) else {}).get("uploads", "")
    )
    channel_title = sanitize_text((channel_row.get("snippet", {}) if isinstance(channel_row.get("snippet"), dict) else {}).get("title", ""))
    if not uploads_playlist_id:
        return []

    playlist_data = fetch_youtube_api_result(
        "playlistItems",
        {
            "part": "snippet,contentDetails,status",
            "playlistId": uploads_playlist_id,
            "maxResults": max_results,
        },
    )

    entries = []
    for row in playlist_data.get("items", []):
        if not isinstance(row, dict):
            continue
        snippet = row.get("snippet", {}) if isinstance(row.get("snippet"), dict) else {}
        content_details = row.get("contentDetails", {}) if isinstance(row.get("contentDetails"), dict) else {}
        status = row.get("status", {}) if isinstance(row.get("status"), dict) else {}
        resource = snippet.get("resourceId", {}) if isinstance(snippet.get("resourceId"), dict) else {}
        video_id = sanitize_text(content_details.get("videoId", "") or resource.get("videoId", ""))
        if not video_id:
            continue
        if sanitize_text(status.get("privacyStatus", "")).lower() == "private":
            continue

        title = sanitize_text(snippet.get("title", ""))
        if title.lower() == "private video":
            continue

        item_channel_id = sanitize_text(snippet.get("channelId", "") or channel_text)
        entries.append(
            {
                "video_id": video_id,
                "title": title,
                "published": sanitize_text(content_details.get("videoPublishedAt", "") or snippet.get("publishedAt", "")),
                "author": sanitize_text(snippet.get("channelTitle", "") or channel_title),
                "channel_id": item_channel_id,
                "url": "https://www.youtube.com/watch?v={}".format(video_id),
                "channel_url": "https://www.youtube.com/channel/{}".format(item_channel_id) if item_channel_id else "",
                "thumbnail_url": extract_youtube_thumbnail_url(snippet.get("thumbnails", {})) or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
            }
        )

    return entries


def fetch_youtube_recent_upload_entries_for_channels(channel_ids, limit_per_channel=5):
    entries = []
    seen_video_ids = set()
    for channel_id in parse_csv_list(",".join(channel_ids if isinstance(channel_ids, list) else parse_csv_list(channel_ids))):
        for item in fetch_youtube_recent_upload_entries(channel_id, limit=limit_per_channel):
            video_id = sanitize_text(item.get("video_id", ""))
            if not video_id or video_id in seen_video_ids:
                continue
            seen_video_ids.add(video_id)
            entries.append(item)

    entries.sort(key=lambda row: parse_wp_datetime_to_epoch(row.get("published", "")) or 0, reverse=True)
    return entries


def is_youtube_nonfatal_comment_error(error_text):
    lowered = sanitize_text(error_text).lower()
    return any(
        token in lowered
        for token in (
            "commentsdisabled",
            "comment disabled",
            "comments disabled",
            "comment threads disabled",
            "videonotfound",
            "video not found",
        )
    )


def fetch_youtube_comment_entries(channel_ids, limit=20, video_limit=5, per_video_limit=5):
    total_limit = max(1, min(int(limit or 20), 100))
    max_per_video = max(1, min(int(per_video_limit or 5), 20))
    videos = fetch_youtube_recent_upload_entries_for_channels(channel_ids, limit_per_channel=video_limit)
    entries = []

    for video in videos:
        if len(entries) >= total_limit:
            break

        try:
            data = fetch_youtube_api_result(
                "commentThreads",
                {
                    "part": "snippet",
                    "videoId": video.get("video_id", ""),
                    "maxResults": min(max_per_video, total_limit),
                    "order": "time",
                    "textFormat": "plainText",
                },
            )
        except Exception as exc:
            if is_youtube_nonfatal_comment_error(str(exc)):
                continue
            raise

        for row in data.get("items", []):
            if not isinstance(row, dict):
                continue
            snippet = row.get("snippet", {}) if isinstance(row.get("snippet"), dict) else {}
            top_comment = snippet.get("topLevelComment", {}) if isinstance(snippet.get("topLevelComment"), dict) else {}
            top_snippet = top_comment.get("snippet", {}) if isinstance(top_comment.get("snippet"), dict) else {}
            comment_id = sanitize_text(top_comment.get("id", "") or row.get("id", ""))
            if not comment_id:
                continue

            comment_text = sanitize_text(top_snippet.get("textOriginal", "") or top_snippet.get("textDisplay", ""))
            entries.append(
                {
                    "id": comment_id,
                    "video_id": sanitize_text(video.get("video_id", "")),
                    "video_title": sanitize_text(video.get("title", "")),
                    "video_url": sanitize_text(video.get("url", "")),
                    "comment_url": build_youtube_comment_url(video.get("url", ""), comment_id),
                    "published": sanitize_text(top_snippet.get("publishedAt", "")),
                    "updated": sanitize_text(top_snippet.get("updatedAt", "")),
                    "author": sanitize_text(top_snippet.get("authorDisplayName", "")),
                    "author_channel_id": sanitize_text(top_snippet.get("authorChannelId", {}).get("value", "") if isinstance(top_snippet.get("authorChannelId"), dict) else ""),
                    "text": comment_text,
                    "like_count": safe_int(top_snippet.get("likeCount", 0), 0),
                    "creator": sanitize_text(video.get("author", "")),
                    "channel_id": sanitize_text(video.get("channel_id", "")),
                    "channel_url": sanitize_text(video.get("channel_url", "")),
                    "thumbnail_url": sanitize_text(video.get("thumbnail_url", "")),
                }
            )

    entries.sort(key=lambda row: parse_wp_datetime_to_epoch(row.get("published", "")) or 0, reverse=True)
    return entries[:total_limit]


def fetch_youtube_active_live_video_entries(channel_ids, video_limit=5):
    videos = fetch_youtube_recent_upload_entries_for_channels(channel_ids, limit_per_channel=video_limit)
    if not videos:
        return []

    base_by_video_id = {}
    for video in videos:
        video_id = sanitize_text(video.get("video_id", ""))
        if video_id:
            base_by_video_id[video_id] = video

    active_rows = []
    for chunk in chunk_list(list(base_by_video_id.keys()), 50):
        data = fetch_youtube_api_result(
            "videos",
            {
                "part": "snippet,liveStreamingDetails",
                "id": ",".join(chunk),
                "maxResults": len(chunk),
            },
        )
        for row in data.get("items", []):
            if not isinstance(row, dict):
                continue
            video_id = sanitize_text(row.get("id", ""))
            if not video_id or video_id not in base_by_video_id:
                continue

            snippet = row.get("snippet", {}) if isinstance(row.get("snippet"), dict) else {}
            live_details = row.get("liveStreamingDetails", {}) if isinstance(row.get("liveStreamingDetails"), dict) else {}
            live_chat_id = sanitize_text(live_details.get("activeLiveChatId", ""))
            if not live_chat_id:
                continue

            base = base_by_video_id[video_id]
            active_rows.append(
                {
                    "live_chat_id": live_chat_id,
                    "video_id": video_id,
                    "title": sanitize_text(base.get("title", "") or snippet.get("title", "")),
                    "author": sanitize_text(base.get("author", "") or snippet.get("channelTitle", "")),
                    "channel_id": sanitize_text(base.get("channel_id", "") or snippet.get("channelId", "")),
                    "url": sanitize_text(base.get("url", "") or "https://www.youtube.com/watch?v={}".format(video_id)),
                    "channel_url": sanitize_text(base.get("channel_url", "")),
                    "thumbnail_url": sanitize_text(base.get("thumbnail_url", "")) or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
                    "published": sanitize_text(base.get("published", "") or snippet.get("publishedAt", "")),
                    "started": sanitize_text(live_details.get("actualStartTime", "") or live_details.get("scheduledStartTime", "")),
                }
            )

    active_rows.sort(key=lambda row: parse_wp_datetime_to_epoch(row.get("started", "")) or parse_wp_datetime_to_epoch(row.get("published", "")) or 0, reverse=True)
    return active_rows


def is_supported_youtube_livechat_event(event_type):
    return sanitize_text(event_type) in (
        "textMessageEvent",
        "superChatEvent",
        "superStickerEvent",
        "memberMilestoneChatEvent",
        "membershipGiftingEvent",
        "giftMembershipReceivedEvent",
    )


def youtube_livechat_event_label(event_type):
    return {
        "textMessageEvent": "Text",
        "superChatEvent": "Super Chat",
        "superStickerEvent": "Super Sticker",
        "memberMilestoneChatEvent": "Member Milestone",
        "membershipGiftingEvent": "Membership Gift",
        "giftMembershipReceivedEvent": "Gift Received",
    }.get(sanitize_text(event_type), "Live Chat")


def fetch_youtube_livechat_entries(channel_ids, limit=50, video_limit=5, page_tokens=None, prime_missing_tokens=True):
    total_limit = max(1, min(int(limit or 50), 200))
    known_tokens = dict(page_tokens or {})
    active_streams = fetch_youtube_active_live_video_entries(channel_ids, video_limit=video_limit)

    entries = []
    next_page_tokens = {}
    active_chat_ids = []
    active_video_ids = []

    for stream in active_streams:
        live_chat_id = sanitize_text(stream.get("live_chat_id", ""))
        if not live_chat_id:
            continue

        active_chat_ids.append(live_chat_id)
        video_id = sanitize_text(stream.get("video_id", ""))
        if video_id:
            active_video_ids.append(video_id)

        request_params = {
            "part": "snippet,authorDetails",
            "liveChatId": live_chat_id,
            "maxResults": min(total_limit, 200),
        }
        page_token = sanitize_text(known_tokens.get(live_chat_id, ""))
        skip_items = False
        if page_token:
            request_params["pageToken"] = page_token
        elif prime_missing_tokens:
            skip_items = True

        try:
            data = fetch_youtube_api_result("liveChat/messages", request_params)
        except Exception as exc:
            if page_token and "page token" in sanitize_text(str(exc)).lower():
                retry_params = dict(request_params)
                retry_params.pop("pageToken", None)
                data = fetch_youtube_api_result("liveChat/messages", retry_params)
                skip_items = True
            else:
                raise

        next_page_token = sanitize_text(data.get("nextPageToken", ""))
        if next_page_token:
            next_page_tokens[live_chat_id] = next_page_token
        if skip_items:
            continue

        for row in data.get("items", []):
            if not isinstance(row, dict):
                continue
            snippet = row.get("snippet", {}) if isinstance(row.get("snippet"), dict) else {}
            event_type = sanitize_text(snippet.get("type", ""))
            if not is_supported_youtube_livechat_event(event_type):
                continue
            message_text = sanitize_text(snippet.get("displayMessage", ""))
            if not message_text:
                continue
            message_id = sanitize_text(row.get("id", ""))
            if not message_id:
                continue

            author_details = row.get("authorDetails", {}) if isinstance(row.get("authorDetails"), dict) else {}
            entries.append(
                {
                    "id": message_id,
                    "live_chat_id": live_chat_id,
                    "video_id": video_id,
                    "video_title": sanitize_text(stream.get("title", "")),
                    "video_url": sanitize_text(stream.get("url", "")),
                    "published": sanitize_text(snippet.get("publishedAt", "")),
                    "author": sanitize_text(author_details.get("displayName", "")),
                    "author_channel_id": sanitize_text(author_details.get("channelId", "")),
                    "author_channel_url": "https://www.youtube.com/channel/{}".format(sanitize_text(author_details.get("channelId", ""))) if sanitize_text(author_details.get("channelId", "")) else "",
                    "author_image_url": sanitize_text(author_details.get("profileImageUrl", "")),
                    "text": message_text,
                    "event_type": event_type,
                    "event_label": youtube_livechat_event_label(event_type),
                    "creator": sanitize_text(stream.get("author", "")),
                    "channel_id": sanitize_text(stream.get("channel_id", "")),
                    "channel_url": sanitize_text(stream.get("channel_url", "")),
                    "thumbnail_url": sanitize_text(stream.get("thumbnail_url", "")),
                    "started": sanitize_text(stream.get("started", "")),
                }
            )

    entries.sort(key=lambda row: parse_wp_datetime_to_epoch(row.get("published", "")) or 0, reverse=True)
    return {
        "items": entries[:total_limit],
        "next_page_tokens": next_page_tokens,
        "active_chat_ids": active_chat_ids,
        "active_video_ids": active_video_ids,
    }


def build_recent_youtube_comment_items(items, max_items=50):
    recent_items = []
    for item in list(items or [])[:max(1, min(int(max_items or 50), 100))]:
        if not isinstance(item, dict):
            continue
        item_id = sanitize_text(item.get("id", ""))
        if not item_id:
            continue
        recent_items.append(
            {
                "id": item_id,
                "type": "youtube_comment",
                "video_id": sanitize_text(item.get("video_id", "")),
                "video_title": truncate_text(sanitize_text(item.get("video_title", "")), 256),
                "video_url": sanitize_text(item.get("video_url", "")),
                "comment_url": sanitize_text(item.get("comment_url", "")),
                "published": sanitize_text(item.get("published", "")),
                "updated": sanitize_text(item.get("updated", "")),
                "author": sanitize_text(item.get("author", "")),
                "author_channel_id": sanitize_text(item.get("author_channel_id", "")),
                "text": truncate_text(sanitize_text(item.get("text", "")), 500),
                "like_count": safe_int(item.get("like_count", 0), 0),
                "creator": sanitize_text(item.get("creator", "")),
                "channel": sanitize_text(item.get("creator", "")),
                "channel_id": sanitize_text(item.get("channel_id", "")),
                "channel_url": sanitize_text(item.get("channel_url", "")),
                "thumbnail_url": sanitize_text(item.get("thumbnail_url", "")),
            }
        )
    return recent_items


def build_recent_youtube_livechat_items(items, max_items=50):
    recent_items = []
    for item in list(items or [])[:max(1, min(int(max_items or 50), 100))]:
        if not isinstance(item, dict):
            continue
        item_id = sanitize_text(item.get("id", ""))
        if not item_id:
            continue
        recent_items.append(
            {
                "id": item_id,
                "type": "youtube_livechat",
                "live_chat_id": sanitize_text(item.get("live_chat_id", "")),
                "video_id": sanitize_text(item.get("video_id", "")),
                "video_title": truncate_text(sanitize_text(item.get("video_title", "")), 256),
                "video_url": sanitize_text(item.get("video_url", "")),
                "published": sanitize_text(item.get("published", "")),
                "author": sanitize_text(item.get("author", "")),
                "author_channel_id": sanitize_text(item.get("author_channel_id", "")),
                "author_channel_url": sanitize_text(item.get("author_channel_url", "")),
                "author_image_url": sanitize_text(item.get("author_image_url", "")),
                "text": truncate_text(sanitize_text(item.get("text", "")), 500),
                "event_type": sanitize_text(item.get("event_type", "")),
                "event_label": sanitize_text(item.get("event_label", "")),
                "creator": sanitize_text(item.get("creator", "")),
                "channel": sanitize_text(item.get("creator", "")),
                "channel_id": sanitize_text(item.get("channel_id", "")),
                "channel_url": sanitize_text(item.get("channel_url", "")),
                "thumbnail_url": sanitize_text(item.get("thumbnail_url", "")),
                "started": sanitize_text(item.get("started", "")),
            }
        )
    return recent_items


def fetch_youtube_feed_entries(channel_id):
    channel_id = sanitize_text(channel_id)
    if not channel_id:
        return []

    if YOUTUBE_NOTIFY_API_KEY:
        api_url = (
            "https://www.googleapis.com/youtube/v3/search"
            "?part=snippet"
            "&channelId={}"
            "&order=date"
            "&maxResults=50"
            "&type=video"
            "&key={}"
        ).format(quote(channel_id), quote(YOUTUBE_NOTIFY_API_KEY))
        data = fetch_json_request(api_url, timeout=WP_BRIDGE_TIMEOUT)
        items = []
        for entry in data.get("items", []):
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id", {}) if isinstance(entry.get("id"), dict) else {}
            snippet = entry.get("snippet", {}) if isinstance(entry.get("snippet"), dict) else {}
            video_id = sanitize_text(entry_id.get("videoId", ""))
            if not video_id:
                continue

            item_channel_id = sanitize_text(snippet.get("channelId", "")) or channel_id
            thumbnail_url = ""
            thumbnails = snippet.get("thumbnails", {}) if isinstance(snippet.get("thumbnails"), dict) else {}
            for size_key in ("high", "medium", "default"):
                node = thumbnails.get(size_key, {}) if isinstance(thumbnails.get(size_key), dict) else {}
                thumbnail_url = sanitize_text(node.get("url", ""))
                if thumbnail_url:
                    break

            items.append(
                {
                    "video_id": video_id,
                    "title": sanitize_text(snippet.get("title", "")),
                    "published": sanitize_text(snippet.get("publishedAt", "")),
                    "author": sanitize_text(snippet.get("channelTitle", "")),
                    "channel_id": item_channel_id,
                    "url": "https://www.youtube.com/watch?v={}".format(video_id),
                    "channel_url": "https://www.youtube.com/channel/{}".format(item_channel_id),
                    "thumbnail_url": thumbnail_url or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
                }
            )
        return items

    url = "https://www.youtube.com/feeds/videos.xml?channel_id={}".format(quote(channel_id))
    timeout_seconds = max(1, int(WP_BRIDGE_TIMEOUT or 10))
    try:
        # Data API 未設定時の後方互換。YouTube feed は urllib / requests 系クライアントへ 404 を返すことがあるため curl を優先する。
        completed = subprocess.run(
            ["curl", "-fsSL", "--max-time", str(timeout_seconds), url],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout_seconds + 2,
        )
        xml_text = completed.stdout
    except FileNotFoundError:
        with urlopen(Request(url), timeout=timeout_seconds) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError("YouTube feed fetch via curl failed{}".format(": " + detail if detail else "")) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("YouTube feed fetch via curl timed out") from exc

    root = ET.fromstring(xml_text)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    items = []
    for entry in root.findall("atom:entry", ns):
        video_id = ""
        node_video_id = entry.find("yt:videoId", ns)
        if node_video_id is not None and node_video_id.text:
            video_id = node_video_id.text.strip()
        title = ""
        node_title = entry.find("atom:title", ns)
        if node_title is not None and node_title.text:
            title = node_title.text.strip()
        published = ""
        node_published = entry.find("atom:published", ns)
        if node_published is not None and node_published.text:
            published = node_published.text.strip()
        author = ""
        node_author_name = entry.find("atom:author/atom:name", ns)
        if node_author_name is not None and node_author_name.text:
            author = node_author_name.text.strip()
        channel = ""
        node_channel_id = entry.find("yt:channelId", ns)
        if node_channel_id is not None and node_channel_id.text:
            channel = node_channel_id.text.strip()

        if video_id:
            items.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "published": published,
                    "author": author,
                    "channel_id": channel or channel_id,
                    "url": "https://www.youtube.com/watch?v={}".format(video_id),
                    "channel_url": "https://www.youtube.com/channel/{}".format(channel or channel_id),
                    "thumbnail_url": "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
                }
            )

    return items


def format_youtube_notification(item):
    author = sanitize_text(item.get("author", "Unknown"))
    title = sanitize_text(item.get("title", "新着動画"))
    published = sanitize_text(item.get("published", ""))
    video_id = sanitize_text(item.get("video_id", ""))
    channel_id = sanitize_text(item.get("channel_id", ""))

    url = "https://www.youtube.com/watch?v={}".format(video_id)
    channel_url = "https://www.youtube.com/channel/{}".format(channel_id) if channel_id else ""
    lines = ["【YouTube 新着動画】", "{} が新しい動画を公開しました".format(author), title]
    if published:
        lines.append("公開時刻: {}".format(published))
    if channel_url:
        lines.append("チャンネル: {}".format(channel_url))
    lines.append(url)
    return "\n".join(lines)[:1900]


def build_youtube_open_components(video_url, channel_url="", channel_label=""):
    return build_youtube_link_components(
        video_url,
        "視聴する / Watch",
        channel_url,
        truncate_text(sanitize_text(channel_label) or "チャンネル / Channel", 80),
    )


def build_youtube_link_components(primary_url, primary_label, channel_url="", channel_label=""):
    buttons = []
    primary_link = sanitize_text(primary_url)
    if primary_link:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": truncate_text(sanitize_text(primary_label) or "Open", 80),
                "url": primary_link,
            }
        )
    resolved_channel_url = sanitize_text(channel_url)
    if resolved_channel_url:
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": truncate_text(sanitize_text(channel_label) or "チャンネル / Channel", 80),
                "url": resolved_channel_url,
            }
        )
    if not buttons:
        return []
    return [{"type": 1, "components": buttons[:5]}]


def append_youtube_favorite_button(components, include_save_button=False):
    rows = extract_discord_component_dicts(components)
    if not include_save_button:
        return rows
    if rows:
        first_row = dict(rows[0])
        row_components = list(first_row.get("components", []))
        row_components.append(
            {
                "type": 2,
                "style": 2,
                "label": "お気に入り / Favorite",
                "custom_id": YOUTUBE_FAVORITE_BUTTON_CUSTOM_ID,
            }
        )
        first_row["components"] = row_components[:5]
        return [first_row]
    return [{"type": 1, "components": [{"type": 2, "style": 2, "label": "お気に入り / Favorite", "custom_id": YOUTUBE_FAVORITE_BUTTON_CUSTOM_ID}]}]


def build_youtube_message_payload(item, include_save_button=False):
    author = sanitize_text(item.get("author", "Unknown"))
    title = truncate_text(sanitize_text(item.get("title", "新着動画")), 256)
    published = sanitize_text(item.get("published", ""))
    video_id = sanitize_text(item.get("video_id", ""))
    channel_id = sanitize_text(item.get("channel_id", ""))
    video_url = sanitize_text(item.get("url", "") or "https://www.youtube.com/watch?v={}".format(video_id))
    channel_url = sanitize_text(item.get("channel_url", "") or ("https://www.youtube.com/channel/{}".format(channel_id) if channel_id else ""))
    thumbnail_url = sanitize_text(item.get("thumbnail_url", "") or ("https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id) if video_id else ""))

    payload = {
        "content": truncate_text("【YouTube 新着動画】\n{}".format(video_url), 1900),
        "embeds": [
            {
                "title": title,
                "url": video_url or None,
                "color": 0xFF0000,
                "author": {
                    "name": "YouTube Watch",
                    "icon_url": "https://www.youtube.com/s/desktop/6e7e0c58/img/favicon_32x32.png",
                },
                "fields": [
                    {
                        "name": "Creator",
                        "value": truncate_text(author or "Unknown", 1024),
                        "inline": True,
                    },
                    {
                        "name": "Channel",
                        "value": truncate_text(author or "Unknown", 1024),
                        "inline": True,
                    },
                    {
                        "name": "Published",
                        "value": truncate_text(published or "-", 1024),
                        "inline": True,
                    },
                ],
            }
        ],
    }
    if thumbnail_url:
        payload["embeds"][0]["image"] = {"url": thumbnail_url}

    components = append_youtube_favorite_button(
        build_youtube_open_components(video_url, channel_url, author),
        include_save_button=include_save_button,
    )
    if components:
        payload["components"] = components
    return payload


def build_youtube_comment_message_payload(item, include_save_button=False):
    creator = sanitize_text(item.get("creator", "")) or "Unknown"
    video_title = truncate_text(sanitize_text(item.get("video_title", "") or "YouTube 動画"), 256)
    comment_author = sanitize_text(item.get("author", "")) or "Unknown"
    published = sanitize_text(item.get("published", ""))
    comment_url = sanitize_text(item.get("comment_url", "") or item.get("video_url", ""))
    video_url = sanitize_text(item.get("video_url", ""))
    channel_url = sanitize_text(item.get("channel_url", ""))
    thumbnail_url = sanitize_text(item.get("thumbnail_url", ""))
    comment_text = truncate_text(sanitize_text(item.get("text", "")), 350)
    like_count = safe_int(item.get("like_count", 0), 0)

    payload = {
        "content": truncate_text("【YouTube 動画コメント】\n{}".format(comment_url or video_url), 1900),
        "embeds": [
            {
                "title": video_title,
                "url": comment_url or video_url or None,
                "description": comment_text or None,
                "color": 0xFF0000,
                "author": {
                    "name": "YouTube Comments",
                    "icon_url": "https://www.youtube.com/s/desktop/6e7e0c58/img/favicon_32x32.png",
                },
                "fields": [
                    {"name": "Creator", "value": truncate_text(creator, 1024), "inline": True},
                    {"name": "Video", "value": truncate_text(video_title, 1024), "inline": True},
                    {"name": "Comment By", "value": truncate_text(comment_author, 1024), "inline": True},
                    {"name": "Published", "value": truncate_text(published or "-", 1024), "inline": True},
                    {"name": "Likes", "value": str(max(0, like_count)), "inline": True},
                ],
            }
        ],
    }
    if thumbnail_url:
        payload["embeds"][0]["thumbnail"] = {"url": thumbnail_url}

    components = append_youtube_favorite_button(
        build_youtube_link_components(
            comment_url or video_url,
            "コメントを見る / View Comment",
            channel_url,
            creator,
        ),
        include_save_button=include_save_button,
    )
    if components:
        payload["components"] = components
    return payload


def build_youtube_livechat_message_payload(item, include_save_button=False):
    creator = sanitize_text(item.get("creator", "")) or "Unknown"
    video_title = truncate_text(sanitize_text(item.get("video_title", "") or "YouTube Live"), 256)
    author = sanitize_text(item.get("author", "")) or "Unknown"
    published = sanitize_text(item.get("published", ""))
    video_url = sanitize_text(item.get("video_url", ""))
    channel_url = sanitize_text(item.get("channel_url", ""))
    thumbnail_url = sanitize_text(item.get("thumbnail_url", ""))
    author_image_url = sanitize_text(item.get("author_image_url", ""))
    text = truncate_text(sanitize_text(item.get("text", "")), 350)
    event_label = sanitize_text(item.get("event_label", "")) or "Live Chat"

    payload = {
        "content": truncate_text("【YouTube Live Chat】\n{}".format(video_url), 1900),
        "embeds": [
            {
                "title": video_title,
                "url": video_url or None,
                "description": text or None,
                "color": 0xFF0000,
                "author": {
                    "name": "YouTube Live Chat",
                    "icon_url": "https://www.youtube.com/s/desktop/6e7e0c58/img/favicon_32x32.png",
                },
                "fields": [
                    {"name": "Creator", "value": truncate_text(creator, 1024), "inline": True},
                    {"name": "Live", "value": truncate_text(video_title, 1024), "inline": True},
                    {"name": "User", "value": truncate_text(author, 1024), "inline": True},
                    {"name": "Type", "value": truncate_text(event_label, 1024), "inline": True},
                    {"name": "Published", "value": truncate_text(published or "-", 1024), "inline": True},
                ],
            }
        ],
    }
    if author_image_url:
        payload["embeds"][0]["thumbnail"] = {"url": author_image_url}
    elif thumbnail_url:
        payload["embeds"][0]["thumbnail"] = {"url": thumbnail_url}

    components = append_youtube_favorite_button(
        build_youtube_link_components(
            video_url,
            "ライブを見る / Watch Live",
            channel_url,
            creator,
        ),
        include_save_button=include_save_button,
    )
    if components:
        payload["components"] = components
    return payload


def initialize_youtube_media_tags():
    media_channel_id = sanitize_text(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return {"ok": True, "enabled": False, "created": [], "existing": [], "skipped": []}

    return {
        "ok": True,
        "enabled": False,
        "created": [],
        "existing": [],
        "skipped": [],
        "reason": "youtube media forum tags are disabled",
    }


def ensure_youtube_notification_thread():
    return ensure_youtube_named_notification_thread(
        DISCORD_YOUTUBE_NOTIFY_THREAD_NAME,
        "このスレッドへ YouTube の新着通知を投稿します。クリエイター別スレッドへも自動投稿されます。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    )


def ensure_youtube_comments_notification_thread():
    return ensure_youtube_named_notification_thread(
        DISCORD_YOUTUBE_COMMENTS_NOTIFY_THREAD_NAME,
        "このスレッドへ YouTube 動画コメント通知を投稿します。クリエイター別スレッドへも自動投稿されます。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    )


def ensure_youtube_livechat_notification_thread():
    return ensure_youtube_named_notification_thread(
        DISCORD_YOUTUBE_LIVECHAT_NOTIFY_THREAD_NAME,
        "このスレッドへ YouTube live chat 通知を投稿します。クリエイター別スレッドへも自動投稿されます。お気に入りボタンで対象スレッドへお気に入りタグを付けられます。",
    )


def ensure_youtube_named_notification_thread(thread_name, starter_text):
    media_channel_id = sanitize_text(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        return ""

    starter_payload = {"content": starter_text}
    result = ensure_nexus_media_thread(
        media_channel_id,
        thread_name,
        starter_payload,
    )
    return str(result.get("thread_id", "") or "")


def post_youtube_notification_message(item, payload):
    return post_youtube_media_notification_message(
        payload,
        YOUTUBE_NOTIFY_CHANNEL_ID,
        ensure_youtube_notification_thread,
        "YouTube notification thread could not be resolved",
    )


def post_youtube_comment_notification_message(item, payload):
    return post_youtube_media_notification_message(
        payload,
        YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID,
        ensure_youtube_comments_notification_thread,
        "YouTube comments notification thread could not be resolved",
    )


def post_youtube_livechat_notification_message(item, payload):
    return post_youtube_media_notification_message(
        payload,
        YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID,
        ensure_youtube_livechat_notification_thread,
        "YouTube live chat notification thread could not be resolved",
    )


def post_youtube_media_notification_message(payload, fallback_channel_id, ensure_thread_func, missing_thread_message):
    media_channel_id = sanitize_text(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID)
    if media_channel_id:
        thread_id = ensure_thread_func()
        if not thread_id:
            raise RuntimeError(missing_thread_message)
        result = discord_post_json("/channels/{}/messages".format(thread_id), payload)
        try:
            update_discord_thread_starter_message(thread_id, payload)
        except Exception:
            pass
        try:
            save_youtube_message_to_creator_thread(
                payload.get("content", ""),
                (payload.get("embeds", [{}])[0] if isinstance(payload.get("embeds"), list) and payload.get("embeds") else {}),
                payload.get("components", []),
            )
        except Exception:
            pass
        return result

    fallback_channel_text = sanitize_text(fallback_channel_id)
    if not fallback_channel_text:
        raise RuntimeError("YouTube notify channel is not set")
    return discord_post_json("/channels/{}/messages".format(fallback_channel_text), payload)


def get_youtube_embed_creator_name(embed_payload):
    creator_name = get_nexus_embed_field_value(embed_payload, "Creator")
    if not creator_name:
        creator_name = get_nexus_embed_field_value(embed_payload, "Channel")
    return normalize_nexus_thread_name(creator_name, "YouTube")


def save_youtube_message_to_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_YOUTUBE_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_youtube_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_youtube_open_components(link_url)
    if components:
        message_payload["components"] = components

    result = post_message_to_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    result["thread_name"] = creator_name
    return result


def favorite_youtube_creator_thread(source_content, source_embed_payload, source_components=None):
    media_channel_id = sanitize_text(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID)
    if not media_channel_id:
        raise RuntimeError("DISCORD_YOUTUBE_MEDIA_CHANNEL_ID is not set")
    if not isinstance(source_embed_payload, dict):
        raise RuntimeError("source embed is required")

    creator_name = get_youtube_embed_creator_name(source_embed_payload)
    link_url = sanitize_text(source_embed_payload.get("url", ""))
    message_payload = {
        "content": truncate_text(source_content, 1900),
        "embeds": [source_embed_payload],
    }
    components = extract_discord_component_dicts(source_components)
    if not components:
        components = build_youtube_open_components(link_url)
    if components:
        message_payload["components"] = components

    thread_result = ensure_nexus_media_thread(
        media_channel_id,
        creator_name,
        message_payload,
    )
    thread_id = sanitize_text(thread_result.get("thread_id", ""))
    add_favorite_tag_to_media_thread(media_channel_id, thread_id, required_tag_name="")
    return {
        "thread_id": thread_id,
        "message_id": thread_id,
        "thread_name": creator_name,
        "created": bool(thread_result.get("created", False)),
        "jump_url": build_nexus_jump_url(thread_id, thread_id),
    }


async def handle_youtube_favorite_interaction(interaction):
    message = getattr(interaction, "message", None)
    if message is None or not getattr(message, "embeds", None):
        if interaction.response.is_done():
            await interaction.followup.send("保存対象の埋め込みが見つかりません。", ephemeral=True)
        else:
            await interaction.response.send_message("保存対象の埋め込みが見つかりません。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    source_embed = message.embeds[0].to_dict()
    source_content = truncate_text(message.content or "", 1900)
    source_components = list(getattr(message, "components", []) or [])

    try:
        result = await asyncio.to_thread(
            favorite_youtube_creator_thread,
            source_content,
            source_embed,
            source_components,
        )
        thread_name = sanitize_text(result.get("thread_name", "クリエイター不明"))
        jump_url = sanitize_text(result.get("jump_url", ""))
        text = "お気に入りへ追加しました: {}".format(thread_name)
        if jump_url:
            text += "\n{}".format(jump_url)
        await interaction.followup.send(text, ephemeral=True)
    except Exception as exc:
        await interaction.followup.send("お気に入り処理に失敗しました: {}".format(exc), ephemeral=True)


def fetch_wordpress_page_promos(limit=50):
    if not WP_PAGE_PROMO_ENDPOINT:
        raise RuntimeError("WP_PAGE_PROMO_ENDPOINT is not set")

    bounded_limit = max(1, min(int(limit or 50), 100))
    joiner = "&" if "?" in WP_PAGE_PROMO_ENDPOINT else "?"
    url = "{}{}limit={}".format(WP_PAGE_PROMO_ENDPOINT, joiner, bounded_limit)
    headers = {"User-Agent": "DiscordBotBridge/1.0"}
    if WP_PAGE_PROMO_TOKEN:
        headers["Authorization"] = "Bearer {}".format(WP_PAGE_PROMO_TOKEN)
        headers["X-Sevendtd-Bearer"] = WP_PAGE_PROMO_TOKEN

    req = Request(url)
    for key, value in headers.items():
        req.add_header(key, value)
    with urlopen(req, timeout=WP_BRIDGE_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw) if raw.strip() else []

    items = []
    if isinstance(data, dict):
        raw_items = data.get("items", [])
        if isinstance(raw_items, list):
            items = raw_items
    elif isinstance(data, list):
        items = data
    if not isinstance(items, list):
        items = []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        post_id = sanitize_text(item.get("id", ""))
        title = strip_html_tags(item.get("title", ""))
        excerpt = strip_html_tags(item.get("excerpt", ""))
        url_value = sanitize_text(item.get("url", "") or item.get("link", ""))
        icon_url = sanitize_text(item.get("icon", "") or item.get("thumbnail", ""))
        updated_at = sanitize_text(item.get("updated_at", "") or item.get("modified", "") or item.get("date", ""))
        category = sanitize_text(item.get("category", ""))

        title_data = item.get("title", {}) if isinstance(item.get("title", {}), dict) else {}
        excerpt_data = item.get("excerpt", {}) if isinstance(item.get("excerpt", {}), dict) else {}
        embedded = item.get("_embedded", {}) if isinstance(item.get("_embedded", {}), dict) else {}

        if not title:
            title = strip_html_tags(title_data.get("rendered", ""))
        if not excerpt:
            excerpt = strip_html_tags(excerpt_data.get("rendered", ""))
        if not icon_url:
            media_list = embedded.get("wp:featuredmedia", []) if isinstance(embedded.get("wp:featuredmedia", []), list) else []
            if media_list and isinstance(media_list[0], dict):
                icon_url = sanitize_text(media_list[0].get("source_url", ""))

        if not post_id:
            post_id = hashlib.sha256((title + "|" + url_value).encode("utf-8")).hexdigest()[:20]
        if not title and not url_value:
            continue

        normalized.append(
            {
                "id": post_id,
                "title": title or "ページ更新",
                "excerpt": excerpt,
                "url": url_value,
                "icon": icon_url,
                "updated_at": updated_at,
                "category": category,
            }
        )

    return normalized


def _build_page_promo_embed(item):
    title = truncate_text(sanitize_text(item.get("title", "ページ更新")), 256)
    excerpt = truncate_text(sanitize_text(item.get("excerpt", "")), 240)
    category = sanitize_text(item.get("category", ""))
    updated_at = sanitize_text(item.get("updated_at", ""))
    url_value = sanitize_text(item.get("url", ""))
    icon = sanitize_text(item.get("icon", ""))

    detail_lines = []
    if excerpt:
        detail_lines.append(excerpt)
    if category:
        detail_lines.append("カテゴリ: {}".format(category))
    if updated_at:
        detail_lines.append("更新: {}".format(updated_at))

    embed = {
        "title": title,
        "description": truncate_text("\n".join(detail_lines), 3800),
        "color": 0x2E7D32,
    }
    if url_value:
        embed["url"] = url_value
    if icon:
        embed["thumbnail"] = {"url": icon}
    return embed


def _build_page_promo_message(page_index, page_count, total_items):
    try:
        msg = PAGE_PROMO_COMMENT_TEMPLATE.format(page=page_index, pages=page_count, total=total_items)
    except Exception:
        msg = "気になるページがあればコメントで教えてください。({}/{})".format(page_index, page_count)
    return truncate_text(sanitize_text(msg), 1900)


def _send_page_promo_batches(items):
    if not DISCORD_PAGE_PROMO_CHANNEL_ID:
        raise RuntimeError("DISCORD_PAGE_PROMO_CHANNEL_ID is not set")

    page_size = max(1, min(PAGE_PROMO_BATCH_SIZE, 10))
    page_count = (len(items) + page_size - 1) // page_size
    sent_messages = 0
    for idx in range(page_count):
        start = idx * page_size
        chunk = items[start : start + page_size]
        embeds = [_build_page_promo_embed(entry) for entry in chunk]
        payload = {
            "content": _build_page_promo_message(idx + 1, page_count, len(items)),
            "embeds": embeds,
        }
        discord_post_json("/channels/{}/messages".format(DISCORD_PAGE_PROMO_CHANNEL_ID), payload)
        sent_messages += 1
    return sent_messages


def sync_wordpress_page_promotions(limit=50, force_send_seen=False):
    if not DISCORD_PAGE_PROMO_CHANNEL_ID:
        return {"ok": False, "error": "DISCORD_PAGE_PROMO_CHANNEL_ID is not set", "sent": 0}

    items = fetch_wordpress_page_promos(limit=limit)
    with page_promo_lock:
        seen = set([str(x) for x in page_promo_state.get("seen_ids", [])])
        primed = bool(page_promo_state.get("primed", False))

    current_ids = [str(item.get("id", "") or "").strip() for item in items if str(item.get("id", "") or "").strip()]

    if PAGE_PROMO_PRIME_ON_START and not primed and not seen and not force_send_seen:
        with page_promo_lock:
            page_promo_state["seen_ids"] = list(set(current_ids))[-5000:]
            page_promo_state["primed"] = True
            page_promo_state["last_run"] = now_iso_utc()
            page_promo_state["last_error"] = ""
        save_social_notify_state(PAGE_PROMO_STATE_FILE, page_promo_lock, page_promo_state)
        return {"ok": True, "sent": 0, "primed": True, "total": len(items), "updated_at": now_iso_utc()}

    pending = []
    for item in reversed(items):
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            continue
        if (not force_send_seen) and item_id in seen:
            continue
        pending.append(item)

    sent_messages = 0
    if pending:
        sent_messages = _send_page_promo_batches(pending)
        for item in pending:
            seen.add(str(item.get("id", "") or "").strip())

    with page_promo_lock:
        page_promo_state["seen_ids"] = list(seen)[-5000:]
        page_promo_state["primed"] = True
        page_promo_state["last_run"] = now_iso_utc()
        page_promo_state["last_error"] = ""
    save_social_notify_state(PAGE_PROMO_STATE_FILE, page_promo_lock, page_promo_state)

    return {
        "ok": True,
        "sent": len(pending),
        "sent_messages": sent_messages,
        "total": len(items),
        "updated_at": now_iso_utc(),
    }


def sync_youtube_notifications(limit=None, force_send_seen=False, min_timestamp=None, wordpress_force_refresh=False, allow_direct_fallback=False):
    def build_error_result(error_text, source="", source_error_text=""):
        error_text = sanitize_text(error_text) or "unknown error"
        with youtube_notify_lock:
            youtube_notify_state["last_run"] = now_iso_utc()
            youtube_notify_state["last_error"] = error_text
            if source:
                youtube_notify_state["last_source"] = source
        save_social_notify_state(YOUTUBE_NOTIFY_STATE_FILE, youtube_notify_lock, youtube_notify_state)

        result = {"ok": False, "error": error_text, "sent": 0}
        if source:
            result["source"] = source
        if source_error_text:
            result["source_error"] = source_error_text
        return result

    if not YOUTUBE_NOTIFY_CHANNEL_ID and not DISCORD_YOUTUBE_MEDIA_CHANNEL_ID:
        return build_error_result("YOUTUBE_NOTIFY_CHANNEL_ID is not set")

    all_items = []
    using_wordpress_source = False
    source_used = "direct"
    source_error = ""
    fetch_limit = max(1, min(int(limit or 50), 100))
    wordpress_enabled = bool(WP_YOUTUBE_WATCH_ENDPOINT and (WP_YOUTUBE_WATCH_TOKEN or WP_SOCIAL_WATCH_TOKEN))
    wordpress_force_refresh = bool(wordpress_force_refresh)
    allow_direct_fallback = bool(allow_direct_fallback)

    if wordpress_enabled:
        try:
            all_items = fetch_wordpress_youtube_feed_entries(
                limit=fetch_limit,
                language="ja",
                today_only=(min_timestamp is None and not force_send_seen),
                order="date",
                force_refresh=wordpress_force_refresh,
            )
            using_wordpress_source = True
            source_used = "wordpress"
        except Exception as exc:
            source_error = str(exc)

    if not using_wordpress_source:
        if wordpress_enabled and not allow_direct_fallback:
            return build_error_result(
                "WP youtube watch failed: {}".format(source_error or "unknown error"),
                source="wordpress",
                source_error_text=source_error,
            )

        channel_ids = parse_csv_list(YOUTUBE_NOTIFY_CHANNEL_IDS)
        if not channel_ids:
            error_text = "YOUTUBE_NOTIFY_CHANNEL_IDS is empty"
            if source_error:
                error_text = "{} (WP youtube fallback failed: {})".format(error_text, source_error)
            return build_error_result(error_text, source="direct", source_error_text=source_error)

        for channel_id in channel_ids:
            all_items.extend(fetch_youtube_feed_entries(channel_id))

    with youtube_notify_lock:
        seen = set([str(x) for x in youtube_notify_state.get("seen_ids", [])])
        primed = bool(youtube_notify_state.get("primed", False))

    current_ids = [str(item.get("video_id", "") or "").strip() for item in all_items if str(item.get("video_id", "") or "").strip()]

    # 初回起動時は既存動画を既読化して通知スパムを防ぐ。
    if YOUTUBE_NOTIFY_PRIME_ON_START and not primed and not seen and not force_send_seen and min_timestamp is None:
        with youtube_notify_lock:
            youtube_notify_state["seen_ids"] = list(set(current_ids))[-2000:]
            youtube_notify_state["primed"] = True
            youtube_notify_state["last_run"] = now_iso_utc()
            youtube_notify_state["last_error"] = ""
            youtube_notify_state["last_source"] = source_used
        save_social_notify_state(YOUTUBE_NOTIFY_STATE_FILE, youtube_notify_lock, youtube_notify_state)
        return {"ok": True, "sent": 0, "primed": True, "total": len(all_items), "source": source_used, "updated_at": now_iso_utc()}

    pending = []
    source_items = list(all_items if using_wordpress_source else reversed(all_items))
    for item in source_items:
        video_id = str(item.get("video_id", "") or "").strip()
        if not video_id:
            continue
        if min_timestamp is not None:
            published_ts = parse_wp_datetime_to_epoch(item.get("published", ""))
            if published_ts is None or published_ts < min_timestamp:
                continue
        if (not force_send_seen) and video_id in seen:
            continue
        pending.append(item)

    if limit is not None:
        capped_limit = max(1, min(int(limit or 20), 100))
        if len(pending) > capped_limit:
            pending = pending[:capped_limit] if using_wordpress_source else pending[-capped_limit:]

    sent = 0
    for item in pending:
        video_id = str(item.get("video_id", "") or "").strip()
        payload = build_youtube_message_payload(item, include_save_button=bool(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID))
        post_youtube_notification_message(item, payload)
        seen.add(video_id)
        sent += 1

    with youtube_notify_lock:
        youtube_notify_state["seen_ids"] = list(seen)[-2000:]
        youtube_notify_state["primed"] = True
        youtube_notify_state["last_run"] = now_iso_utc()
        youtube_notify_state["last_error"] = ""
        youtube_notify_state["last_source"] = source_used
    save_social_notify_state(YOUTUBE_NOTIFY_STATE_FILE, youtube_notify_lock, youtube_notify_state)

    return {
        "ok": True,
        "sent": sent,
        "total": len(all_items),
        "filtered_total": len(pending),
        "source": source_used,
        "source_error": source_error,
        "force_send_seen": bool(force_send_seen),
        "updated_at": now_iso_utc(),
    }


def sync_youtube_comment_notifications(limit=None, force_send_seen=False, min_timestamp=None):
    def build_error_result(error_text):
        error_text = sanitize_text(error_text) or "unknown error"
        with youtube_comments_notify_lock:
            youtube_comments_notify_state["last_run"] = now_iso_utc()
            youtube_comments_notify_state["last_error"] = error_text
            youtube_comments_notify_state["last_source"] = "direct"
            youtube_comments_notify_state["last_total"] = 0
        save_social_notify_state(YOUTUBE_COMMENTS_NOTIFY_STATE_FILE, youtube_comments_notify_lock, youtube_comments_notify_state)
        return {"ok": False, "error": error_text, "sent": 0, "source": "direct"}

    if not YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID and not DISCORD_YOUTUBE_MEDIA_CHANNEL_ID:
        return build_error_result("YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID is not set")

    channel_ids = parse_csv_list(YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS)
    if not channel_ids:
        return build_error_result("YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS is empty")

    fetch_limit = max(1, min(int(limit or YOUTUBE_COMMENTS_FETCH_LIMIT), 100))
    all_items = fetch_youtube_comment_entries(
        channel_ids,
        limit=fetch_limit,
        video_limit=YOUTUBE_COMMENTS_VIDEO_LIMIT,
        per_video_limit=YOUTUBE_COMMENTS_PER_VIDEO_LIMIT,
    )

    with youtube_comments_notify_lock:
        seen = set([str(x) for x in youtube_comments_notify_state.get("seen_ids", [])])
        primed = bool(youtube_comments_notify_state.get("primed", False))

    current_ids = [str(item.get("id", "") or "").strip() for item in all_items if str(item.get("id", "") or "").strip()]

    if YOUTUBE_COMMENTS_NOTIFY_PRIME_ON_START and not primed and not seen and not force_send_seen and min_timestamp is None:
        with youtube_comments_notify_lock:
            youtube_comments_notify_state["seen_ids"] = list(set(current_ids))[-2000:]
            youtube_comments_notify_state["primed"] = True
            youtube_comments_notify_state["last_run"] = now_iso_utc()
            youtube_comments_notify_state["last_error"] = ""
            youtube_comments_notify_state["last_source"] = "direct"
            youtube_comments_notify_state["last_total"] = len(all_items)
            youtube_comments_notify_state["recent_items"] = build_recent_youtube_comment_items(all_items)
        save_social_notify_state(YOUTUBE_COMMENTS_NOTIFY_STATE_FILE, youtube_comments_notify_lock, youtube_comments_notify_state)
        return {"ok": True, "sent": 0, "primed": True, "total": len(all_items), "source": "direct", "updated_at": now_iso_utc()}

    pending = []
    for item in reversed(all_items):
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            continue
        if min_timestamp is not None:
            published_ts = parse_wp_datetime_to_epoch(item.get("published", ""))
            if published_ts is None or published_ts < min_timestamp:
                continue
        if (not force_send_seen) and item_id in seen:
            continue
        pending.append(item)

    if len(pending) > fetch_limit:
        pending = pending[-fetch_limit:]

    sent = 0
    for item in pending:
        item_id = str(item.get("id", "") or "").strip()
        payload = build_youtube_comment_message_payload(item, include_save_button=bool(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID))
        post_youtube_comment_notification_message(item, payload)
        seen.add(item_id)
        sent += 1

    with youtube_comments_notify_lock:
        youtube_comments_notify_state["seen_ids"] = list(seen)[-2000:]
        youtube_comments_notify_state["primed"] = True
        youtube_comments_notify_state["last_run"] = now_iso_utc()
        youtube_comments_notify_state["last_error"] = ""
        youtube_comments_notify_state["last_source"] = "direct"
        youtube_comments_notify_state["last_total"] = len(all_items)
        youtube_comments_notify_state["recent_items"] = build_recent_youtube_comment_items(all_items)
    save_social_notify_state(YOUTUBE_COMMENTS_NOTIFY_STATE_FILE, youtube_comments_notify_lock, youtube_comments_notify_state)

    return {
        "ok": True,
        "sent": sent,
        "total": len(all_items),
        "filtered_total": len(pending),
        "source": "direct",
        "force_send_seen": bool(force_send_seen),
        "updated_at": now_iso_utc(),
    }


def sync_youtube_livechat_notifications(limit=None, force_send_seen=False, min_timestamp=None):
    def build_error_result(error_text):
        error_text = sanitize_text(error_text) or "unknown error"
        with youtube_livechat_notify_lock:
            youtube_livechat_notify_state["last_run"] = now_iso_utc()
            youtube_livechat_notify_state["last_error"] = error_text
            youtube_livechat_notify_state["last_source"] = "direct"
            youtube_livechat_notify_state["last_total"] = 0
        save_social_notify_state(YOUTUBE_LIVECHAT_STATE_FILE, youtube_livechat_notify_lock, youtube_livechat_notify_state)
        return {"ok": False, "error": error_text, "sent": 0, "source": "direct"}

    if not YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID and not DISCORD_YOUTUBE_MEDIA_CHANNEL_ID:
        return build_error_result("YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID is not set")

    channel_ids = parse_csv_list(YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_IDS)
    if not channel_ids:
        return build_error_result("YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_IDS is empty")

    with youtube_livechat_notify_lock:
        seen = set([str(x) for x in youtube_livechat_notify_state.get("seen_ids", [])])
        primed = bool(youtube_livechat_notify_state.get("primed", False))
        page_tokens = dict(youtube_livechat_notify_state.get("page_tokens", {}) if isinstance(youtube_livechat_notify_state.get("page_tokens"), dict) else {})

    fetch_limit = max(1, min(int(limit or YOUTUBE_LIVECHAT_FETCH_LIMIT), 200))
    livechat_data = fetch_youtube_livechat_entries(
        channel_ids,
        limit=fetch_limit,
        video_limit=YOUTUBE_LIVECHAT_VIDEO_LIMIT,
        page_tokens={} if force_send_seen else page_tokens,
        prime_missing_tokens=not force_send_seen,
    )
    all_items = list(livechat_data.get("items", []) if isinstance(livechat_data, dict) else [])
    next_page_tokens = dict(livechat_data.get("next_page_tokens", {}) if isinstance(livechat_data.get("next_page_tokens"), dict) else {})
    active_chat_ids = [str(value) for value in livechat_data.get("active_chat_ids", []) if str(value).strip()] if isinstance(livechat_data, dict) else []
    active_video_ids = [str(value) for value in livechat_data.get("active_video_ids", []) if str(value).strip()] if isinstance(livechat_data, dict) else []

    current_ids = [str(item.get("id", "") or "").strip() for item in all_items if str(item.get("id", "") or "").strip()]

    if YOUTUBE_LIVECHAT_NOTIFY_PRIME_ON_START and not primed and not seen and not force_send_seen:
        with youtube_livechat_notify_lock:
            youtube_livechat_notify_state["seen_ids"] = list(set(current_ids))[-2000:]
            youtube_livechat_notify_state["primed"] = True
            youtube_livechat_notify_state["last_run"] = now_iso_utc()
            youtube_livechat_notify_state["last_error"] = ""
            youtube_livechat_notify_state["last_source"] = "direct"
            youtube_livechat_notify_state["last_total"] = len(all_items)
            youtube_livechat_notify_state["page_tokens"] = next_page_tokens
            youtube_livechat_notify_state["active_chat_ids"] = active_chat_ids[:50]
            youtube_livechat_notify_state["active_video_ids"] = active_video_ids[:50]
            youtube_livechat_notify_state["recent_items"] = build_recent_youtube_livechat_items(all_items)
        save_social_notify_state(YOUTUBE_LIVECHAT_STATE_FILE, youtube_livechat_notify_lock, youtube_livechat_notify_state)
        return {
            "ok": True,
            "sent": 0,
            "primed": True,
            "total": len(all_items),
            "active_chat_count": len(active_chat_ids),
            "source": "direct",
            "updated_at": now_iso_utc(),
        }

    pending = []
    for item in reversed(all_items):
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            continue
        if min_timestamp is not None:
            published_ts = parse_wp_datetime_to_epoch(item.get("published", ""))
            if published_ts is None or published_ts < min_timestamp:
                continue
        if (not force_send_seen) and item_id in seen:
            continue
        pending.append(item)

    if len(pending) > fetch_limit:
        pending = pending[-fetch_limit:]

    sent = 0
    for item in pending:
        item_id = str(item.get("id", "") or "").strip()
        payload = build_youtube_livechat_message_payload(item, include_save_button=bool(DISCORD_YOUTUBE_MEDIA_CHANNEL_ID))
        post_youtube_livechat_notification_message(item, payload)
        seen.add(item_id)
        sent += 1

    with youtube_livechat_notify_lock:
        youtube_livechat_notify_state["seen_ids"] = list(seen)[-2000:]
        youtube_livechat_notify_state["primed"] = True
        youtube_livechat_notify_state["last_run"] = now_iso_utc()
        youtube_livechat_notify_state["last_error"] = ""
        youtube_livechat_notify_state["last_source"] = "direct"
        youtube_livechat_notify_state["last_total"] = len(all_items)
        youtube_livechat_notify_state["page_tokens"] = next_page_tokens
        youtube_livechat_notify_state["active_chat_ids"] = active_chat_ids[:50]
        youtube_livechat_notify_state["active_video_ids"] = active_video_ids[:50]
        youtube_livechat_notify_state["recent_items"] = build_recent_youtube_livechat_items(all_items)
    save_social_notify_state(YOUTUBE_LIVECHAT_STATE_FILE, youtube_livechat_notify_lock, youtube_livechat_notify_state)

    return {
        "ok": True,
        "sent": sent,
        "total": len(all_items),
        "filtered_total": len(pending),
        "active_chat_count": len(active_chat_ids),
        "source": "direct",
        "force_send_seen": bool(force_send_seen),
        "updated_at": now_iso_utc(),
    }


def fetch_wordpress_nexus_watch(limit=10):
    return get_nexus_watcher().fetch_wordpress_items(limit=limit)


def fetch_wordpress_nexus_fallback_posts(limit=10):
    return get_nexus_watcher().fetch_fallback_posts(limit=limit)


def parse_wp_datetime_to_epoch(value):
    text = sanitize_text(value)
    if not text:
        return None
    patterns = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(text, pattern)
            return dt.timestamp()
        except Exception:
            continue
    return None


def parse_request_bool(value):
    return sanitize_text(value).lower() in ("1", "true", "on", "yes")


def resolve_sync_request_options(body, default_limit, max_limit=100):
    body = body if isinstance(body, dict) else {}

    limit = int(body.get("limit", default_limit) or default_limit)
    if limit < 1:
        limit = 1
    if limit > max_limit:
        limit = max_limit

    force_send_seen = parse_request_bool(body.get("force", ""))
    backfill_days_raw = body.get("backfill_days", "")
    backfill_days = None
    min_timestamp = None

    if str(backfill_days_raw).strip() != "":
        backfill_days = float(backfill_days_raw)
        if backfill_days <= 0:
            raise ValueError("backfill_days must be greater than 0")
        if backfill_days > 30:
            backfill_days = 30.0
        min_timestamp = time.time() - (backfill_days * 86400.0)
        force_send_seen = True

    return {
        "limit": limit,
        "force_send_seen": force_send_seen,
        "backfill_days": backfill_days,
        "min_timestamp": min_timestamp,
    }


def fetch_wordpress_social_watch(limit=20):
    if not WP_SOCIAL_WATCH_ENDPOINT:
        raise RuntimeError("WP_SOCIAL_WATCH_ENDPOINT is not set")
    if not WP_SOCIAL_WATCH_TOKEN:
        raise RuntimeError("WP_SOCIAL_WATCH_TOKEN is not set")

    url = "{}{}limit={}".format(
        WP_SOCIAL_WATCH_ENDPOINT,
        "&" if "?" in WP_SOCIAL_WATCH_ENDPOINT else "?",
        max(1, min(int(limit or 20), 100)),
    )
    req = Request(url)
    for key, value in build_wordpress_watch_headers(WP_SOCIAL_WATCH_TOKEN, WP_SOCIAL_WATCH_ENDPOINT).items():
        req.add_header(key, value)

    with urlopen(req, timeout=WP_BRIDGE_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise RuntimeError("WP social watch response is invalid")
    return data


def build_wordpress_watch_headers(token, endpoint_url):
    headers = {
        "User-Agent": "DiscordBotBridge/1.0",
    }
    token_text = sanitize_text(token)
    if token_text:
        headers["Authorization"] = "Bearer {}".format(token_text)
        headers["X-Sevendtd-Bearer"] = token_text

    endpoint_host = sanitize_text(urlsplit(str(endpoint_url or "")).hostname or "").lower()
    site_host = ""
    for candidate in (
        WP_SOCIAL_WATCH_ENDPOINT,
        WP_NEXUS_CATEGORIES_ENDPOINT,
        WP_NEXUS_WATCH_ENDPOINT,
        WP_TWITCH_WATCH_ENDPOINT,
        WP_YOUTUBE_WATCH_ENDPOINT,
        WP_TWITTER_WATCH_ENDPOINT,
        WP_COMMENTS_WATCH_ENDPOINT,
    ):
        candidate_host = sanitize_text(urlsplit(str(candidate or "")).hostname or "").lower()
        if candidate_host and candidate_host not in ("127.0.0.1", "localhost"):
            site_host = candidate_host
            break

    if endpoint_host in ("127.0.0.1", "localhost") and site_host:
        headers["Host"] = site_host

    return headers


def fetch_wordpress_youtube_watch(limit=20, language="ja", today_only=True, order="date", force_refresh=False, game_keyword=""):
    endpoint = (WP_YOUTUBE_WATCH_ENDPOINT or "").strip()
    token = (WP_YOUTUBE_WATCH_TOKEN or WP_SOCIAL_WATCH_TOKEN or "").strip()
    if not endpoint:
        raise RuntimeError("WP_YOUTUBE_WATCH_ENDPOINT is not set")
    if not token:
        raise RuntimeError("WP_YOUTUBE_WATCH_TOKEN is not set")

    params = {
        "limit": max(1, min(int(limit or 20), 100)),
        "language": sanitize_text(language or "ja") or "ja",
        "today_only": "1" if today_only else "0",
        "order": sanitize_text(order or "date") or "date",
    }
    if force_refresh:
        params["force_refresh"] = "1"
    keyword_text = sanitize_text(game_keyword)
    if keyword_text:
        params["game_keyword"] = keyword_text

    url = "{}{}{}".format(
        endpoint,
        "&" if "?" in endpoint else "?",
        urlencode(params),
    )
    headers = build_wordpress_watch_headers(token, endpoint)
    data = fetch_json_request(url, headers=headers, timeout=WP_BRIDGE_TIMEOUT)
    if not isinstance(data, dict):
        raise RuntimeError("WP youtube watch response is invalid")
    return data


def normalize_wordpress_youtube_item(item):
    if not isinstance(item, dict):
        return {}

    video_id = sanitize_text(item.get("id", ""))
    channel_id = sanitize_text(item.get("channel_id", ""))
    channel_name = sanitize_text(item.get("channel", "")) or sanitize_text(item.get("member_display_name", "Unknown")) or "Unknown"
    video_url = sanitize_text(item.get("url", "") or "https://www.youtube.com/watch?v={}".format(video_id))
    channel_url = "https://www.youtube.com/channel/{}".format(channel_id) if channel_id else ""

    return {
        "video_id": video_id,
        "title": sanitize_text(item.get("title", "")),
        "published": sanitize_text(item.get("published_at", "")),
        "author": channel_name,
        "channel_id": channel_id,
        "url": video_url,
        "channel_url": channel_url,
        "thumbnail_url": sanitize_text(item.get("thumbnail", "") or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id)),
        "is_linked_member": bool(item.get("is_linked_member")),
        "member_display_name": sanitize_text(item.get("member_display_name", "")),
        "member_level": sanitize_text(item.get("member_level", "")),
    }


def fetch_wordpress_youtube_feed_entries(limit=20, language="ja", today_only=True, order="date", force_refresh=False, game_keyword=""):
    data = fetch_wordpress_youtube_watch(
        limit=limit,
        language=language,
        today_only=today_only,
        order=order,
        force_refresh=force_refresh,
        game_keyword=game_keyword,
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []

    normalized = []
    for item in items:
        row = normalize_wordpress_youtube_item(item)
        if row.get("video_id"):
            normalized.append(row)
    return normalized


def format_nexus_notification(item):
    return get_nexus_watcher().format_plaintext_notification(item)


def format_social_notification(item):
    platform = sanitize_text(item.get("platform", "social"))
    title = sanitize_text(item.get("title", "新着コンテンツ"))
    author = sanitize_text(item.get("author", ""))
    channel_name = sanitize_text(item.get("channel_name", ""))
    published_at = sanitize_text(item.get("published_at", ""))
    category = sanitize_text(item.get("category", ""))
    score = item.get("score", "")
    url = sanitize_text(item.get("url", ""))

    lines = ["【ソーシャル新着通知】", "[{}] {}".format(platform.upper(), title)]
    if author:
        lines.append("投稿者: {}".format(author))
    if channel_name:
        lines.append("チャンネル: {}".format(channel_name))
    if category:
        lines.append("カテゴリ: {}".format(category))
    if published_at:
        lines.append("公開時刻: {}".format(published_at))
    if str(score).strip() != "":
        lines.append("スコア: {}".format(score))
    if url:
        lines.append(url)

    return "\n".join(lines)[:1900]


def sync_nexus_watch_notifications(limit=10, force_send_seen=False, min_timestamp=None):
    return get_nexus_watcher().poll_once(
        limit=limit,
        force_send_seen=force_send_seen,
        min_timestamp=min_timestamp,
    )


def sync_social_watch_notifications(limit=20):
    if not DISCORD_SOCIAL_NOTIFY_CHANNEL_ID:
        return {"ok": False, "error": "DISCORD_SOCIAL_NOTIFY_CHANNEL_ID is not set", "sent": 0}

    data = fetch_wordpress_social_watch(limit=limit)
    items = data.get("items", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []

    with social_notify_lock:
        seen = set([str(x) for x in social_notify_state.get("seen_ids", [])])
        primed = bool(social_notify_state.get("primed", False))

    current_ids = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            item_id = str(item.get("url", "") or "").strip() or sanitize_text(item.get("title", ""))
        if item_id:
            current_ids.append(item_id)

    if not primed and not seen:
        with social_notify_lock:
            social_notify_state["seen_ids"] = list(set(current_ids))[-2000:]
            social_notify_state["primed"] = True
            social_notify_state["last_run"] = now_iso_utc()
            social_notify_state["last_error"] = ""
        save_social_notify_state(SOCIAL_NOTIFY_STATE_FILE, social_notify_lock, social_notify_state)
        return {"ok": True, "sent": 0, "primed": True, "total": len(items), "updated_at": now_iso_utc()}

    sent = 0
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            item_id = str(item.get("url", "") or "").strip() or sanitize_text(item.get("title", ""))
        if item_id == "" or item_id in seen:
            continue

        message = format_social_notification(item)
        discord_post_json(
            "/channels/{}/messages".format(DISCORD_SOCIAL_NOTIFY_CHANNEL_ID),
            {"content": message},
        )
        seen.add(item_id)
        sent += 1

    with social_notify_lock:
        social_notify_state["seen_ids"] = list(seen)[-2000:]
        social_notify_state["primed"] = True
        social_notify_state["last_run"] = now_iso_utc()
        social_notify_state["last_error"] = ""
    save_social_notify_state(SOCIAL_NOTIFY_STATE_FILE, social_notify_lock, social_notify_state)

    return {"ok": True, "sent": sent, "total": len(items), "updated_at": now_iso_utc()}


def fetch_wordpress_comment_updates(limit=20):
    if not WP_COMMENTS_WATCH_ENDPOINT:
        raise RuntimeError("WP_COMMENTS_WATCH_ENDPOINT is not set")

    capped = max(1, min(int(limit or 20), 100))
    url = "{}{}limit={}".format(
        WP_COMMENTS_WATCH_ENDPOINT,
        "&" if "?" in WP_COMMENTS_WATCH_ENDPOINT else "?",
        capped,
    )
    req = Request(url)
    for key, value in build_wordpress_watch_headers(WP_COMMENTS_WATCH_TOKEN, WP_COMMENTS_WATCH_ENDPOINT).items():
        req.add_header(key, value)

    with urlopen(req, timeout=WP_BRIDGE_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw.strip() else {}

    items = []
    if isinstance(data, dict):
        src_items = data.get("items", [])
        if isinstance(src_items, list):
            items = src_items
    elif isinstance(data, list):
        items = data

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cid = sanitize_text(item.get("id", ""))
        author = sanitize_text(item.get("author", ""))
        post_title = sanitize_text(item.get("post_title", ""))
        content = strip_html_tags(item.get("content", ""))
        published_at = sanitize_text(item.get("published_at", "") or item.get("date", ""))
        url = sanitize_text(item.get("url", "") or item.get("link", ""))
        if not cid and url:
            cid = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        if not cid:
            continue
        normalized.append(
            {
                "id": cid,
                "author": author,
                "post_title": post_title,
                "content": content,
                "published_at": published_at,
                "url": url,
            }
        )

    return normalized


def format_comment_notification(item):
    author = sanitize_text(item.get("author", "")) or "Unknown"
    post_title = sanitize_text(item.get("post_title", "")) or "記事"
    content = truncate_text(sanitize_text(item.get("content", "")), 300)
    published_at = sanitize_text(item.get("published_at", ""))
    url = sanitize_text(item.get("url", ""))

    lines = ["【コメント通知】", "記事: {}".format(post_title), "投稿者: {}".format(author)]
    if published_at:
        lines.append("時刻: {}".format(published_at))
    if content:
        lines.append("内容: {}".format(content))
    if url:
        lines.append(url)
    return "\n".join(lines)[:1900]


def sync_comment_notifications(limit=20):
    if not DISCORD_COMMENTS_NOTIFY_CHANNEL_ID:
        return {"ok": False, "error": "DISCORD_COMMENTS_NOTIFY_CHANNEL_ID is not set", "sent": 0}

    items = fetch_wordpress_comment_updates(limit=limit)

    with comments_notify_lock:
        seen = set([str(x) for x in comments_notify_state.get("seen_ids", [])])
        primed = bool(comments_notify_state.get("primed", False))

    current_ids = [str(item.get("id", "") or "").strip() for item in items if str(item.get("id", "") or "").strip()]

    if not primed and not seen:
        with comments_notify_lock:
            comments_notify_state["seen_ids"] = list(set(current_ids))[-2000:]
            comments_notify_state["primed"] = True
            comments_notify_state["last_run"] = now_iso_utc()
            comments_notify_state["last_error"] = ""
        save_social_notify_state(COMMENTS_NOTIFY_STATE_FILE, comments_notify_lock, comments_notify_state)
        return {"ok": True, "sent": 0, "primed": True, "total": len(items), "updated_at": now_iso_utc()}

    sent = 0
    for item in reversed(items):
        item_id = str(item.get("id", "") or "").strip()
        if not item_id or item_id in seen:
            continue
        message = format_comment_notification(item)
        discord_post_json("/channels/{}/messages".format(DISCORD_COMMENTS_NOTIFY_CHANNEL_ID), {"content": message})
        seen.add(item_id)
        sent += 1

    with comments_notify_lock:
        comments_notify_state["seen_ids"] = list(seen)[-2000:]
        comments_notify_state["primed"] = True
        comments_notify_state["last_run"] = now_iso_utc()
        comments_notify_state["last_error"] = ""
    save_social_notify_state(COMMENTS_NOTIFY_STATE_FILE, comments_notify_lock, comments_notify_state)

    return {"ok": True, "sent": sent, "total": len(items), "updated_at": now_iso_utc()}


def _fetch_guild_members_paginated(max_members=5000):
    members = []
    after = ""
    while True:
        path = "/guilds/{}/members?limit=1000".format(DISCORD_GUILD_ID)
        if after:
            path += "&after={}".format(after)

        chunk = discord_request_json(path)
        if not isinstance(chunk, list):
            raise RuntimeError("guild members response is invalid")
        if not chunk:
            break

        for member in chunk:
            if isinstance(member, dict):
                members.append(member)

        if len(chunk) < 1000 or len(members) >= max_members:
            break

        last = chunk[-1] if isinstance(chunk[-1], dict) else {}
        last_user = last.get("user", {}) if isinstance(last.get("user", {}), dict) else {}
        after = str(last_user.get("id", "") or last.get("id", "")).strip()
        if not after:
            break

    return members[:max_members]


def _build_instance_role_member_sets(instance_role_ids, members):
    role_member_sets = {str(role_id): set() for role_id in instance_role_ids}
    for member in members:
        if not isinstance(member, dict):
            continue
        user = member.get("user", {}) if isinstance(member.get("user", {}), dict) else {}
        user_id = str(user.get("id", "") or member.get("id", "")).strip()
        if not user_id:
            continue

        role_ids = member.get("roles", []) if isinstance(member.get("roles", []), list) else []
        for role_id in role_ids:
            role_id = str(role_id or "").strip()
            if role_id in role_member_sets:
                role_member_sets[role_id].add(user_id)
    return role_member_sets


def fetch_voice_runtime_stats():
    if not DISCORD_GUILD_ID:
        return {"ok": False, "voice_member_count": 0, "active_voice_channel_count": 0, "error": "DISCORD_GUILD_ID is not set"}
    runtime = ensure_gateway_runtime()
    if not runtime.get("runtime_ok"):
        return {"ok": False, "voice_member_count": 0, "active_voice_channel_count": 0, "error": "Discord gateway not connected"}

    async def _collect():
        guild = _discord_client.get_guild(int(DISCORD_GUILD_ID))
        if guild is None:
            raise RuntimeError("guild is not cached yet")

        active_voice_channel_count = 0
        voice_member_ids = set()

        for channel in list(getattr(guild, "channels", []) or []):
            channel_type = _discord_channel_type_value(getattr(channel, "type", 0))
            if channel_type not in (2, 13):
                continue

            members = list(getattr(channel, "members", []) or [])
            if members:
                active_voice_channel_count += 1
            for member in members:
                member_id = str(getattr(member, "id", "") or "").strip()
                if member_id:
                    voice_member_ids.add(member_id)

        return {
            "ok": True,
            "voice_member_count": len(voice_member_ids),
            "active_voice_channel_count": active_voice_channel_count,
        }

    try:
        future = asyncio.run_coroutine_threadsafe(_collect(), _discord_loop)
        return future.result(timeout=8)
    except Exception as exc:
        return {"ok": False, "voice_member_count": 0, "active_voice_channel_count": 0, "error": str(exc)}


def fetch_active_threads():
    if not DISCORD_GUILD_ID:
        raise RuntimeError("DISCORD_GUILD_ID is not set")
    if not DISCORD_THREAD_CHANNEL_ID:
        raise RuntimeError("DISCORD_THREAD_CHANNEL_ID is not set")

    data = discord_request_json("/guilds/{}/threads/active".format(DISCORD_GUILD_ID))
    roles_data = discord_request_json("/guilds/{}/roles".format(DISCORD_GUILD_ID))
    channels_data = discord_request_json("/guilds/{}/channels".format(DISCORD_GUILD_ID))

    if not isinstance(roles_data, list):
        raise RuntimeError("guild roles response is invalid")
    if not isinstance(channels_data, list):
        raise RuntimeError("guild channels response is invalid")

    normalized_prefix = _normalize_instance_role_prefix(DISCORD_INSTANCE_ROLE_PREFIX)
    instance_role_map = {}
    for role in roles_data:
        if not isinstance(role, dict):
            continue
        role_id = str(role.get("id", "") or "").strip()
        role_name = sanitize_text(role.get("name", ""))
        if role_id and role_name and role_name.lower().startswith(normalized_prefix):
            instance_role_map[role_id] = role_name

    instance_role_ids = list(instance_role_map.keys())
    instance_role_member_sets = {}
    role_count_error = ""
    if instance_role_ids:
        try:
            members = _fetch_guild_members_paginated(max_members=5000)
            instance_role_member_sets = _build_instance_role_member_sets(instance_role_ids, members)
        except Exception as exc:
            role_count_error = str(exc)

    everyone_role_id = DISCORD_GUILD_ID
    categories = {}
    channel_meta = {}
    text_channel_count = 0
    forum_channel_count = 0
    voice_channel_count = 0

    for channel in channels_data:
        if not isinstance(channel, dict):
            continue

        channel_id = str(channel.get("id", "") or "").strip()
        if not channel_id:
            continue

        channel_type = _discord_int(channel.get("type", 0))
        required_role_ids, everyone_denied = _extract_instance_visibility(channel, instance_role_map, everyone_role_id)

        if channel_type in (0, 5):
            text_channel_count += 1
        elif channel_type == 15:
            forum_channel_count += 1
        elif channel_type in (2, 13):
            voice_channel_count += 1

        channel_meta[channel_id] = {
            "parent_id": str(channel.get("parent_id", "") or "").strip(),
            "required_role_ids": required_role_ids,
            "everyone_denied": everyone_denied,
            "name": sanitize_text(channel.get("name", "")),
            "type": channel_type,
        }

        if channel_type == 4:
            categories[channel_id] = {
                "required_role_ids": required_role_ids,
                "everyone_denied": everyone_denied,
            }

    threads = data.get("threads", []) if isinstance(data, dict) else []
    items = []
    total_thread_messages = 0
    total_thread_participants = 0

    for t in threads:
        if not isinstance(t, dict):
            continue
        thread_id = str(t.get("id", ""))
        parent_id = str(t.get("parent_id", ""))
        if parent_id and DISCORD_THREAD_CHANNEL_ID and parent_id != DISCORD_THREAD_CHANNEL_ID:
            continue

        direct_role_ids, direct_everyone_denied = _extract_instance_visibility(t, instance_role_map, everyone_role_id)
        thread_parent = channel_meta.get(parent_id, {}) if parent_id else {}
        parent_category = categories.get(thread_parent.get("parent_id", ""), {}) if isinstance(thread_parent, dict) else {}

        required_role_ids = list(direct_role_ids)
        required_everyone_denied = direct_everyone_denied

        if not required_role_ids:
            parent_role_ids = thread_parent.get("required_role_ids", []) if isinstance(thread_parent, dict) else []
            if parent_role_ids:
                required_role_ids = list(parent_role_ids)
                required_everyone_denied = bool(thread_parent.get("everyone_denied", False))

        if not required_role_ids and parent_category:
            category_role_ids = parent_category.get("required_role_ids", []) if isinstance(parent_category, dict) else []
            if category_role_ids:
                required_role_ids = list(category_role_ids)
                required_everyone_denied = bool(parent_category.get("everyone_denied", False))

        member_count = int(t.get("member_count", 0) or 0)
        participant_count = member_count
        participant_source = "thread_member"

        if required_role_ids and required_everyone_denied and instance_role_member_sets:
            participant_ids = set()
            for role_id in required_role_ids:
                participant_ids.update(instance_role_member_sets.get(role_id, set()))
            participant_count = len(participant_ids)
            participant_source = "instance_role"

        message_count = int(t.get("message_count", 0) or 0)
        total_thread_messages += message_count
        total_thread_participants += participant_count

        required_role_names = [instance_role_map[rid] for rid in required_role_ids if rid in instance_role_map]

        items.append(
            {
                "id": thread_id,
                "name": t.get("name", ""),
                "url": "https://discord.com/channels/{}/{}/{}".format(DISCORD_GUILD_ID, DISCORD_THREAD_CHANNEL_ID, thread_id),
                "archived": bool(t.get("thread_metadata", {}).get("archived", False)),
                "locked": bool(t.get("thread_metadata", {}).get("locked", False)),
                "message_count": message_count,
                "member_count": member_count,
                "participant_count": participant_count,
                "participant_source": participant_source,
                "required_roles": required_role_names,
                "last_message_id": t.get("last_message_id"),
            }
        )

    instance_member_ids = set()
    for member_set in instance_role_member_sets.values():
        instance_member_ids.update(member_set)

    capacity_map = _parse_instance_role_capacity_map(DISCORD_INSTANCE_ROLE_CAPACITY)
    instance_role_items = []
    total_capacity = 0
    total_members_with_capacity = 0
    full_role_count = 0
    for role_id, role_name in sorted(instance_role_map.items(), key=lambda item: item[1].lower()):
        member_count = len(instance_role_member_sets.get(role_id, set())) if instance_role_member_sets else 0
        capacity = 0
        role_id_key = sanitize_text(role_id).lower()
        role_name_key = sanitize_text(role_name).lower()
        if role_id_key in capacity_map:
            capacity = int(capacity_map.get(role_id_key, 0) or 0)
        elif role_name_key in capacity_map:
            capacity = int(capacity_map.get(role_name_key, 0) or 0)
        elif DISCORD_INSTANCE_ROLE_DEFAULT_CAPACITY > 0:
            capacity = DISCORD_INSTANCE_ROLE_DEFAULT_CAPACITY

        occupancy_rate = None
        remaining = None
        is_full = False
        if capacity > 0:
            total_capacity += capacity
            total_members_with_capacity += member_count
            occupancy_rate = round((float(member_count) / float(capacity)) * 100.0, 1)
            remaining = capacity - member_count
            is_full = member_count >= capacity
            if is_full:
                full_role_count += 1

        instance_role_items.append(
            {
                "role_id": role_id,
                "role_name": role_name,
                "member_count": member_count,
                "capacity": capacity,
                "occupancy_rate": occupancy_rate,
                "remaining": remaining,
                "is_full": is_full,
            }
        )

    delta24 = _compute_delta24h_metrics(total_thread_messages, total_thread_participants, len(instance_member_ids))

    voice_stats = fetch_voice_runtime_stats()

    return {
        "ok": True,
        "channel_id": DISCORD_THREAD_CHANNEL_ID,
        "count": len(items),
        "thread_message_total": total_thread_messages,
        "thread_participant_total": total_thread_participants,
        "instance_role_prefix": normalized_prefix,
        "instance_role_count": len(instance_role_map),
        "instance_member_total": len(instance_member_ids),
        "instance_role_member_count_available": bool(instance_role_member_sets),
        "instance_role_member_count_error": role_count_error,
        "instance_roles": instance_role_items,
        "instance_capacity_total": total_capacity,
        "instance_member_total_with_capacity": total_members_with_capacity,
        "instance_occupancy_rate": round((float(total_members_with_capacity) / float(total_capacity)) * 100.0, 1) if total_capacity > 0 else None,
        "instance_full_role_count": full_role_count,
        "text_channel_count": text_channel_count,
        "forum_channel_count": forum_channel_count,
        "voice_channel_count": voice_channel_count,
        "active_voice_channel_count": int(voice_stats.get("active_voice_channel_count", 0) or 0),
        "voice_member_count": int(voice_stats.get("voice_member_count", 0) or 0),
        "voice_count_source": "gateway" if voice_stats.get("ok") else "unavailable",
        "voice_count_error": "" if voice_stats.get("ok") else str(voice_stats.get("error", "") or ""),
        "delta24h_available": bool(delta24.get("delta24h_available")),
        "delta24h_hours_covered": int(delta24.get("delta24h_hours_covered", 0) or 0),
        "thread_message_delta24h": int(delta24.get("thread_message_delta24h", 0) or 0),
        "thread_participant_delta24h": int(delta24.get("thread_participant_delta24h", 0) or 0),
        "instance_member_delta24h": int(delta24.get("instance_member_delta24h", 0) or 0),
        "updated_at": now_iso_utc(),
        "threads": items,
    }


def fetch_announcements(limit=20):
    if not DISCORD_ANNOUNCEMENT_CHANNEL_ID:
        raise RuntimeError("DISCORD_ANNOUNCEMENT_CHANNEL_ID is not set")

    max_limit = max(1, min(int(limit or 20), 100))
    data = discord_request_json(
        "/channels/{}/messages?limit={}".format(DISCORD_ANNOUNCEMENT_CHANNEL_ID, max_limit)
    )

    def text_from_embeds(message):
        return discord_message_embed_text(message)

    items = []
    if isinstance(data, list):
        for message in data:
            if not isinstance(message, dict):
                continue
            if int(message.get("type", 0) or 0) != 0:
                continue

            content = (message.get("content", "") or "").strip()
            if content == "":
                content = text_from_embeds(message)
            if content == "":
                continue

            author = ""
            author_data = message.get("author", {}) or {}
            if author_data.get("global_name"):
                author = author_data.get("global_name", "")
            elif author_data.get("username"):
                author = author_data.get("username", "")

            items.append(
                {
                    "id": str(message.get("id", "")),
                    "channel_id": DISCORD_ANNOUNCEMENT_CHANNEL_ID,
                    "guild_id": DISCORD_GUILD_ID,
                    "content": content,
                    "timestamp": message.get("timestamp"),
                    "url": "https://discord.com/channels/{}/{}/{}".format(
                        DISCORD_GUILD_ID,
                        DISCORD_ANNOUNCEMENT_CHANNEL_ID,
                        str(message.get("id", "")),
                    ),
                    "author": {
                        "username": author_data.get("username", "") or "",
                        "global_name": author_data.get("global_name", "") or "",
                        "display_name": author,
                    },
                }
            )

    return {
        "ok": True,
        "channel_id": DISCORD_ANNOUNCEMENT_CHANNEL_ID,
        "count": len(items),
        "updated_at": now_iso_utc(),
        "messages": items,
    }


def discord_message_embed_text(message, mode="full"):
    parts = []
    embeds = message.get("embeds", []) if isinstance(message, dict) else []
    if not isinstance(embeds, list):
        return ""

    for embed in embeds:
        if not isinstance(embed, dict):
            continue

        title = sanitize_text(embed.get("title", ""))
        description = sanitize_text(embed.get("description", ""))
        if str(mode or "full").lower() in ("body", "description", "summary"):
            if description:
                parts.append(description)
            continue
        if title:
            parts.append(title)
        if description:
            parts.append(description)

        fields = embed.get("fields", [])
        if isinstance(fields, list):
            for field in fields:
                if not isinstance(field, dict):
                    continue
                fname = sanitize_text(field.get("name", ""))
                fvalue = sanitize_text(field.get("value", ""))
                if fname and fvalue:
                    parts.append("{}: {}".format(fname, fvalue))
                elif fvalue:
                    parts.append(fvalue)

    return "\n\n".join([p for p in parts if p]).strip()


def _discord_int(value):
    try:
        return int(str(value or "0"), 10)
    except Exception:
        return 0


def _discord_has_flag(value, bitmask):
    return (_discord_int(value) & int(bitmask)) == int(bitmask)


def _discord_channel_type_value(value):
    try:
        enum_value = getattr(value, "value", value)
        return int(enum_value or 0)
    except Exception:
        return 0


def _normalize_instance_role_prefix(prefix):
    normalized = sanitize_text(prefix or DISCORD_INSTANCE_ROLE_PREFIX).lower()
    return normalized or "instance"


def _channel_type_label(channel_type):
    labels = {
        0: "text",
        2: "voice",
        4: "category",
        5: "announcement",
        13: "stage",
        15: "forum",
    }
    return labels.get(int(channel_type or 0), "other")


def _extract_instance_visibility(channel, instance_role_map, everyone_role_id):
    required_role_ids = []
    everyone_denied = False
    overwrites = channel.get("permission_overwrites", []) if isinstance(channel, dict) else []
    if not isinstance(overwrites, list):
        return required_role_ids, everyone_denied

    for overwrite in overwrites:
        if not isinstance(overwrite, dict):
            continue
        overwrite_id = str(overwrite.get("id", "") or "")
        overwrite_type = _discord_int(overwrite.get("type", 0))
        allow = overwrite.get("allow", "0")
        deny = overwrite.get("deny", "0")

        if overwrite_type == 0 and overwrite_id == everyone_role_id and _discord_has_flag(deny, DISCORD_PERMISSION_VIEW_CHANNEL):
            everyone_denied = True

        if overwrite_type != 0 or overwrite_id not in instance_role_map:
            continue
        if _discord_has_flag(deny, DISCORD_PERMISSION_VIEW_CHANNEL):
            continue
        if _discord_has_flag(allow, DISCORD_PERMISSION_VIEW_CHANNEL):
            required_role_ids.append(overwrite_id)

    unique_ids = []
    for role_id in required_role_ids:
        if role_id not in unique_ids:
            unique_ids.append(role_id)
    return unique_ids, everyone_denied


def fetch_instance_space_channels(discord_user_id, role_prefix=""):
    discord_user_id = sanitize_text(discord_user_id)
    if not discord_user_id:
        raise RuntimeError("discord_id is required")
    if not DISCORD_GUILD_ID:
        raise RuntimeError("DISCORD_GUILD_ID is not set")

    normalized_prefix = _normalize_instance_role_prefix(role_prefix)
    roles_data = discord_request_json("/guilds/{}/roles".format(DISCORD_GUILD_ID))
    channels_data = discord_request_json("/guilds/{}/channels".format(DISCORD_GUILD_ID))
    member_data = discord_request_json("/guilds/{}/members/{}".format(DISCORD_GUILD_ID, quote(discord_user_id)))

    if not isinstance(roles_data, list):
        raise RuntimeError("guild roles response is invalid")
    if not isinstance(channels_data, list):
        raise RuntimeError("guild channels response is invalid")
    if not isinstance(member_data, dict):
        raise RuntimeError("guild member response is invalid")

    instance_role_map = {}
    for role in roles_data:
        if not isinstance(role, dict):
            continue
        role_id = str(role.get("id", "") or "")
        role_name = sanitize_text(role.get("name", ""))
        if not role_id or not role_name:
            continue
        if role_name.lower().startswith(normalized_prefix):
            instance_role_map[role_id] = role_name

    member_role_ids = set()
    for role_id in member_data.get("roles", []) if isinstance(member_data.get("roles", []), list) else []:
        role_id = str(role_id or "")
        if role_id:
            member_role_ids.add(role_id)

    owned_roles = []
    for role_id, role_name in instance_role_map.items():
        if role_id in member_role_ids:
            owned_roles.append({"id": role_id, "name": role_name})
    owned_roles.sort(key=lambda item: item["name"].lower())

    categories = {}
    ordered_channels = []
    everyone_role_id = DISCORD_GUILD_ID
    visible_types = {0, 2, 5, 13, 15}

    for channel in channels_data:
        if not isinstance(channel, dict):
            continue
        channel_id = str(channel.get("id", "") or "")
        channel_type = _discord_int(channel.get("type", 0))
        if not channel_id:
            continue

        required_role_ids, everyone_denied = _extract_instance_visibility(channel, instance_role_map, everyone_role_id)
        if channel_type == 4:
            categories[channel_id] = {
                "id": channel_id,
                "name": sanitize_text(channel.get("name", "カテゴリ")) or "カテゴリ",
                "position": _discord_int(channel.get("position", 0)),
                "required_role_ids": required_role_ids,
                "everyone_denied": everyone_denied,
            }
            continue

        if channel_type not in visible_types:
            continue
        ordered_channels.append(channel)

    def _channel_sort_key(channel):
        parent_id = str(channel.get("parent_id", "") or "")
        parent = categories.get(parent_id, {})
        return (
            _discord_int(parent.get("position", 999999)),
            _discord_int(channel.get("position", 999999)),
            sanitize_text(channel.get("name", "")).lower(),
        )

    ordered_channels.sort(key=_channel_sort_key)

    grouped_channels = {}
    group_order = []
    channel_count = 0

    for channel in ordered_channels:
        channel_id = str(channel.get("id", "") or "")
        channel_name = sanitize_text(channel.get("name", ""))
        if not channel_id or not channel_name:
            continue

        direct_role_ids, direct_everyone_denied = _extract_instance_visibility(channel, instance_role_map, everyone_role_id)
        parent_id = str(channel.get("parent_id", "") or "")
        parent = categories.get(parent_id)

        required_role_ids = list(direct_role_ids)
        everyone_denied = direct_everyone_denied
        if not required_role_ids and parent and parent.get("required_role_ids"):
            required_role_ids = list(parent.get("required_role_ids", []))
            everyone_denied = bool(parent.get("everyone_denied"))

        if not required_role_ids or not everyone_denied:
            continue
        if not any(role_id in member_role_ids for role_id in required_role_ids):
            continue

        group_id = parent_id or "ungrouped"
        group_name = parent.get("name", "インスタンスルーム") if parent else "インスタンスルーム"
        if group_id not in grouped_channels:
            grouped_channels[group_id] = []
            group_order.append(group_id)

        grouped_channels[group_id].append(
            {
                "id": channel_id,
                "name": channel_name,
                "type": _channel_type_label(channel.get("type", 0)),
                "required_roles": [instance_role_map[role_id] for role_id in required_role_ids if role_id in instance_role_map],
                "url": "https://discord.com/channels/{}/{}".format(DISCORD_GUILD_ID, channel_id),
            }
        )
        channel_count += 1

    groups = []
    for group_id in group_order:
        channels = grouped_channels.get(group_id, [])
        if not channels:
            continue
        group_name = categories.get(group_id, {}).get("name", "インスタンスルーム") if group_id != "ungrouped" else "インスタンスルーム"
        groups.append(
            {
                "id": group_id,
                "name": group_name,
                "channels": channels,
            }
        )

    return {
        "ok": True,
        "guild_id": DISCORD_GUILD_ID,
        "discord_user_id": discord_user_id,
        "role_prefix": normalized_prefix,
        "owned_roles": owned_roles,
        "group_count": len(groups),
        "channel_count": channel_count,
        "groups": groups,
        "updated_at": now_iso_utc(),
    }


def wordpress_bridge_post_event(event_payload, timeout=10):
    if not WP_BRIDGE_ENDPOINT:
        raise RuntimeError("WP_BRIDGE_ENDPOINT is not set")
    if not WP_BRIDGE_BEARER_TOKEN:
        raise RuntimeError("WP_BRIDGE_BEARER_TOKEN is not set")
    if not WP_BRIDGE_HMAC_SECRET:
        raise RuntimeError("WP_BRIDGE_HMAC_SECRET is not set")

    body_text = json.dumps(event_payload, ensure_ascii=False, separators=(",", ":"))
    body_bytes = body_text.encode("utf-8")
    timestamp = str(int(time.time()))

    digest = hmac.new(
        WP_BRIDGE_HMAC_SECRET.encode("utf-8"),
        (timestamp + body_text).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    req = Request(WP_BRIDGE_ENDPOINT, data=body_bytes, method="POST")
    bearer_value = "Bearer {}".format(WP_BRIDGE_BEARER_TOKEN)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", bearer_value)
    # Authorization が中継で落ちる環境向けに独自ヘッダーでも同値を渡す。
    req.add_header("X-Sevendtd-Bearer", WP_BRIDGE_BEARER_TOKEN)
    if WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER:
        req.add_header("X-Authorization", bearer_value)
        req.add_header("X-Auth-Token", WP_BRIDGE_BEARER_TOKEN)
    req.add_header("X-Timestamp", timestamp)
    req.add_header("X-Signature", "sha256={}".format(digest))
    req.add_header("User-Agent", "DiscordBotBridge/1.0")

    sent_headers = ["Authorization", "X-Sevendtd-Bearer", "X-Timestamp", "X-Signature", "User-Agent"]
    if WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER:
        sent_headers.extend(["X-Authorization", "X-Auth-Token"])
    bridge_debug(
        "POST {} headers={} token_fp={} body_bytes={}".format(
            WP_BRIDGE_ENDPOINT,
            ",".join(sent_headers),
            token_fingerprint(WP_BRIDGE_BEARER_TOKEN),
            len(body_bytes),
        )
    )

    with urlopen(req, timeout=timeout) as resp:
        status = resp.getcode()
        raw = resp.read().decode("utf-8")
        data = {}
        if raw.strip() != "":
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
        return status, data


def get_wordpress_profile_base_url():
    for candidate in (
        WP_BRIDGE_ENDPOINT,
        WP_NEXUS_WATCH_ENDPOINT,
        WP_YOUTUBE_WATCH_ENDPOINT,
        WP_TWITTER_WATCH_ENDPOINT,
        WP_COMMENTS_WATCH_ENDPOINT,
    ):
        raw = sanitize_text(candidate)
        if not raw:
            continue
        parsed = urlsplit(raw)
        if parsed.scheme and parsed.netloc:
            return "{}://{}".format(parsed.scheme, parsed.netloc)
    return "https://7daystodie.jp"


def build_wordpress_profile_api_url(path, query=None):
    normalized_path = "/{}".format(sanitize_text(path).lstrip("/"))
    url = "{}/wp-json/sevendtd/v1{}".format(get_wordpress_profile_base_url().rstrip("/"), normalized_path)
    if isinstance(query, dict) and query:
        query_values = {}
        for key, value in query.items():
            if value is None:
                continue
            text = sanitize_text(value)
            if not text:
                continue
            query_values[str(key)] = text
        if query_values:
            url = "{}?{}".format(url, urlencode(query_values))
    return url


def wordpress_profile_api_request(path, method="GET", payload=None, timeout=None):
    if not BOT_API_SHARED_KEY:
        raise RuntimeError("BOT_API_SHARED_KEY is not set")

    resolved_method = sanitize_text(method or "GET").upper() or "GET"
    resolved_timeout = timeout if timeout is not None else WP_BRIDGE_TIMEOUT
    request_payload = payload if isinstance(payload, dict) else {}
    url = build_wordpress_profile_api_url(path, query=(request_payload if resolved_method == "GET" else None))
    body_bytes = None
    if resolved_method != "GET" and request_payload:
        body_bytes = json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    req = Request(url, data=body_bytes, method=resolved_method)
    req.add_header("X-Api-Key", BOT_API_SHARED_KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "DiscordProfileBot/1.0")

    try:
        with urlopen(req, timeout=resolved_timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw.strip() else {}
    except HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8")
        except Exception:
            raw = ""
        message = ""
        if raw.strip():
            try:
                error_data = json.loads(raw)
                if isinstance(error_data, dict):
                    message = sanitize_text(error_data.get("error") or error_data.get("message") or error_data.get("code"))
            except Exception:
                message = sanitize_text(raw)
        raise RuntimeError("WordPress API HTTP {} {}".format(exc.code, message or sanitize_text(raw) or "request failed"))
    except URLError as exc:
        raise RuntimeError("WordPress API URLError {}".format(exc))

    if not isinstance(data, dict):
        raise RuntimeError("WordPress API returned invalid response")
    return data


def fetch_wordpress_profile_member_status(discord_user_id):
    resolved_user_id = normalize_discord_user_id(discord_user_id)
    if not resolved_user_id:
        raise ValueError("discord_user_id is required")
    data = wordpress_profile_api_request(
        "/profile/member-status",
        method="GET",
        payload={"discord_id": resolved_user_id},
        timeout=3,
    )
    if not bool(data.get("ok", False)):
        raise RuntimeError(sanitize_text(data.get("error") or "profile member status failed"))
    return data


def update_wordpress_profile_from_discord(discord_user_id, section, payload=None):
    resolved_user_id = normalize_discord_user_id(discord_user_id)
    resolved_section = sanitize_text(section).lower()
    if not resolved_user_id:
        raise ValueError("discord_user_id is required")
    if not resolved_section:
        raise ValueError("section is required")

    body = {
        "discord_id": resolved_user_id,
        "section": resolved_section,
    }
    if isinstance(payload, dict):
        body.update(payload)

    data = wordpress_profile_api_request(
        "/profile/discord-edit",
        method="POST",
        payload=body,
        timeout=max(10, WP_BRIDGE_TIMEOUT),
    )
    if not bool(data.get("ok", False)):
        raise RuntimeError(sanitize_text(data.get("error") or "profile update failed"))
    return data


def push_announcements_to_wordpress(limit=20, max_retries=3):
    source = fetch_announcements(limit=limit)
    messages = source.get("messages", []) if isinstance(source, dict) else []

    sent = 0
    duplicated = 0
    failed = []

    # 先に古いメッセージを送ることで、Web 側の時系列を崩しにくくする。
    for message in reversed(messages):
        message_id = str(message.get("id", "") or "").strip()
        if message_id == "":
            continue

        payload = {
            "event_type": "announcement.created",
            "guild_id": str(message.get("guild_id", "") or DISCORD_GUILD_ID),
            "channel_id": str(message.get("channel_id", "") or DISCORD_ANNOUNCEMENT_CHANNEL_ID),
            "message_id": message_id,
            "author": str((message.get("author", {}) or {}).get("display_name", "") or ""),
            "content": str(message.get("content", "") or ""),
            "posted_at": message.get("timestamp"),
            "url": str(message.get("url", "") or ""),
        }

        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                status, data = wordpress_bridge_post_event(payload, timeout=WP_BRIDGE_TIMEOUT)
                if status == 200:
                    sent += 1
                    last_error = ""
                    break
                if status == 202:
                    duplicated += 1
                    last_error = ""
                    break
                if status == 429 or status >= 500:
                    last_error = "status {}".format(status)
                    if attempt < max_retries:
                        time.sleep(2 ** (attempt - 1))
                        continue
                last_error = "status {} response {}".format(status, data)
                break
            except HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    body = ""
                bridge_debug("HTTPError code={} body={}".format(exc.code, body))
                if exc.code == 429 or exc.code >= 500:
                    last_error = "HTTPError {} {}".format(exc.code, body)
                    if attempt < max_retries:
                        time.sleep(2 ** (attempt - 1))
                        continue
                last_error = "HTTPError {} {}".format(exc.code, body)
                break
            except URLError as exc:
                bridge_debug("URLError {}".format(exc))
                last_error = "URLError {}".format(exc)
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                break
            except Exception as exc:
                bridge_debug("Exception {}".format(exc))
                last_error = "Exception {}".format(exc)
                break

        if last_error:
            failed.append({"message_id": message_id, "error": last_error})

    return {
        "ok": len(failed) == 0,
        "total": len(messages),
        "sent": sent,
        "duplicated": duplicated,
        "failed": failed,
        "updated_at": now_iso_utc(),
    }


def refresh_snapshot():
    global snapshot
    try:
        latest = fetch_active_threads()
    except Exception as exc:
        latest = {
            "ok": False,
            "channel_id": DISCORD_THREAD_CHANNEL_ID,
            "count": 0,
            "updated_at": now_iso_utc(),
            "threads": [],
            "error": str(exc),
        }

    with snapshot_lock:
        snapshot = latest


def poller_loop():
    last_nexus_poll = 0
    last_social_poll = 0
    last_comments_poll = 0
    last_twitch_poll = 0
    last_twitter_poll = 0
    last_youtube_poll = 0
    last_youtube_comments_poll = 0
    last_youtube_livechat_poll = 0
    last_page_promo_poll = 0
    while True:
        refresh_snapshot()
        now = time.time()
        if now - last_nexus_poll >= NEXUS_NOTIFY_POLL_SECONDS:
            has_nexus_wordpress = bool(WP_NEXUS_WATCH_ENDPOINT and WP_NEXUS_WATCH_TOKEN)
            has_nexus_posts_fallback = bool(WP_NEXUS_FALLBACK_ENABLED and WP_NEXUS_FALLBACK_POSTS_ENDPOINT)
            if DISCORD_NEXUS_NOTIFY_CHANNEL_ID and (has_nexus_wordpress or has_nexus_posts_fallback):
                try:
                    sync_nexus_watch_notifications(limit=20)
                except Exception as exc:
                    with nexus_notify_lock:
                        nexus_notify_state["last_run"] = now_iso_utc()
                        nexus_notify_state["last_error"] = str(exc)
                    save_nexus_notify_state()
            last_nexus_poll = now

        if now - last_social_poll >= SOCIAL_NOTIFY_POLL_SECONDS:
            if WP_SOCIAL_WATCH_ENDPOINT and WP_SOCIAL_WATCH_TOKEN and DISCORD_SOCIAL_NOTIFY_CHANNEL_ID:
                try:
                    sync_social_watch_notifications(limit=20)
                except Exception as exc:
                    with social_notify_lock:
                        social_notify_state["last_run"] = now_iso_utc()
                        social_notify_state["last_error"] = str(exc)
                    save_social_notify_state(SOCIAL_NOTIFY_STATE_FILE, social_notify_lock, social_notify_state)
            last_social_poll = now

        if COMMENTS_NOTIFY_ENABLED and now - last_comments_poll >= COMMENTS_NOTIFY_POLL_SECONDS:
            if WP_COMMENTS_WATCH_ENDPOINT and DISCORD_COMMENTS_NOTIFY_CHANNEL_ID:
                try:
                    sync_comment_notifications(limit=20)
                except Exception as exc:
                    with comments_notify_lock:
                        comments_notify_state["last_run"] = now_iso_utc()
                        comments_notify_state["last_error"] = str(exc)
                    save_social_notify_state(COMMENTS_NOTIFY_STATE_FILE, comments_notify_lock, comments_notify_state)
            last_comments_poll = now

        if TWITCH_NOTIFY_ENABLED and now - last_twitch_poll >= TWITCH_NOTIFY_POLL_SECONDS:
            try:
                sync_twitch_notifications()
            except Exception as exc:
                with twitch_notify_lock:
                    twitch_notify_state["last_run"] = now_iso_utc()
                    twitch_notify_state["last_error"] = str(exc)
                save_social_notify_state(TWITCH_NOTIFY_STATE_FILE, twitch_notify_lock, twitch_notify_state)
            last_twitch_poll = now

        if TWITTER_NOTIFY_ENABLED and now - last_twitter_poll >= get_effective_twitter_poll_seconds():
            try:
                sync_twitter_notifications()
            except Exception as exc:
                with twitter_notify_lock:
                    twitter_notify_state["last_run"] = now_iso_utc()
                    twitter_notify_state["last_error"] = str(exc)
                save_social_notify_state(TWITTER_NOTIFY_STATE_FILE, twitter_notify_lock, twitter_notify_state)
            last_twitter_poll = now

        if YOUTUBE_NOTIFY_ENABLED and now - last_youtube_poll >= YOUTUBE_NOTIFY_POLL_SECONDS:
            try:
                sync_youtube_notifications(wordpress_force_refresh=False, allow_direct_fallback=False)
            except Exception as exc:
                with youtube_notify_lock:
                    youtube_notify_state["last_run"] = now_iso_utc()
                    youtube_notify_state["last_error"] = str(exc)
                save_social_notify_state(YOUTUBE_NOTIFY_STATE_FILE, youtube_notify_lock, youtube_notify_state)
            last_youtube_poll = now

        if YOUTUBE_COMMENTS_NOTIFY_ENABLED and now - last_youtube_comments_poll >= YOUTUBE_COMMENTS_NOTIFY_POLL_SECONDS:
            try:
                sync_youtube_comment_notifications(limit=YOUTUBE_COMMENTS_FETCH_LIMIT)
            except Exception as exc:
                with youtube_comments_notify_lock:
                    youtube_comments_notify_state["last_run"] = now_iso_utc()
                    youtube_comments_notify_state["last_error"] = str(exc)
                    youtube_comments_notify_state["last_source"] = "direct"
                save_social_notify_state(YOUTUBE_COMMENTS_NOTIFY_STATE_FILE, youtube_comments_notify_lock, youtube_comments_notify_state)
            last_youtube_comments_poll = now

        if YOUTUBE_LIVECHAT_NOTIFY_ENABLED and now - last_youtube_livechat_poll >= YOUTUBE_LIVECHAT_POLL_SECONDS:
            try:
                sync_youtube_livechat_notifications(limit=YOUTUBE_LIVECHAT_FETCH_LIMIT)
            except Exception as exc:
                with youtube_livechat_notify_lock:
                    youtube_livechat_notify_state["last_run"] = now_iso_utc()
                    youtube_livechat_notify_state["last_error"] = str(exc)
                    youtube_livechat_notify_state["last_source"] = "direct"
                save_social_notify_state(YOUTUBE_LIVECHAT_STATE_FILE, youtube_livechat_notify_lock, youtube_livechat_notify_state)
            last_youtube_livechat_poll = now

        if WP_PAGE_PROMO_ENABLED and now - last_page_promo_poll >= PAGE_PROMO_POLL_SECONDS:
            try:
                sync_wordpress_page_promotions(limit=PAGE_PROMO_MAX_ITEMS_PER_SYNC)
            except Exception as exc:
                with page_promo_lock:
                    page_promo_state["last_run"] = now_iso_utc()
                    page_promo_state["last_error"] = str(exc)
                save_social_notify_state(PAGE_PROMO_STATE_FILE, page_promo_lock, page_promo_state)
            last_page_promo_poll = now
        time.sleep(60)


def set_gateway_state(**kwargs):
    with gateway_lock:
        gateway_state.update(kwargs)


def is_discord_admin_interaction(interaction):
    member = getattr(interaction, "user", None)
    permissions = getattr(member, "guild_permissions", None)
    if permissions is None:
        return False
    try:
        return bool(permissions.administrator)
    except Exception:
        return False


def format_profile_notify_channel_reference(channel_id="", channel_name=""):
    resolved_channel_id = sanitize_text(channel_id)
    resolved_channel_name = truncate_text(sanitize_text(channel_name), 100)
    if resolved_channel_id.isdigit():
        return "<#{}>".format(resolved_channel_id)
    return resolved_channel_name or "未設定 / Not set"


def build_profile_notify_status_embed(state=None):
    resolved_state = state if isinstance(state, dict) else get_profile_notify_state_snapshot()
    voice_channel_id = sanitize_text(resolved_state.get("voice_channel_id", ""))
    voice_channel_name = sanitize_text(resolved_state.get("voice_channel_name", ""))
    post_channel_id = sanitize_text(resolved_state.get("post_channel_id", ""))
    post_channel_name = sanitize_text(resolved_state.get("post_channel_name", ""))
    configured = bool(resolved_state.get("enabled", False)) and voice_channel_id.isdigit() and post_channel_id.isdigit()

    embed = discord.Embed(
        title="Profile VC Notify",
        description="指定 VC へ入室したメンバーの中央プロフィールを Embed で投稿します。",
        color=0x3BA55C if configured else 0x5865F2,
    )
    embed.add_field(
        name="状態 / Status",
        value="有効 / Enabled" if configured else "未設定 / Not configured",
        inline=False,
    )
    embed.add_field(
        name="監視VC / Source Voice",
        value=format_profile_notify_channel_reference(voice_channel_id, voice_channel_name),
        inline=True,
    )
    embed.add_field(
        name="投稿先 / Post Channel",
        value=format_profile_notify_channel_reference(post_channel_id, post_channel_name),
        inline=True,
    )

    last_lines = []
    last_run = sanitize_text(resolved_state.get("last_run", ""))
    if last_run:
        last_lines.append("時刻: {}".format(last_run))
    last_user_id = normalize_discord_user_id(resolved_state.get("last_notified_user_id", ""))
    if last_user_id:
        last_lines.append("ユーザー: <@{}>".format(last_user_id))
    last_voice_text = format_profile_notify_channel_reference(
        resolved_state.get("last_voice_channel_id", ""),
        resolved_state.get("last_voice_channel_name", ""),
    )
    if last_voice_text != "未設定 / Not set":
        last_lines.append("VC: {}".format(last_voice_text))
    last_message_id = sanitize_text(resolved_state.get("last_notified_message_id", ""))
    if last_message_id:
        last_lines.append("message_id: {}".format(last_message_id))
    embed.add_field(
        name="最終送信 / Last Delivery",
        value="\n".join(last_lines) if last_lines else "まだ送信していません。",
        inline=False,
    )

    last_error = truncate_text(sanitize_text(resolved_state.get("last_error", "")), 1000)
    if last_error:
        embed.add_field(name="最終エラー / Last Error", value=last_error, inline=False)

    embed.set_footer(text="/notify mode:profile operation:set で更新")
    return embed


async def post_profile_notify_message(discord_user_id, post_channel_id, voice_channel_id="", voice_channel_name=""):
    resolved_user_id = normalize_discord_user_id(discord_user_id)
    resolved_post_channel_id = sanitize_text(post_channel_id)
    resolved_voice_channel_id = sanitize_text(voice_channel_id)
    resolved_voice_channel_name = truncate_text(sanitize_text(voice_channel_name), 100)
    if not resolved_user_id:
        raise ValueError("discord_user_id is required")
    if not resolved_post_channel_id.isdigit():
        raise ValueError("post channel is not configured")

    try:
        payload = await asyncio.to_thread(fetch_wordpress_profile_member_status, resolved_user_id)
        if not bool(payload.get("user_exists", False)):
            raise RuntimeError("WordPress 側の連携プロフィールが見つかりません。")
        message_payload = build_profile_card_voice_notify_message_payload(
            payload,
            voice_channel_id=resolved_voice_channel_id,
            voice_channel_name=resolved_voice_channel_name,
        )
        result = await asyncio.to_thread(
            discord_post_json,
            "/channels/{}/messages".format(resolved_post_channel_id),
            message_payload,
        )
        record_profile_notify_result(
            discord_user_id=resolved_user_id,
            message_id=sanitize_text(result.get("id", "")),
            voice_channel_id=resolved_voice_channel_id,
            voice_channel_name=resolved_voice_channel_name,
        )
        return {
            "profile": payload,
            "message": result,
            "message_payload": message_payload,
        }
    except Exception as exc:
        record_profile_notify_result(
            error_message=str(exc),
            discord_user_id=resolved_user_id,
            voice_channel_id=resolved_voice_channel_id,
            voice_channel_name=resolved_voice_channel_name,
        )
        raise


def build_twitch_chat_status_embed(state, authorize_url=""):
    auth_source = sanitize_text(state.get("auth_source", "")) or ("env" if TWITCH_CHAT_USER_ACCESS_TOKEN else "file")
    source_label = {
        "env": "環境変数 / Environment",
        "file": "OAuth 保存 / OAuth cache",
    }.get(auth_source, auth_source or "未設定 / Unset")

    if not TWITCH_CHAT_ENABLED:
        status_text = "無効 / Disabled"
        color = discord.Color.red()
    elif state.get("connected"):
        status_text = "接続中 / Connected"
        color = discord.Color.green()
    elif state.get("awaiting_authorization"):
        status_text = "認可待ち / Waiting for OAuth"
        color = discord.Color.orange()
    else:
        status_text = "待機中 / Standby"
        color = discord.Color.blurple()

    active_relay_channel_id = sanitize_text(state.get("relay_channel_id", "")) or TWITCH_CHAT_DISCORD_CHANNEL_ID
    embed = discord.Embed(
        title="Twitch Chat Relay",
        description="Twitch chat を Discord に片方向転送する状態を表示します。",
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="状態 / Status", value=status_text, inline=True)
    embed.add_field(
        name="Discord 転送先 / Relay Channel",
        value="<#{}>".format(active_relay_channel_id) if active_relay_channel_id else "未設定 / Unset",
        inline=True,
    )
    route_mode = "固定 channel"
    if TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS and DISCORD_TWITCH_MEDIA_CHANNEL_ID:
        route_mode = "Twitch creator threads (<#{}>)".format(DISCORD_TWITCH_MEDIA_CHANNEL_ID)
    embed.add_field(name="配送方式 / Route", value=truncate_text(route_mode, 1024), inline=True)
    broadcaster = sanitize_text(state.get("broadcaster_login", ""))
    if broadcaster:
        broadcaster_value = "{}\nhttps://www.twitch.tv/{}".format(broadcaster, broadcaster)
    else:
        broadcaster_value = sanitize_text(TWITCH_CHAT_BROADCASTER_LOGIN) or "OAuth 認可後に自動確定 / auto after OAuth"
    embed.add_field(name="Twitch 配信元 / Broadcaster", value=truncate_text(broadcaster_value, 1024), inline=False)
    subscription_broadcasters = [sanitize_text(item) for item in state.get("subscription_broadcasters", []) if sanitize_text(item)]
    if subscription_broadcasters:
        embed.add_field(
            name="受信対象 / Subscriptions",
            value=truncate_text(", ".join(subscription_broadcasters), 1024),
            inline=False,
        )
    embed.add_field(name="認証ソース / Auth Source", value=source_label, inline=True)
    scope_text = ", ".join([sanitize_text(item) for item in state.get("token_scopes", []) if sanitize_text(item)])
    embed.add_field(
        name="Scope",
        value=truncate_text(scope_text or "user:read:chat, user:write:chat を要求", 1024),
        inline=True,
    )
    owner_discord_user_id = normalize_discord_user_id(state.get("owner_discord_user_id", ""))
    owner_twitch_login = sanitize_text(state.get("owner_twitch_login", ""))
    owner_text = []
    if owner_discord_user_id:
        owner_text.append("Discord: <@{}>".format(owner_discord_user_id))
    if owner_twitch_login:
        owner_text.append("Twitch: {}".format(owner_twitch_login))
    if owner_text:
        embed.add_field(name="固定 owner / Bound Owner", value=truncate_text("\n".join(owner_text), 1024), inline=False)
    retention = "{} 秒で自動削除 / auto delete after {}s".format(
        TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS,
        TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS,
    )
    if TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS <= 0:
        retention = "自動削除なし / no auto delete"
    embed.add_field(name="保持方針 / Retention", value=retention, inline=False)

    tracked_message_count = safe_int(state.get("tracked_message_count", 0))
    total_deleted_count = safe_int(state.get("total_deleted_count", 0))
    last_delete_reason = sanitize_text(state.get("last_delete_reason", ""))
    last_delete_target = sanitize_text(state.get("last_delete_target", ""))
    last_delete_count = safe_int(state.get("last_delete_count", 0))
    last_delete_sync_at = sanitize_text(state.get("last_delete_sync_at", ""))
    moderation_lines = [
        "追跡中 / Tracked: {}".format(tracked_message_count),
        "同期削除累計 / Deleted: {}".format(total_deleted_count),
    ]
    if last_delete_reason:
        detail = "{} / {}".format(last_delete_reason, last_delete_count)
        if last_delete_target:
            detail = "{}\nTarget: {}".format(detail, truncate_text(last_delete_target, 200))
        if last_delete_sync_at:
            detail = "{}\nAt: {}".format(detail, last_delete_sync_at)
        moderation_lines.append("直近 / Last: {}".format(detail))
    embed.add_field(
        name="削除追従 / Moderation Sync",
        value=truncate_text("\n".join(moderation_lines), 1024),
        inline=False,
    )

    last_preview = sanitize_text(state.get("last_message_preview", ""))
    if last_preview:
        embed.add_field(name="直近転送 / Last Relayed", value=truncate_text(last_preview, 1024), inline=False)

    last_error = sanitize_text(state.get("last_error", ""))
    if last_error:
        embed.add_field(name="Last Error", value=truncate_text(last_error, 1024), inline=False)

    if authorize_url:
        embed.add_field(name="OAuth URL", value=truncate_text(authorize_url, 1024), inline=False)

    embed.set_footer(text="EventSub + Helix API / Twitch ソース URL を各転送へ付与")
    return embed


def build_twitch_chat_status_detail_embed(state, authorize_url=""):
    embed = build_twitch_chat_status_embed(state, authorize_url=authorize_url)
    embed.title = "Twitch Chat Relay Detail"

    sender_login = sanitize_text(state.get("sender_login", ""))
    sender_user_id = sanitize_text(state.get("sender_user_id", ""))
    broadcaster_login = sanitize_text(state.get("broadcaster_login", ""))
    broadcaster_user_id = sanitize_text(state.get("broadcaster_user_id", ""))
    sender_lines = []
    if sender_login or sender_user_id:
        sender_lines.append("Sender: {} ({})".format(sender_login or "-", sender_user_id or "-"))
    if broadcaster_login or broadcaster_user_id:
        sender_lines.append("Broadcaster: {} ({})".format(broadcaster_login or "-", broadcaster_user_id or "-"))
    if sender_lines:
        embed.add_field(name="送信主体 / Identity", value=truncate_text("\n".join(sender_lines), 1024), inline=False)

    session_lines = []
    if sanitize_text(state.get("session_id", "")):
        session_lines.append("Session: {}".format(sanitize_text(state.get("session_id", ""))))
    if sanitize_text(state.get("last_event_type", "")):
        session_lines.append("Last Event: {}".format(sanitize_text(state.get("last_event_type", ""))))
    if sanitize_text(state.get("last_event_at", "")):
        session_lines.append("Last Event At: {}".format(sanitize_text(state.get("last_event_at", ""))))
    if sanitize_text(state.get("last_relayed_at", "")):
        session_lines.append("Last Relayed At: {}".format(sanitize_text(state.get("last_relayed_at", ""))))
    if session_lines:
        embed.add_field(name="接続詳細 / Session", value=truncate_text("\n".join(session_lines), 1024), inline=False)

    subscribed_types = [sanitize_text(item) for item in state.get("subscribed_types", []) if sanitize_text(item)]
    if subscribed_types:
        embed.add_field(name="購読 / Subscriptions", value=truncate_text("\n".join(subscribed_types), 1024), inline=False)

    runtime_lines = [
        "Enabled: {}".format(bool(state.get("enabled"))),
        "Running: {}".format(bool(state.get("running"))),
        "Connected: {}".format(bool(state.get("connected"))),
        "Awaiting OAuth: {}".format(bool(state.get("awaiting_authorization"))),
        "Route To Creator Threads: {}".format(bool(TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS and DISCORD_TWITCH_MEDIA_CHANNEL_ID)),
        "Allowed Games: {}".format(TWITCH_CHAT_ALLOWED_GAME_NAMES or "all"),
        "Subscription Logins: {}".format(TWITCH_CHAT_BROADCASTER_LOGINS or "owner only"),
        "Auth State File: {}".format(TWITCH_CHAT_AUTH_STATE_FILE),
    ]
    embed.add_field(name="Runtime", value=truncate_text("\n".join(runtime_lines), 1024), inline=False)
    return embed


def build_twitch_action_list_embed(catalog, filtered_actions, selected_category="", page=1, page_size=12, sender_context=None):
    category_name = sanitize_text(selected_category)
    category_label = "全カテゴリ / All"
    if category_name:
        for item in catalog.get("categories", []):
            if sanitize_text(item.get("name", "")) == category_name:
                category_label = sanitize_text(item.get("label", "")) or category_name
                break

    context = sender_context if isinstance(sender_context, dict) else get_twitch_action_sender_context()
    pagination = get_twitch_action_page_slice(filtered_actions, page=page, page_size=page_size)
    page_items = pagination.get("items", [])
    status_counts = {"executable": 0, "pending": 0, "unsupported": 0}
    validation_by_name = {}
    for item in filtered_actions:
        validation = evaluate_twitch_action_execution(item, sender_context=context)
        validation_by_name[sanitize_text(item.get("name", ""))] = validation
        status_counts[validation.get("status", "unsupported")] = status_counts.get(validation.get("status", "unsupported"), 0) + 1

    preview_lines = []
    for item in page_items:
        validation = validation_by_name.get(sanitize_text(item.get("name", "")), evaluate_twitch_action_execution(item, sender_context=context))
        flags = []
        flags.append(validation.get("status_short", "不明"))
        if item.get("default_cost", 0) > 0:
            flags.append("Cost {}".format(item.get("default_cost", 0)))
        if item.get("start_gamestage", 0) > 0:
            flags.append("GS {}+".format(item.get("start_gamestage", 0)))
        if not item.get("chat_compatible"):
            flags.append("Bits only")
        suffix = " | {}".format(" / ".join(flags)) if flags else ""
        preview_lines.append("{} | {}{}".format(item.get("title", item.get("name", "action")), item.get("command", "-"), suffix))

    if not preview_lines:
        preview_lines = ["一致する action はありません。 / No matching actions."]

    category_summary_lines = []
    for item in catalog.get("categories", []):
        count = int(item.get("visible_count", 0) or 0)
        if count <= 0:
            continue
        category_summary_lines.append("{}: {}".format(sanitize_text(item.get("label", "")) or item.get("name", "Other"), count))
        if len(category_summary_lines) >= 8:
            break

    embed = discord.Embed(
        title="Twitch v2.6 コマンド一覧",
        description=truncate_text("\n".join(preview_lines), 4000),
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="カテゴリ / Category", value=category_label, inline=True)
    embed.add_field(name="表示件数 / Visible", value=str(len(filtered_actions)), inline=True)
    embed.add_field(name="ページ / Page", value="{}/{}".format(pagination.get("page", 1), pagination.get("total_pages", 1)), inline=True)
    embed.add_field(
        name="Chat 実行可 / Chat Compatible",
        value=str(len([item for item in filtered_actions if item.get("chat_compatible")])),
        inline=True,
    )
    embed.add_field(
        name="判定 / Validation",
        value="実行可能: {}\n条件待ち: {}\n非対応: {}".format(
            status_counts.get("executable", 0),
            status_counts.get("pending", 0),
            status_counts.get("unsupported", 0),
        ),
        inline=True,
    )
    if category_summary_lines:
        embed.add_field(name="カテゴリ内訳 / Category Summary", value=truncate_text("\n".join(category_summary_lines), 1024), inline=False)
    embed.add_field(
        name="使い方 / Usage",
        value="select UI または action 指定で詳細表示、execute=true または詳細画面の実行ボタンで管理者のみ Twitch chat へ送信します。",
        inline=False,
    )
    embed.set_footer(
        text="{} 件中 {}-{} 件を表示。action オートコンプリートでも絞り込めます。".format(
            pagination.get("total_items", 0),
            pagination.get("start_index", 0) + 1 if pagination.get("total_items", 0) else 0,
            pagination.get("end_index", 0),
        )
    )
    return embed


def build_twitch_action_detail_embed(item, validation=None):
    action_validation = validation if isinstance(validation, dict) else evaluate_twitch_action_execution(item)
    status = action_validation.get("status", "unsupported")
    color = {
        "executable": discord.Color.green(),
        "pending": discord.Color.orange(),
        "unsupported": discord.Color.red(),
    }.get(status, discord.Color.blurple())
    embed = discord.Embed(
        title=sanitize_text(item.get("title", "action")) or "action",
        description=truncate_text(sanitize_text(item.get("description", "")) or "説明はありません。", 4000),
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Action 名 / Name", value=sanitize_text(item.get("name", "")) or "-", inline=False)
    embed.add_field(name="判定 / Validation", value=action_validation.get("status_label", "不明"), inline=True)
    embed.add_field(name="コマンド / Command", value=sanitize_text(item.get("command", "")) or "-", inline=True)
    localized_command = sanitize_text(item.get("command_display", ""))
    if localized_command and localized_command != sanitize_text(item.get("command", "")):
        embed.add_field(name="表示コマンド / Localized", value=localized_command, inline=True)
    embed.add_field(name="カテゴリ / Category", value=sanitize_text(item.get("category_label", "")) or "Other", inline=True)
    embed.add_field(name="ポイント種別 / Point", value=sanitize_text(item.get("point_type", "PP")) or "PP", inline=True)
    embed.add_field(name="コスト / Cost", value=str(int(item.get("default_cost", 0) or 0)), inline=True)
    embed.add_field(name="権限 / Permission", value=sanitize_text(action_validation.get("permission", item.get("permission", "Everyone"))) or "Everyone", inline=True)
    embed.add_field(name="開始 GS / Start GS", value=str(int(item.get("start_gamestage", 0) or 0)), inline=True)
    embed.add_field(
        name="Chat 実行可 / Chat Compatible",
        value="Yes" if item.get("chat_compatible") else "No (Bits / Extension only)",
        inline=True,
    )
    presets = item.get("presets", []) if isinstance(item.get("presets"), list) else []
    if presets:
        embed.add_field(name="Preset", value=truncate_text(", ".join([sanitize_text(entry) for entry in presets if sanitize_text(entry)]), 1024), inline=False)
    requirements = item.get("special_requirements", []) if isinstance(item.get("special_requirements"), list) else []
    if requirements:
        embed.add_field(name="条件 / Requirements", value=truncate_text(", ".join([get_twitch_action_special_requirement_label(entry) or sanitize_text(entry) for entry in requirements if sanitize_text(entry)]), 1024), inline=False)
    if action_validation.get("pending_reasons"):
        embed.add_field(
            name="ゲーム側条件待ち / Waiting",
            value=truncate_text("\n".join([sanitize_text(entry) for entry in action_validation.get("pending_reasons", []) if sanitize_text(entry)]), 1024),
            inline=False,
        )
    if action_validation.get("unsupported_reasons"):
        embed.add_field(
            name="非対応理由 / Unsupported",
            value=truncate_text("\n".join([sanitize_text(entry) for entry in action_validation.get("unsupported_reasons", []) if sanitize_text(entry)]), 1024),
            inline=False,
        )
    return embed


def build_twitch_action_execution_embed(item, result):
    embed = discord.Embed(
        title="Twitch action 実行結果",
        description="Discord から Twitch chat へ action command を送信しました。",
        color=discord.Color.green(),
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Action", value=sanitize_text(item.get("title", item.get("name", "action"))) or "action", inline=True)
    embed.add_field(name="Command", value=sanitize_text(result.get("message", item.get("command", ""))) or "-", inline=True)
    embed.add_field(name="Sender", value=sanitize_text(result.get("sender_login", "")) or "-", inline=True)
    broadcaster_login = sanitize_text(result.get("broadcaster_login", ""))
    if broadcaster_login:
        embed.add_field(name="Twitch", value="https://www.twitch.tv/{}".format(broadcaster_login), inline=False)
    return embed


def get_gateway_command_guild():
    if discord is None:
        return None
    if DISCORD_GUILD_ID and DISCORD_GUILD_ID.isdigit():
        return discord.Object(id=int(DISCORD_GUILD_ID))
    return None


async def sync_gateway_commands(command_tree):
    guild = get_gateway_command_guild()
    if guild is not None:
        # 以前の bot で残った global slash command を起動時に明示削除する
        command_tree.clear_commands(guild=None)
        await command_tree.sync()
        synced = await command_tree.sync(guild=guild)
        return synced, "guild"
    synced = await command_tree.sync()
    return synced, "global"


def register_gateway_commands(command_tree):
    if discord is None:
        return

    app_commands = discord.app_commands
    command_guild = get_gateway_command_guild()
    command_scope_kwargs = {"guild": command_guild} if command_guild is not None else {}

    async def twitch_category_autocomplete(interaction, current):
        catalog = get_twitch_action_catalog()
        if not catalog.get("ok"):
            return []
        needle = sanitize_text(current).lower()
        choices = []
        for item in catalog.get("categories", []):
            count = int(item.get("visible_count", 0) or 0)
            if count <= 0:
                continue
            label = sanitize_text(item.get("label", "")) or sanitize_text(item.get("name", "Other"))
            display = "{} ({})".format(label, sanitize_text(item.get("name", "Other"))) if label != sanitize_text(item.get("name", "Other")) else label
            if needle and needle not in display.lower():
                continue
            choices.append(app_commands.Choice(name=truncate_text(display, 100), value=sanitize_text(item.get("name", "Other"))))
        return choices[:25]

    async def twitch_action_autocomplete(interaction, current):
        catalog = get_twitch_action_catalog()
        if not catalog.get("ok"):
            return []
        category_filter = sanitize_text(getattr(interaction.namespace, "category", ""))
        needle = sanitize_text(current).lower()
        choices = []
        for item in catalog.get("actions", []):
            if not isinstance(item, dict) or not item.get("visible"):
                continue
            if category_filter and sanitize_text(item.get("category", "")) != category_filter:
                continue
            haystack = "{} {} {} {}".format(
                sanitize_text(item.get("name", "")),
                sanitize_text(item.get("title", "")),
                sanitize_text(item.get("command", "")),
                " ".join([sanitize_text(entry) for entry in item.get("category_labels", []) if sanitize_text(entry)]),
            ).lower()
            if needle and needle not in haystack:
                continue
            label = "{} | {} | {}".format(
                sanitize_text(item.get("title", item.get("name", "action"))) or "action",
                sanitize_text(item.get("command", "")) or "-",
                sanitize_text(item.get("category_label", "")) or "Other",
            )
            choices.append(app_commands.Choice(name=truncate_text(label, 100), value=sanitize_text(item.get("name", ""))))
        return choices[:25]

    async def send_twitch_ephemeral_response(interaction, content="", embed=None, view=None):
        kwargs = {"ephemeral": True}
        if content:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    async def execute_twitch_action_interaction(interaction, item, validation=None):
        if not is_discord_admin_interaction(interaction):
            await send_twitch_ephemeral_response(interaction, content="この操作は Discord 管理者のみ実行できます。")
            return

        action_validation = validation if isinstance(validation, dict) else evaluate_twitch_action_execution(item)
        if not action_validation.get("can_execute"):
            embed = build_twitch_action_detail_embed(item, action_validation)
            await send_twitch_ephemeral_response(
                interaction,
                content="この action は事前判定で実行不可です。詳細を確認してください。",
                embed=embed,
            )
            return

        if not TWITCH_CHAT_ENABLED:
            await send_twitch_ephemeral_response(interaction, content="TWITCH_CHAT_ENABLED=1 が必要です。")
            return

        try:
            result = await get_twitch_chat_bridge().send_chat_message_async(item.get("command", ""))
            embed = build_twitch_action_execution_embed(item, result)
            await send_twitch_ephemeral_response(interaction, embed=embed)
        except Exception as exc:
            await send_twitch_ephemeral_response(
                interaction,
                content="Twitch chat 送信に失敗しました: {}".format(sanitize_text(str(exc))),
            )

    class TwitchActionPageSelect(discord.ui.Select):
        def __init__(self, browser_view):
            self.browser_view = browser_view
            page_info = get_twitch_action_page_slice(
                browser_view.filtered_actions,
                page=browser_view.current_page,
                page_size=browser_view.page_size,
            )
            options = []
            for item in page_info.get("items", []):
                validation = evaluate_twitch_action_execution(item, sender_context=browser_view.sender_context)
                options.append(
                    discord.SelectOption(
                        label=truncate_text(sanitize_text(item.get("title", item.get("name", "action"))) or "action", 100),
                        value=sanitize_text(item.get("name", "")),
                        description=truncate_text(
                            "{} | {} | {}".format(
                                sanitize_text(item.get("command", "")) or "-",
                                validation.get("status_short", "不明"),
                                sanitize_text(item.get("category_label", "")) or "Other",
                            ),
                            100,
                        ),
                    )
                )

            self._is_placeholder = not bool(options)
            if not options:
                options = [
                    discord.SelectOption(
                        label="一致する action はありません",
                        value="__empty__",
                        description="No matching actions",
                    )
                ]

            super().__init__(
                placeholder="action を選択 / Select action",
                min_values=1,
                max_values=1,
                options=options,
                disabled=self._is_placeholder,
            )

        async def callback(self, interaction):
            selected_action = sanitize_text((self.values or [""])[0])
            if not selected_action or selected_action == "__empty__":
                await interaction.response.defer()
                return

            item = find_twitch_action_entry(self.browser_view.catalog, selected_action)
            if item is None:
                await send_twitch_ephemeral_response(interaction, content="指定した action が見つかりません。")
                return

            validation = evaluate_twitch_action_execution(item, sender_context=self.browser_view.sender_context)
            detail_view = TwitchActionDetailView(
                request_user_id=self.browser_view.request_user_id,
                item=item,
                validation=validation,
                catalog=self.browser_view.catalog,
                filtered_actions=self.browser_view.filtered_actions,
                selected_category=self.browser_view.selected_category,
                page=self.browser_view.current_page,
                page_size=self.browser_view.page_size,
                sender_context=self.browser_view.sender_context,
            )
            await interaction.response.edit_message(
                embed=build_twitch_action_detail_embed(item, validation),
                view=detail_view,
            )

    class TwitchActionBrowserView(discord.ui.View):
        def __init__(self, request_user_id, catalog, filtered_actions, selected_category="", page=1, page_size=12, sender_context=None):
            super().__init__(timeout=300)
            self.request_user_id = sanitize_text(request_user_id)
            self.catalog = catalog
            self.filtered_actions = list(filtered_actions or [])
            self.selected_category = sanitize_text(selected_category)
            self.page_size = max(1, safe_int(page_size, 12))
            self.sender_context = sender_context if isinstance(sender_context, dict) else get_twitch_action_sender_context()
            page_info = get_twitch_action_page_slice(self.filtered_actions, page=page, page_size=self.page_size)
            self.current_page = page_info.get("page", 1)
            self.total_pages = page_info.get("total_pages", 1)
            self.add_item(TwitchActionPageSelect(self))
            self.previous_page.disabled = self.current_page <= 1
            self.next_page.disabled = self.current_page >= self.total_pages

        async def interaction_check(self, interaction):
            if self.request_user_id and str(getattr(interaction.user, "id", "") or "") != self.request_user_id:
                await send_twitch_ephemeral_response(interaction, content="この UI はコマンド実行者専用です。")
                return False
            return True

        def build_embed(self):
            return build_twitch_action_list_embed(
                self.catalog,
                self.filtered_actions,
                selected_category=self.selected_category,
                page=self.current_page,
                page_size=self.page_size,
                sender_context=self.sender_context,
            )

        @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
        async def previous_page(self, interaction, button):
            new_view = TwitchActionBrowserView(
                request_user_id=self.request_user_id,
                catalog=self.catalog,
                filtered_actions=self.filtered_actions,
                selected_category=self.selected_category,
                page=max(1, self.current_page - 1),
                page_size=self.page_size,
                sender_context=self.sender_context,
            )
            await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
        async def next_page(self, interaction, button):
            new_view = TwitchActionBrowserView(
                request_user_id=self.request_user_id,
                catalog=self.catalog,
                filtered_actions=self.filtered_actions,
                selected_category=self.selected_category,
                page=min(self.total_pages, self.current_page + 1),
                page_size=self.page_size,
                sender_context=self.sender_context,
            )
            await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)

    class TwitchActionDetailView(discord.ui.View):
        def __init__(self, request_user_id, item, validation=None, catalog=None, filtered_actions=None, selected_category="", page=1, page_size=12, sender_context=None):
            super().__init__(timeout=300)
            self.request_user_id = sanitize_text(request_user_id)
            self.item = item
            self.validation = validation if isinstance(validation, dict) else evaluate_twitch_action_execution(item)
            self.catalog = catalog or {}
            self.filtered_actions = list(filtered_actions or [])
            self.selected_category = sanitize_text(selected_category)
            self.page = max(1, safe_int(page, 1))
            self.page_size = max(1, safe_int(page_size, 12))
            self.sender_context = sender_context if isinstance(sender_context, dict) else get_twitch_action_sender_context()
            self.back_to_list.disabled = not bool(self.filtered_actions)
            self.execute_action.disabled = not bool(self.validation.get("can_execute"))

        async def interaction_check(self, interaction):
            if self.request_user_id and str(getattr(interaction.user, "id", "") or "") != self.request_user_id:
                await send_twitch_ephemeral_response(interaction, content="この UI はコマンド実行者専用です。")
                return False
            return True

        @discord.ui.button(label="一覧へ戻る", style=discord.ButtonStyle.secondary)
        async def back_to_list(self, interaction, button):
            browser_view = TwitchActionBrowserView(
                request_user_id=self.request_user_id,
                catalog=self.catalog,
                filtered_actions=self.filtered_actions,
                selected_category=self.selected_category,
                page=self.page,
                page_size=self.page_size,
                sender_context=self.sender_context,
            )
            await interaction.response.edit_message(embed=browser_view.build_embed(), view=browser_view)

        @discord.ui.button(label="実行", style=discord.ButtonStyle.danger)
        async def execute_action(self, interaction, button):
            await execute_twitch_action_interaction(interaction, self.item, validation=self.validation)

    @command_tree.command(name="repost_messages", description="チャンネル履歴を embed で再投稿 / repost messages as embeds", **command_scope_kwargs)
    @app_commands.guild_only()
    @app_commands.describe(
        source_channel="転載元 channel / source channel",
        post_channel="転載先 channel / destination channel",
        limit="再投稿件数 (1-20) / number of messages",
        before_message_id="この message より前を取得 / fetch before this message id",
        after_message_id="この message より後を取得 / fetch after this message id",
        include_bots="Bot の投稿も含める / include bot messages",
    )
    async def repost_messages(
        interaction,
        source_channel: discord.TextChannel | None = None,
        post_channel: discord.TextChannel | None = None,
        limit: int = 10,
        before_message_id: str = "",
        after_message_id: str = "",
        include_bots: bool = False,
    ):
        if not is_discord_admin_interaction(interaction):
            await interaction.response.send_message("このコマンドは Discord 管理者のみ使用できます。", ephemeral=True)
            return

        current_channel = getattr(interaction, "channel", None)
        resolved_source_channel = source_channel or (current_channel if isinstance(current_channel, (discord.TextChannel, discord.Thread)) else None)
        resolved_post_channel = post_channel or (current_channel if isinstance(current_channel, (discord.TextChannel, discord.Thread)) else None)

        if resolved_source_channel is None:
            await interaction.response.send_message("source_channel を指定するか、対象 channel / thread で実行してください。", ephemeral=True)
            return
        if resolved_post_channel is None:
            await interaction.response.send_message("post_channel を指定するか、投稿先 channel / thread で実行してください。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            result = await asyncio.to_thread(
                repost_discord_channel_messages_as_embeds,
                str(getattr(resolved_source_channel, "id", "") or ""),
                str(getattr(resolved_post_channel, "id", "") or ""),
                limit,
                before_message_id,
                after_message_id,
                include_bots,
                sanitize_text(getattr(resolved_source_channel, "name", "")),
            )
        except Exception as exc:
            await interaction.followup.send(
                "Embed 再投稿に失敗しました: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
                ephemeral=True,
            )
            return

        posted_message_ids = result.get("posted_message_ids", []) if isinstance(result.get("posted_message_ids", []), list) else []
        first_jump_url = build_nexus_jump_url(str(getattr(resolved_post_channel, "id", "") or ""), posted_message_ids[0]) if posted_message_ids else ""
        last_jump_url = build_nexus_jump_url(str(getattr(resolved_post_channel, "id", "") or ""), posted_message_ids[-1]) if posted_message_ids else ""

        response_lines = [
            "Embed 再投稿を完了しました。",
            "取得 {} 件 / 投稿 {} 件 / Bot 除外 {} 件 / 空メッセージ除外 {} 件".format(
                int(result.get("fetched", 0) or 0),
                int(result.get("posted", 0) or 0),
                int(result.get("skipped_bots", 0) or 0),
                int(result.get("skipped_empty", 0) or 0),
            ),
            "投稿メッセージには「管理者投稿編集」ボタンを付けています。タイトル・本文・画像URLを後から修正できます。",
        ]
        if first_jump_url:
            response_lines.append("先頭: {}".format(first_jump_url))
        if last_jump_url and last_jump_url != first_jump_url:
            response_lines.append("末尾: {}".format(last_jump_url))

        await interaction.followup.send("\n".join(response_lines), ephemeral=True)

    @command_tree.command(name="notify", description="通知状態を表示 / Show relay status", **command_scope_kwargs)
    @app_commands.guild_only()
    @app_commands.describe(
        mode="通知モード / notify mode",
        operation="管理操作 / operation",
        voice_channel="監視対象VC / source voice channel",
        post_channel="投稿先テキスト channel / destination text channel",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="twitch", value="twitch"),
            app_commands.Choice(name="profile", value="profile"),
        ]
    )
    @app_commands.choices(
        operation=[
            app_commands.Choice(name="status", value="status"),
            app_commands.Choice(name="status_detail", value="status_detail"),
            app_commands.Choice(name="reconnect", value="reconnect"),
            app_commands.Choice(name="disconnect", value="disconnect"),
            app_commands.Choice(name="clear_auth", value="clear_auth"),
            app_commands.Choice(name="set", value="set"),
            app_commands.Choice(name="clear", value="clear"),
            app_commands.Choice(name="test", value="test"),
        ]
    )
    async def notify(
        interaction,
        mode: str,
        operation: str = "status",
        voice_channel: discord.VoiceChannel | None = None,
        post_channel: discord.TextChannel | None = None,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        operation_name = sanitize_text(operation) or "status"

        if mode == "profile":
            if not is_discord_admin_interaction(interaction):
                await interaction.followup.send("このコマンドは Discord 管理者のみ使用できます。", ephemeral=True)
                return

            current_state = get_profile_notify_state_snapshot()
            if operation_name == "status":
                await interaction.followup.send(embed=build_profile_notify_status_embed(current_state), ephemeral=True)
                return

            if operation_name == "clear":
                cleared_state = clear_profile_notify_state()
                await interaction.followup.send(
                    content="プロフィール VC 通知設定をクリアしました。",
                    embed=build_profile_notify_status_embed(cleared_state),
                    ephemeral=True,
                )
                return

            if operation_name == "set":
                interaction_guild_id = getattr(getattr(interaction, "guild", None), "id", None)
                if voice_channel is not None and getattr(getattr(voice_channel, "guild", None), "id", None) != interaction_guild_id:
                    await interaction.followup.send("監視対象 VC は同じ guild 内から選択してください。", ephemeral=True)
                    return
                if post_channel is not None and getattr(getattr(post_channel, "guild", None), "id", None) != interaction_guild_id:
                    await interaction.followup.send("投稿先 channel は同じ guild 内から選択してください。", ephemeral=True)
                    return

                resolved_voice_channel_id = sanitize_text(current_state.get("voice_channel_id", ""))
                resolved_voice_channel_name = sanitize_text(current_state.get("voice_channel_name", ""))
                if voice_channel is not None:
                    resolved_voice_channel_id = str(getattr(voice_channel, "id", "") or "")
                    resolved_voice_channel_name = sanitize_text(getattr(voice_channel, "name", ""))

                resolved_post_channel_id = sanitize_text(current_state.get("post_channel_id", ""))
                resolved_post_channel_name = sanitize_text(current_state.get("post_channel_name", ""))
                if post_channel is not None:
                    resolved_post_channel_id = str(getattr(post_channel, "id", "") or "")
                    resolved_post_channel_name = sanitize_text(getattr(post_channel, "name", ""))
                elif not resolved_post_channel_id:
                    current_channel = getattr(interaction, "channel", None)
                    if isinstance(current_channel, (discord.TextChannel, discord.Thread)):
                        resolved_post_channel_id = str(getattr(current_channel, "id", "") or "")
                        resolved_post_channel_name = sanitize_text(getattr(current_channel, "name", ""))

                if not resolved_voice_channel_id.isdigit():
                    await interaction.followup.send("voice_channel を指定してください。", ephemeral=True)
                    return
                if not resolved_post_channel_id.isdigit():
                    await interaction.followup.send("投稿先 text channel を指定してください。", ephemeral=True)
                    return

                updated_state = configure_profile_notify_state(
                    resolved_voice_channel_id,
                    resolved_voice_channel_name,
                    resolved_post_channel_id,
                    resolved_post_channel_name,
                )
                await interaction.followup.send(
                    content="プロフィール VC 通知を更新しました。",
                    embed=build_profile_notify_status_embed(updated_state),
                    ephemeral=True,
                )
                return

            if operation_name == "test":
                if not bool(current_state.get("enabled", False)):
                    await interaction.followup.send("先に operation:set で監視 VC と投稿先 channel を設定してください。", ephemeral=True)
                    return
                try:
                    await post_profile_notify_message(
                        str(getattr(interaction.user, "id", "") or ""),
                        current_state.get("post_channel_id", ""),
                        voice_channel_id=current_state.get("voice_channel_id", ""),
                        voice_channel_name=current_state.get("voice_channel_name", ""),
                    )
                except Exception as exc:
                    await interaction.followup.send(
                        "テスト投稿に失敗しました: {}".format(truncate_text(sanitize_text(str(exc)), 1800)),
                        ephemeral=True,
                    )
                    return

                await interaction.followup.send(
                    content="テスト投稿を送信しました。",
                    embed=build_profile_notify_status_embed(get_profile_notify_state_snapshot()),
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                "profile mode では status / set / clear / test を使用してください。",
                ephemeral=True,
            )
            return

        if mode != "twitch":
            await interaction.followup.send("未対応の mode です。", ephemeral=True)
            return

        if not can_manage_twitch_chat_auth_interaction(interaction):
            await interaction.followup.send(
                "このコマンドは Twitch chat 認可 owner または Discord 管理者のみ使用できます。",
                ephemeral=True,
            )
            return

        authorize_url = ""

        if operation_name == "disconnect":
            stop_twitch_chat_bridge()
        elif operation_name == "reconnect":
            reconnect_twitch_chat_bridge()
        elif operation_name == "clear_auth":
            stop_twitch_chat_bridge()
            clear_twitch_chat_auth_state()

        if TWITCH_CHAT_ENABLED and TWITCH_CLIENT_ID and BOT_PUBLIC_BASE_URL:
            try:
                authorize_url = build_twitch_chat_authorize_url(discord_user_id=str(getattr(interaction.user, "id", "") or ""))
            except Exception as exc:
                with twitch_chat_lock:
                    twitch_chat_state["last_error"] = sanitize_text(str(exc))

        state = get_twitch_chat_bridge().state_snapshot()
        if operation_name == "status":
            embed = build_twitch_chat_status_embed(state, authorize_url=authorize_url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        content = {
            "status_detail": "Twitch chat relay の詳細状態です。",
            "reconnect": "Twitch chat bridge を再接続しました。",
            "disconnect": "Twitch chat bridge を切断しました。",
            "clear_auth": "保存済み Twitch OAuth をクリアしました。",
        }.get(operation_name, "Twitch chat relay の状態です。")
        if operation_name == "clear_auth" and TWITCH_CHAT_USER_ACCESS_TOKEN:
            content += " 環境変数トークンは残るため、env source の場合は再認可なしで動作する可能性があります。"

        embed = build_twitch_chat_status_detail_embed(state, authorize_url=authorize_url)
        await interaction.followup.send(content=content, embed=embed, ephemeral=True)

    @command_tree.command(name="twitch", description="twitch.xml action 一覧と実行 / list and run twitch actions", **command_scope_kwargs)
    @app_commands.guild_only()
    @app_commands.describe(
        mode="表示モード / view mode",
        category="カテゴリ / category",
        action="action を選択 / select action",
        execute="管理者として実行 / run as admin",
        page="一覧ページ / page",
    )
    @app_commands.choices(mode=[app_commands.Choice(name="v2.6コマンド", value="v26_command")])
    @app_commands.autocomplete(category=twitch_category_autocomplete, action=twitch_action_autocomplete)
    async def twitch(interaction, mode: str, category: str = "", action: str = "", execute: bool = False, page: int = 1):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if mode != "v26_command":
            await interaction.followup.send("未対応の mode です。", ephemeral=True)
            return

        catalog = get_twitch_action_catalog()
        if not catalog.get("ok"):
            await interaction.followup.send(
                "twitch.xml の読込に失敗しました: {}".format(sanitize_text(catalog.get("error", "unknown error"))),
                ephemeral=True,
            )
            return

        category_filter = sanitize_text(category)
        filtered_actions = filter_twitch_action_entries(catalog, category_name=category_filter)
        sender_context = get_twitch_action_sender_context()

        if action:
            item = find_twitch_action_entry(catalog, action)
            if item is None:
                await interaction.followup.send("指定した action が見つかりません。", ephemeral=True)
                return

            validation = evaluate_twitch_action_execution(item, sender_context=sender_context)

            if execute:
                if not is_discord_admin_interaction(interaction):
                    await interaction.followup.send("この操作は Discord 管理者のみ実行できます。", ephemeral=True)
                    return
                if not validation.get("can_execute"):
                    embed = build_twitch_action_detail_embed(item, validation)
                    await interaction.followup.send(
                        "この action は事前判定で実行不可です。詳細を確認してください。",
                        embed=embed,
                        ephemeral=True,
                    )
                    return
                if not TWITCH_CHAT_ENABLED:
                    await interaction.followup.send("TWITCH_CHAT_ENABLED=1 が必要です。", ephemeral=True)
                    return

                try:
                    result = await get_twitch_chat_bridge().send_chat_message_async(item.get("command", ""))
                    embed = build_twitch_action_execution_embed(item, result)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except Exception as exc:
                    await interaction.followup.send("Twitch chat 送信に失敗しました: {}".format(sanitize_text(str(exc))), ephemeral=True)
                return

            detail_view = TwitchActionDetailView(
                request_user_id=str(getattr(interaction.user, "id", "") or ""),
                item=item,
                validation=validation,
                catalog=catalog,
                filtered_actions=filtered_actions,
                selected_category=category_filter,
                page=page,
                page_size=12,
                sender_context=sender_context,
            )
            embed = build_twitch_action_detail_embed(item, validation)
            await interaction.followup.send(embed=embed, view=detail_view, ephemeral=True)
            return

        browser_view = TwitchActionBrowserView(
            request_user_id=str(getattr(interaction.user, "id", "") or ""),
            catalog=catalog,
            filtered_actions=filtered_actions,
            selected_category=category_filter,
            page=page,
            page_size=12,
            sender_context=sender_context,
        )
        embed = browser_view.build_embed()
        await interaction.followup.send(embed=embed, view=browser_view, ephemeral=True)

    @command_tree.error
    async def on_app_command_error(interaction, error):
        message = "コマンド処理に失敗しました: {}".format(sanitize_text(str(error)))
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            pass


def start_gateway_client():
    if not DISCORD_GATEWAY_ENABLED:
        set_gateway_state(error="gateway disabled by DISCORD_GATEWAY_ENABLED")
        print("Discord gateway disabled")
        return

    if discord is None:
        set_gateway_state(error="discord.py is not installed")
        print("discord.py is not installed; gateway connection is skipped")
        return

    # サーバーメッセージイベント + メッセージ内容取得 Intent を追加
    # （Discord Developer Portal でも "Message Content Intent" を有効化すること）
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    intents.voice_states = True

    class PresenceClient(discord.Client):
        async def setup_hook(self):
            try:
                synced, sync_scope = await sync_gateway_commands(self.command_tree)
                set_gateway_state(
                    command_count=len(synced),
                    command_sync_scope=sync_scope,
                    command_sync_error="",
                )
            except Exception as exc:
                set_gateway_state(command_sync_error=str(exc))
                print("Gateway command sync error: {}".format(exc))

        async def on_ready(self):
            global _discord_client
            _discord_client = self
            display_name = ""
            try:
                if self.user is not None:
                    display_name = str(self.user)
            except Exception:
                display_name = ""
            set_gateway_state(connected=True, ready=True, user=display_name, error="")
            print("Gateway connected as {}".format(display_name))

        async def on_disconnect(self):
            global _discord_client
            _discord_client = None
            set_gateway_state(connected=False, ready=False)

        async def on_resumed(self):
            set_gateway_state(connected=True, ready=True, error="")

        async def on_voice_state_update(self, member, before, after):
            try:
                if getattr(member, "bot", False):
                    return

                joined_channel = getattr(after, "channel", None)
                previous_channel = getattr(before, "channel", None)
                joined_channel_id = str(getattr(joined_channel, "id", "") or "")
                previous_channel_id = str(getattr(previous_channel, "id", "") or "")
                if not joined_channel_id or joined_channel_id == previous_channel_id:
                    return

                state = get_profile_notify_state_snapshot()
                watched_voice_channel_id = sanitize_text(state.get("voice_channel_id", ""))
                post_channel_id = sanitize_text(state.get("post_channel_id", ""))
                if not bool(state.get("enabled", False)):
                    return
                if not watched_voice_channel_id.isdigit() or not post_channel_id.isdigit():
                    return
                if joined_channel_id != watched_voice_channel_id:
                    return

                await post_profile_notify_message(
                    str(getattr(member, "id", "") or ""),
                    post_channel_id,
                    voice_channel_id=joined_channel_id,
                    voice_channel_name=sanitize_text(getattr(joined_channel, "name", "")),
                )
            except Exception as exc:
                print("Profile VC notify error: {}".format(exc))

        async def on_interaction(self, interaction):
            try:
                if interaction.type != discord.InteractionType.component:
                    return
                data = getattr(interaction, "data", {}) or {}
                custom_id = str(data.get("custom_id", "") or "")
                if custom_id == PROFILE_CARD_THREAD_TOGGLE_CUSTOM_ID:
                    await handle_profile_card_thread_toggle_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_EDIT_BUTTON_PREFIX + ":"):
                    await handle_profile_card_edit_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_INVITE_BUTTON_PREFIX + ":"):
                    await handle_profile_card_invite_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_IMAGE_BUTTON_PREFIX + ":"):
                    await handle_profile_card_image_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_TAG_BUTTON_PREFIX + ":"):
                    await handle_profile_card_tag_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_CHANNEL_BUTTON_PREFIX + ":"):
                    await handle_profile_card_channel_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_WORKSPACE_BUTTON_PREFIX + ":"):
                    await handle_profile_card_workspace_interaction(interaction)
                elif custom_id.startswith(PROFILE_CARD_DELETE_BUTTON_PREFIX + ":"):
                    await handle_profile_card_thread_delete_interaction(interaction)
                elif custom_id in (CHANNEL_REPOST_EDIT_BUTTON_CUSTOM_ID, CHANNEL_REPOST_LEGACY_IMAGE_BUTTON_CUSTOM_ID):
                    await handle_channel_repost_edit_interaction(interaction)
                elif custom_id in (NEXUS_FAVORITE_BUTTON_CUSTOM_ID, NEXUS_LEGACY_SAVE_BUTTON_CUSTOM_ID):
                    await handle_nexus_favorite_interaction(interaction)
                elif custom_id in (TWITCH_FAVORITE_BUTTON_CUSTOM_ID, TWITCH_LEGACY_SAVE_BUTTON_CUSTOM_ID):
                    await handle_twitch_favorite_interaction(interaction)
                elif custom_id in (TWITTER_FAVORITE_BUTTON_CUSTOM_ID, TWITTER_LEGACY_SAVE_BUTTON_CUSTOM_ID):
                    await handle_twitter_favorite_interaction(interaction)
                elif custom_id in (YOUTUBE_FAVORITE_BUTTON_CUSTOM_ID, YOUTUBE_LEGACY_SAVE_BUTTON_CUSTOM_ID):
                    await handle_youtube_favorite_interaction(interaction)
            except Exception as exc:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send("ボタン処理に失敗しました: {}".format(exc), ephemeral=True)
                    else:
                        await interaction.response.send_message("ボタン処理に失敗しました: {}".format(exc), ephemeral=True)
                except Exception:
                    pass

    client = PresenceClient(intents=intents)
    client.command_tree = discord.app_commands.CommandTree(client)
    register_gateway_commands(client.command_tree)

    async def runner():
        try:
            await client.start(DISCORD_BOT_TOKEN)
        except Exception as exc:
            set_gateway_state(connected=False, ready=False, error=str(exc))
            print("Gateway error: {}".format(exc))

    def run_loop():
        global _discord_loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _discord_loop = loop
        try:
            loop.run_until_complete(runner())
        finally:
            _discord_loop = None

    t = threading.Thread(target=run_loop)
    t.daemon = True
    t.start()


def fetch_voice_channel_members(channel_id):
    channel_id = sanitize_text(channel_id)
    if not channel_id or not channel_id.isdigit():
        raise RuntimeError("channel_id is required")
    if not DISCORD_GUILD_ID:
        raise RuntimeError("DISCORD_GUILD_ID is not set")
    runtime = ensure_gateway_runtime()
    if not runtime.get("runtime_ok"):
        raise RuntimeError("Discord gateway not connected")

    async def _collect():
        guild = _discord_client.get_guild(int(DISCORD_GUILD_ID))
        if guild is None:
            raise RuntimeError("guild is not cached yet")

        channel = guild.get_channel(int(channel_id))
        if channel is None:
            raise RuntimeError("channel not found")

        members = []
        for member in list(getattr(channel, "members", []) or []):
            if member is None:
                continue
            members.append(
                {
                    "id": str(getattr(member, "id", "") or ""),
                    "name": sanitize_text(getattr(member, "display_name", "") or getattr(member, "name", "Unknown")),
                }
            )

        members.sort(key=lambda item: item.get("name", "").lower())
        return {
            "ok": True,
            "guild_id": DISCORD_GUILD_ID,
            "channel_id": channel_id,
            "count": len(members),
            "members": members,
            "updated_at": now_iso_utc(),
        }

    future = asyncio.run_coroutine_threadsafe(_collect(), _discord_loop)
    return future.result(timeout=10)


class Handler(BaseHTTPRequestHandler):
    def _authorized(self):
        if BOT_API_SHARED_KEY == "":
            return True
        provided = self.headers.get("X-Api-Key", "")
        return provided == BOT_API_SHARED_KEY

    def _send_json(self, obj, code=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html_text, code=200):
        payload = str(html_text or "").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        if length > 65536:
            raise ValueError("payload too large")
        raw = self.rfile.read(length).decode("utf-8")
        if raw.strip() == "":
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("json body must be an object")
        return data

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            with snapshot_lock:
                ok = bool(snapshot.get("ok"))
            with gateway_lock:
                gw = dict(gateway_state)
            with twitch_chat_lock:
                twitch_chat = dict(twitch_chat_state)
            runtime = get_gateway_runtime_check()
            if not runtime.get("runtime_ok") and (gw.get("connected") or gw.get("ready")):
                set_gateway_state(connected=False, ready=False)
                with gateway_lock:
                    gw = dict(gateway_state)
            self._send_json({"ok": True, "discord_ok": ok, "gateway": gw, "runtime_check": runtime, "twitch_chat": twitch_chat})
            return

        if path == "/oauth/twitch/callback":
            error_code = sanitize_text((query.get("error", [""]) or [""])[0])
            if error_code:
                error_description = sanitize_text((query.get("error_description", [""]) or [""])[0])
                html_text = build_twitch_chat_oauth_result_html(
                    False,
                    "Twitch OAuth Error",
                    error_description or error_code,
                )
                self._send_html(html_text, code=400)
                return

            code_value = sanitize_text((query.get("code", [""]) or [""])[0])
            state_value = sanitize_text((query.get("state", [""]) or [""])[0])
            support_oauth_state = find_twitch_support_oauth_session(state_value)
            if not code_value or not state_value:
                self._send_html(
                    build_twitch_chat_oauth_result_html(False, "Twitch OAuth Error", "code または state が不足しています。"),
                    code=400,
                )
                return

            try:
                if support_oauth_state is not None:
                    auth_payload = complete_twitch_support_oauth(code_value, state_value)
                    html_text = build_twitch_chat_oauth_result_html(
                        True,
                        "Twitch Support Connected",
                        "Twitch Support 用の配信者連携を保存しました。",
                        login=sanitize_text(auth_payload.get("login", "")),
                        scopes=auth_payload.get("scopes", []),
                        follow_up_command="/twitch_support settings",
                    )
                else:
                    auth_payload = complete_twitch_chat_oauth(code_value, state_value)
                    try:
                        start_twitch_chat_bridge()
                    except Exception:
                        pass
                    html_text = build_twitch_chat_oauth_result_html(
                        True,
                        "Twitch OAuth Completed",
                        "Twitch chat relay 用の認可を保存しました。",
                        login=sanitize_text(auth_payload.get("login", "")),
                        scopes=auth_payload.get("scopes", []),
                    )
                self._send_html(html_text, code=200)
            except Exception as exc:
                html_text = build_twitch_chat_oauth_result_html(False, "Twitch OAuth Error", sanitize_text(str(exc)))
                self._send_html(html_text, code=400)
            return

        if not self._authorized():
            self._send_json({"ok": False, "error": "unauthorized"}, code=401)
            return

        if path == "/threads/active":
            refresh_snapshot()
            with snapshot_lock:
                data = dict(snapshot)
            self._send_json(data)
            return

        if path.startswith("/nexus/watch/latest"):
            with nexus_notify_lock:
                state = dict(nexus_notify_state)
            self._send_json({"ok": True, "state": state})
            return

        if path.startswith("/social/watch/latest"):
            with social_notify_lock:
                state = dict(social_notify_state)
            with twitch_notify_lock:
                tw = dict(twitch_notify_state)
            with twitch_chat_lock:
                twitch_chat = dict(twitch_chat_state)
            with twitter_notify_lock:
                tx = dict(twitter_notify_state)
            with youtube_notify_lock:
                yt = dict(youtube_notify_state)
            with youtube_comments_notify_lock:
                yt_comments = dict(youtube_comments_notify_state)
            with youtube_livechat_notify_lock:
                yt_livechat = dict(youtube_livechat_notify_state)
            self._send_json({"ok": True, "state": state, "twitch": tw, "twitch_chat": twitch_chat, "twitter": tx, "youtube": yt, "youtube_comments": yt_comments, "youtube_livechat": yt_livechat})
            return

        if path.startswith("/twitch/vrc/playlist"):
            limit_values = query.get("limit", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 20, 20), 100))
            self._send_json(build_twitch_vrc_playlist(limit=limit))
            return

        if path.startswith("/twitch/chat/recent"):
            limit_values = query.get("limit", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 20, 20), 100))
            items = get_twitch_chat_bridge().recent_items(limit=limit)
            self._send_json({"ok": True, "count": len(items), "items": items, "updated_at": now_iso_utc()})
            return

        if path.startswith("/youtube/comments/watch/latest"):
            with youtube_comments_notify_lock:
                state = dict(youtube_comments_notify_state)
            self._send_json({"ok": True, "state": state})
            return

        if path.startswith("/youtube/comments/recent"):
            limit_values = query.get("limit", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 20, 20), 100))
            with youtube_comments_notify_lock:
                items = list(youtube_comments_notify_state.get("recent_items", []) if isinstance(youtube_comments_notify_state.get("recent_items"), list) else [])
                updated_at = youtube_comments_notify_state.get("last_run")
            self._send_json({"ok": True, "count": min(len(items), limit), "items": items[:limit], "updated_at": updated_at})
            return

        if path.startswith("/youtube/livechat/watch/latest"):
            with youtube_livechat_notify_lock:
                state = dict(youtube_livechat_notify_state)
            self._send_json({"ok": True, "state": state})
            return

        if path.startswith("/youtube/livechat/recent"):
            limit_values = query.get("limit", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 20, 20), 100))
            with youtube_livechat_notify_lock:
                items = list(youtube_livechat_notify_state.get("recent_items", []) if isinstance(youtube_livechat_notify_state.get("recent_items"), list) else [])
                updated_at = youtube_livechat_notify_state.get("last_run")
                active_chat_count = len(youtube_livechat_notify_state.get("active_chat_ids", [])) if isinstance(youtube_livechat_notify_state.get("active_chat_ids"), list) else 0
            self._send_json({"ok": True, "count": min(len(items), limit), "items": items[:limit], "active_chat_count": active_chat_count, "updated_at": updated_at})
            return

        if path.startswith("/comments/watch/latest"):
            with comments_notify_lock:
                state = dict(comments_notify_state)
            self._send_json({"ok": True, "state": state})
            return

        if path.startswith("/pages/watch/latest"):
            with page_promo_lock:
                state = dict(page_promo_state)
            self._send_json({"ok": True, "state": state})
            return

        if path == "/instance-spaces":
            discord_ids = query.get("discord_id", [])
            discord_user_id = sanitize_text(discord_ids[0] if discord_ids else "")
            role_prefixes = query.get("role_prefix", [])
            role_prefix = sanitize_text(role_prefixes[0] if role_prefixes else DISCORD_INSTANCE_ROLE_PREFIX)
            try:
                data = fetch_instance_space_channels(discord_user_id, role_prefix=role_prefix)
            except Exception as exc:
                data = {
                    "ok": False,
                    "guild_id": DISCORD_GUILD_ID,
                    "discord_user_id": discord_user_id,
                    "groups": [],
                    "owned_roles": [],
                    "channel_count": 0,
                    "error": str(exc),
                    "updated_at": now_iso_utc(),
                }
            self._send_json(data)
            return

        if path.startswith("/announcements/latest"):
            limit = 20
            values = query.get("limit", [])
            if values:
                try:
                    limit = int(values[0])
                except Exception:
                    limit = 20
            try:
                data = fetch_announcements(limit=limit)
            except Exception as exc:
                data = {
                    "ok": False,
                    "channel_id": DISCORD_ANNOUNCEMENT_CHANNEL_ID,
                    "count": 0,
                    "updated_at": now_iso_utc(),
                    "messages": [],
                    "error": str(exc),
                }
            self._send_json(data)
            return

        if path.startswith("/events/leaderboard"):
            limit_values = query.get("limit", [])
            guild_values = query.get("guild_id", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 10, 10), 20))
            guild_id = sanitize_text(guild_values[0] if guild_values else "")
            data = fetch_event_points_leaderboard(limit=limit, guild_id=guild_id)
            self._send_json(data)
            return

        if path.startswith("/events/party-leaderboard"):
            limit_values = query.get("limit", [])
            guild_values = query.get("guild_id", [])
            limit = max(1, min(safe_int(limit_values[0] if limit_values else 10, 10), 20))
            guild_id = sanitize_text(guild_values[0] if guild_values else "")
            data = fetch_bear_party_leaderboard(limit=limit, guild_id=guild_id)
            self._send_json(data)
            return

        if path == "/voice/members":
            channel_ids = query.get("channel_id", [])
            channel_id = sanitize_text(channel_ids[0] if channel_ids else "")
            try:
                data = fetch_voice_channel_members(channel_id)
            except Exception as exc:
                data = {
                    "ok": False,
                    "guild_id": DISCORD_GUILD_ID,
                    "channel_id": channel_id,
                    "count": 0,
                    "members": [],
                    "error": str(exc),
                    "updated_at": now_iso_utc(),
                }
            self._send_json(data)
            return

        if path == "/chat/voice-members":
            channel_ids = query.get("channel_id", [])
            channel_id = sanitize_text(channel_ids[0] if channel_ids else "")
            try:
                data = fetch_voice_channel_members(channel_id)
            except Exception as exc:
                data = {
                    "ok": False,
                    "guild_id": DISCORD_GUILD_ID,
                    "channel_id": channel_id,
                    "count": 0,
                    "members": [],
                    "error": str(exc),
                    "updated_at": now_iso_utc(),
                }
            self._send_json(data)
            return

        # ----------------------------------------
        # チャットメッセージ取得（テキスト / スレッド共通）
        # ----------------------------------------
        if path == "/chat/messages":
            channel_ids = query.get("channel_id", [])
            channel_id = sanitize_text(channel_ids[0] if channel_ids else "")
            if not channel_id or not channel_id.isdigit():
                self._send_json({"ok": False, "error": "channel_id is required"}, code=400)
                return
            after_vals = query.get("after", [])
            after = sanitize_text(after_vals[0] if after_vals else "")
            embed_mode_vals = query.get("embed_mode", [])
            embed_mode = sanitize_text(embed_mode_vals[0] if embed_mode_vals else "") or "full"
            api_path = "/channels/{}/messages?limit=50".format(channel_id)
            if after and after.isdigit():
                api_path += "&after={}".format(after)
            try:
                msgs = discord_request_json(api_path)
                if not isinstance(msgs, list):
                    raise RuntimeError("unexpected response from Discord API")
                # Discord REST は新着順で返すため古い順に並び替え
                msgs.sort(key=lambda m: str(m.get("id", "0")))
                result = {
                    "ok": True,
                    "channel_id": channel_id,
                    "messages": [
                        {
                            "id": str(m.get("id", "")),
                            "content": sanitize_text(m.get("content", "")) or discord_message_embed_text(m, mode=embed_mode),
                            "author": sanitize_text(
                                str(
                                    m.get("author", {}).get("global_name")
                                    or m.get("author", {}).get("username", "Unknown")
                                )
                            ),
                            "timestamp": str(m.get("timestamp", "")),
                            "is_bot": bool(m.get("author", {}).get("bot", False)),
                        }
                        for m in msgs
                        if isinstance(m, dict)
                    ],
                }
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            self._send_json(result)
            return

        # ----------------------------------------
        # フォーラムチャンネルのスレッド一覧取得
        # ----------------------------------------
        if path == "/chat/forum-posts":
            channel_ids = query.get("channel_id", [])
            channel_id = sanitize_text(channel_ids[0] if channel_ids else "")
            if not channel_id or not channel_id.isdigit():
                self._send_json({"ok": False, "error": "channel_id is required"}, code=400)
                return
            try:
                # アクティブスレッド（ギルド全体）から parent_id で絞り込み
                all_active = discord_request_json("/guilds/{}/threads/active".format(DISCORD_GUILD_ID))
                active_threads = [
                    t for t in (all_active.get("threads", []) if isinstance(all_active, dict) else [])
                    if isinstance(t, dict) and str(t.get("parent_id", "")) == channel_id
                ]
                # アーカイブ済みスレッド
                try:
                    archived_data = discord_request_json(
                        "/channels/{}/threads/archived/public?limit=25".format(channel_id)
                    )
                    archived_threads = archived_data.get("threads", []) if isinstance(archived_data, dict) else []
                except Exception:
                    archived_threads = []
                # 重複除去してマージ
                seen_ids = {str(t.get("id", "")) for t in active_threads}
                for t in archived_threads:
                    if isinstance(t, dict) and str(t.get("id", "")) not in seen_ids:
                        active_threads.append(t)
                threads = []
                for t in active_threads:
                    if not isinstance(t, dict):
                        continue
                    threads.append({
                        "id": str(t.get("id", "")),
                        "name": sanitize_text(t.get("name", "")),
                        "message_count": int(t.get("message_count", 0) or 0),
                        "archived": bool((t.get("thread_metadata") or {}).get("archived", False)),
                    })
                threads.sort(key=lambda x: x["name"].lower())
                result = {"ok": True, "channel_id": channel_id, "threads": threads}
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            self._send_json(result)
            return

        self._send_json({"ok": False, "error": "not found"}, code=404)

    def do_POST(self):
        if not self._authorized():
            self._send_json({"ok": False, "error": "unauthorized"}, code=401)
            return

        if self.path == "/profile/grant-role":
            self._send_json(
                {"ok": False, "error": "role assignment has been retired; use /profile/card/sync if you only need profile sync"},
                code=410,
            )
            return

        if self.path == "/profile/bootstrap":
            try:
                body = self._read_json_body()
                result = sync_profile_card_to_discord(body)
                self._send_json(result, code=200)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/profile/card/sync":
            try:
                body = self._read_json_body()
                result = sync_profile_card_to_discord(body)
                self._send_json(result, code=200)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/announcements/sync":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", 20) or 20)
                max_retries = int(body.get("max_retries", 3) or 3)
                if limit < 1:
                    limit = 1
                if limit > 100:
                    limit = 100
                if max_retries < 1:
                    max_retries = 1
                if max_retries > 5:
                    max_retries = 5

                result = push_announcements_to_wordpress(limit=limit, max_retries=max_retries)
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/nexus/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=20, max_limit=100)
                result = sync_nexus_watch_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/nexus/rebucket":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", 100) or 100)
                if limit < 1:
                    limit = 1
                if limit > 1000:
                    limit = 1000

                result = rebucket_existing_nexus_messages_to_creator_threads(
                    limit=limit,
                    before_message_id=body.get("before_message_id", ""),
                    force=parse_request_bool(body.get("force", "")),
                    source_channel_id=body.get("source_channel_id", ""),
                )
                self._send_json(result, code=200)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/nexus/retag":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", 200) or 200)
                if limit < 1:
                    limit = 1
                if limit > 500:
                    limit = 500

                result = retag_existing_nexus_creator_threads(limit=limit)
                self._send_json(result, code=200)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/twitch/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=TWITCH_NOTIFY_FETCH_LIMIT, max_limit=100)
                result = sync_twitch_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/twitter/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=TWITTER_NOTIFY_FETCH_LIMIT, max_limit=100)
                result = sync_twitter_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/social/sync":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", 20) or 20)
                result = sync_social_watch_notifications(limit=limit)
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/comments/sync":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", 20) or 20)
                result = sync_comment_notifications(limit=limit)
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/youtube/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=20, max_limit=100)
                force_refresh = parse_request_bool(body.get("force_refresh", ""))
                allow_direct_fallback = parse_request_bool(body.get("allow_direct_fallback", ""))
                result = sync_youtube_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                    wordpress_force_refresh=force_refresh,
                    allow_direct_fallback=allow_direct_fallback,
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                if force_refresh:
                    result["force_refresh"] = True
                if allow_direct_fallback:
                    result["allow_direct_fallback"] = True
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/youtube/comments/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=YOUTUBE_COMMENTS_FETCH_LIMIT, max_limit=100)
                result = sync_youtube_comment_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/youtube/livechat/sync":
            try:
                body = self._read_json_body()
                options = resolve_sync_request_options(body, default_limit=YOUTUBE_LIVECHAT_FETCH_LIMIT, max_limit=200)
                result = sync_youtube_livechat_notifications(
                    limit=options["limit"],
                    force_send_seen=options["force_send_seen"],
                    min_timestamp=options["min_timestamp"],
                )
                if options["backfill_days"] is not None:
                    result["backfill_days"] = options["backfill_days"]
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        if self.path == "/bridge/pages/sync":
            try:
                body = self._read_json_body()
                limit = int(body.get("limit", PAGE_PROMO_MAX_ITEMS_PER_SYNC) or PAGE_PROMO_MAX_ITEMS_PER_SYNC)
                force_raw = str(body.get("force", "") or "").strip().lower()
                force_send_seen = force_raw in ("1", "true", "on", "yes")
                result = sync_wordpress_page_promotions(limit=limit, force_send_seen=force_send_seen)
                code = 200 if result.get("ok") else 502
                self._send_json(result, code=code)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=500)
                return

        # ----------------------------------------
        # Webサイトから Discord チャンネルへメッセージ送信
        # ----------------------------------------
        if self.path == "/chat/send":
            try:
                body = self._read_json_body()
                channel_id = sanitize_text(str(body.get("channel_id", "") or ""))
                content = sanitize_text(str(body.get("content", "") or ""))
                author = sanitize_text(str(body.get("author", "匿名") or "匿名")) or "匿名"

                if not channel_id or not channel_id.isdigit():
                    self._send_json({"ok": False, "error": "channel_id is required"}, code=400)
                    return
                if not content:
                    self._send_json({"ok": False, "error": "content is required"}, code=400)
                    return
                if len(content) > 1900:
                    self._send_json({"ok": False, "error": "content too long (max 1900)"}, code=400)
                    return

                runtime = ensure_gateway_runtime()
                if not runtime.get("runtime_ok"):
                    self._send_json({"ok": False, "error": "Discord gateway not connected"}, code=503)
                    return

                text = "**[{}]** {}".format(author, content)

                async def _send():
                    ch = _discord_client.get_channel(int(channel_id))
                    if ch is None:
                        ch = await _discord_client.fetch_channel(int(channel_id))
                    return await ch.send(text)

                future = asyncio.run_coroutine_threadsafe(_send(), _discord_loop)
                try:
                    msg = future.result(timeout=15)
                    result = {"ok": True, "message_id": str(msg.id), "channel_id": channel_id}
                except asyncio.TimeoutError:
                    result = {"ok": False, "error": "send timeout"}
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, code=400)
                return
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            self._send_json(result)
            return

        self._send_json({"ok": False, "error": "not found"}, code=404)

    def log_message(self, fmt, *args):
        return


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set in .env")

    load_twitch_chat_auth_state()
    load_nexus_notify_state()
    load_social_notify_state(SOCIAL_NOTIFY_STATE_FILE, social_notify_lock, social_notify_state)
    load_social_notify_state(COMMENTS_NOTIFY_STATE_FILE, comments_notify_lock, comments_notify_state)
    load_social_notify_state(PROFILE_NOTIFY_STATE_FILE, profile_notify_lock, profile_notify_state)
    load_social_notify_state(TWITCH_NOTIFY_STATE_FILE, twitch_notify_lock, twitch_notify_state)
    load_social_notify_state(TWITTER_NOTIFY_STATE_FILE, twitter_notify_lock, twitter_notify_state)
    load_social_notify_state(YOUTUBE_NOTIFY_STATE_FILE, youtube_notify_lock, youtube_notify_state)
    load_social_notify_state(YOUTUBE_COMMENTS_NOTIFY_STATE_FILE, youtube_comments_notify_lock, youtube_comments_notify_state)
    load_social_notify_state(YOUTUBE_LIVECHAT_STATE_FILE, youtube_livechat_notify_lock, youtube_livechat_notify_state)
    load_social_notify_state(PAGE_PROMO_STATE_FILE, page_promo_lock, page_promo_state)
    load_discord_status_metrics_state()
    if NEXUS_MEDIA_INIT_TAGS_ON_START and DISCORD_NEXUS_MEDIA_CHANNEL_ID:
        try:
            tag_init = initialize_nexus_media_tags()
            print("Nexus media tags initialized: {}".format(json.dumps(tag_init, ensure_ascii=False)))
        except Exception as exc:
            print("Nexus media tag init error: {}".format(exc))
    if TWITCH_MEDIA_INIT_TAGS_ON_START and DISCORD_TWITCH_MEDIA_CHANNEL_ID:
        try:
            tag_init = initialize_twitch_media_tags()
            print("Twitch media tags initialized: {}".format(json.dumps(tag_init, ensure_ascii=False)))
        except Exception as exc:
            print("Twitch media tag init error: {}".format(exc))
    if TWITTER_MEDIA_INIT_TAGS_ON_START and DISCORD_TWITTER_MEDIA_CHANNEL_ID:
        try:
            tag_init = initialize_twitter_media_tags()
            print("Twitter media tags initialized: {}".format(json.dumps(tag_init, ensure_ascii=False)))
        except Exception as exc:
            print("Twitter media tag init error: {}".format(exc))
    if YOUTUBE_MEDIA_INIT_TAGS_ON_START and DISCORD_YOUTUBE_MEDIA_CHANNEL_ID:
        try:
            tag_init = initialize_youtube_media_tags()
            print("YouTube media tags initialized: {}".format(json.dumps(tag_init, ensure_ascii=False)))
        except Exception as exc:
            print("YouTube media tag init error: {}".format(exc))
    get_nexus_watcher()
    get_twitch_watcher()
    get_twitch_chat_bridge()
    get_twitter_watcher()

    t = threading.Thread(target=poller_loop)
    t.daemon = True
    t.start()

    # Discord上でオンライン表示を維持するためGateway接続を開始
    start_gateway_client()
    start_twitch_chat_bridge()

    server = ThreadingHTTPServer((API_HOST, API_PORT), Handler)
    print("Web API started: http://{}:{}".format(API_HOST, API_PORT))
    server.serve_forever()


if __name__ == "__main__":
    main()
