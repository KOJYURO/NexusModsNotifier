# Discord Bridge API

Discord のスレッド一覧と告知メッセージを取得し、Web側が参照できる JSON API を提供します。
Python 標準ライブラリのみで動作するため追加依存は不要です。

## VPS への配置先

- この VPS の常駐パス: `/root/DiscordBot/WordPress`
- パッケージ配布時の例: `/opt/discordbot`
- 公開方法: リバースプロキシ経由で `https://bot.7daystodie.jp`

## セットアップ

1. アーカイブを VPS に配置して展開
2. `.env.example` を `.env` にコピーして値を設定
3. `python3 main.py` で単体起動確認
4. `/root/DiscordBot/deploy/systemd/wordpress-discordbot.service` を systemd に配置
5. `systemctl enable --now wordpress-discordbot.service` で常駐化

重複 unit によるポート競合を避けるため、この VPS では `wordpress-discordbot.service` のみを使用します。

## 公開リポジトリ向けメモ

- `.env`、`*_state.json`、`.pid`、`.log` は運用時に生成されるため、公開リポジトリには含めません。
- この bot の Nexus 通知は `WP_NEXUS_WATCH_ENDPOINT` 経由で WordPress 側の `watch-updates` を取得して Discord へ配送します。
- Nexus Mods API への直接アクセス、アプリ名、API キー管理は 7daystodie.jp 側の `sevendtd-nexus-browser` plugin が担当します。
- Nexus 側へ審査用ソースを提示する場合は、この bot リポジトリだけでなく、Nexus API を直接扱う plugin 実装も合わせて提示する前提です。

### English Summary For Nexus Review

- This Discord bot is a delivery component for 7DAYSTODIE.JP and posts curated Nexus update notifications to Discord.
- The bot does not call the Nexus Mods API directly. It consumes the internal WordPress `watch-updates` endpoint configured by `WP_NEXUS_WATCH_ENDPOINT`.
- Direct Nexus Mods API access, application naming, and server-side API key handling are implemented in the companion WordPress plugin `sevendtd-nexus-browser`.
- Runtime secrets and generated files such as `.env`, `*_state.json`, `.pid`, and `.log` are intentionally excluded from version control.

## 必要な環境変数

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `DISCORD_THREAD_CHANNEL_ID`（WordPress のプロフィールカード thread 親 forum / channel）
- `DISCORD_ANNOUNCEMENT_CHANNEL_ID`
- `API_HOST`
- `API_PORT`
- `BOT_API_SHARED_KEY`
- `BOT_PUBLIC_BASE_URL`（Twitch chat OAuth を使う場合）
- `EVENT_LEADERBOARD_DB_PATH`（任意。既定: `/root/DiscordBot/7DJPGameManager/runtime/game_manager.db`）

WordPress 連携（Bot -> WordPress）を使う場合は以下も設定します。

- `WP_BRIDGE_ENDPOINT`
- `WP_BRIDGE_BEARER_TOKEN`
- `WP_BRIDGE_HMAC_SECRET`
- `WP_BRIDGE_TIMEOUT`
- `WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER`（既定: `1`）
- `WP_BRIDGE_DEBUG`（既定: `0`）

## Discord Bot 必要権限

- View Channel
- Read Message History

## Slash Command 同期

`DISCORD_GUILD_ID` を設定している運用では、slash command はその guild 専用で登録します。
起動時には global command を空同期して、以前の bot を使い回した際に残った実装外コマンドを削除します。

## 手動 Embed 再投稿

管理者は `/repost_messages` で、任意 channel のメッセージを 1 メッセージずつ embed 化して再投稿できます。

- `source_channel` 未指定時は、コマンドを実行した現在の channel / thread を転載元として扱います。
- `post_channel` 未指定時は、コマンドを実行した現在の channel / thread を投稿先として扱います。
- `limit` は 1 から 20 件までです。Discord REST の 429 回避のため、小さめ batch を前提にしています。
- `before_message_id` / `after_message_id` を指定すると、対象範囲を絞って再投稿できます。
- 投稿された embed には `管理者投稿編集` ボタンが付きます。管理者は後からタイトル・本文・画像 URL を修正でき、元の添付画像 URL をそのまま使えない場合でも画像を追加・削除できます。
- 旧投稿に残っている `画像編集` ボタンを押した場合も、内部的に `管理者投稿編集` へ自動移行して同じモーダルでタイトル・本文・画像 URL を編集できます。

## API

- `GET /health`
- `GET /threads/active`
- `GET /announcements/latest?limit=20`
- `GET /events/leaderboard?limit=10&guild_id=<discord_guild_id>`
- `GET /nexus/watch/latest`
- `GET /social/watch/latest`
- `GET /twitch/vrc/playlist?limit=20`
- `GET /twitch/chat/recent?limit=20`
- `GET /youtube/comments/watch/latest`
- `GET /youtube/comments/recent?limit=20`
- `GET /youtube/livechat/watch/latest`
- `GET /youtube/livechat/recent?limit=20`
- `GET /oauth/twitch/callback`
- `GET /comments/watch/latest`
- `POST /profile/card/sync`
- `POST /bridge/nexus/sync`
- `POST /bridge/nexus/rebucket`
- `POST /bridge/nexus/retag`
- `POST /bridge/social/sync`
- `POST /bridge/comments/sync`
- `POST /bridge/twitch/sync`
- `POST /bridge/twitter/sync`
- `POST /bridge/youtube/sync`

`/health` 以外は、`BOT_API_SHARED_KEY` を設定した場合 `X-Api-Key` ヘッダーが必要です。

`POST /profile/card/sync` は `DISCORD_THREAD_CHANNEL_ID` 配下にユーザー名 thread を作成または更新し、starter message をプロフィールカードに同期します。

`GET /health` は以下を返します。

- `gateway`: Gateway の接続状態（connected/ready/user/error）
- `runtime_check`: 実ランタイム状態（`client_valid`/`loop_valid`/`runtime_ok`）
- `generated_at`: health 応答生成時刻（UTC）
- `process.pid`: 応答を返した Bot プロセス PID

また、API 応答には `Cache-Control: no-store` が付与されるため、監視時のキャッシュ由来の状態ズレを抑制します。

`GET /oauth/twitch/callback` は Twitch OAuth の redirect 専用です。`X-Api-Key` は不要ですが、Twitch Developer Console 側で `BOT_PUBLIC_BASE_URL + /oauth/twitch/callback` を Redirect URL として事前登録しておく必要があります。

## Nexus 通知連携

Nexus 通知は watcher 構成で動作し、優先順は次の通りです。

1. `WP_NEXUS_WATCH_ENDPOINT` が利用できる場合は、WordPress の `watch-updates` API を使用
2. 上記 API が失敗した場合のみ、`WP_NEXUS_FALLBACK_POSTS_ENDPOINT` の WordPress 投稿一覧を fallback として使用
3. `DISCORD_NEXUS_MEDIA_CHANNEL_ID` が設定されている場合は、通知先をその media channel 配下の `DISCORD_NEXUS_NOTIFY_THREAD_NAME` thread へ切り替え

`watch-updates` は `nexus-mod-search-3` の既定 feed 取得ロジックと共通 helper を使い、Web 側で表示している既定 feed をそのまま通知候補として返します。必要に応じて API URL 側へ `source=latest_updated|latest_added|trending` を付与できます。

`WP_NEXUS_CATEGORIES_ENDPOINT` が設定されている場合は、起動時に既知の MOD カテゴリ一覧を取得し、media channel のタグを先に初期化します。categories API が空の場合は `watch-updates` の表示カテゴリから補完します。Discord 側のタグ上限は 20 件のため、既存タグと合わせて上限を超える分は作成されません。`watch-updates` では WordPress 側で `category_id`、既知カテゴリ名、title/summary のキーワードから `category` と `tags_ja` を補完します。さらに `summary` は日本語本文を優先して返し、DeepL API キー設定時は英語概要を日本語化します。翻訳できない場合も、日本語メタ情報と原文概要を合わせて返します。Bot 側では `tags_ja` が空の item や既存 embed に対して、title/description の既知キーワードから暫定分類を行い、Nexus embed の説明欄も従来より長めに表示します。

ローカル vhost 経由で WordPress を参照する環境では、`WP_NEXUS_WATCH_ENDPOINT` / `WP_NEXUS_CATEGORIES_ENDPOINT` / `WP_NEXUS_FALLBACK_POSTS_ENDPOINT` に `http://127.0.0.1/...` を設定できます。この場合、Bot は site host を `Host` header に自動付与して WordPress route へ到達します。

media channel モードでは、新着通知は 1 本の通知 thread に集約して投稿され、同時に MOD 作成者名 thread にも自動投稿されます。通知メッセージには `お気に入り / Favorite` ボタンが付き、押下すると対象作成者 thread に `FAVORITE_MEDIA_TAG_NAME` tag を付与します。作成者 thread には starter message の `Tags` と `Category` から解決した投稿タグを最大 4 件まで適用し、通知 thread は `DISCORD_NEXUS_NOTIFY_TAG_NAME` を使用します。これにより、スレッド名は作成者単位のまま、スレッド tag は実際の投稿内容ベースで追従します。通知 thread と作成者 thread は、新着投稿時に starter message を最新 payload へ更新するため、media channel の表紙も最新に追従します。作成者情報が取得できない fallback 投稿のみ、thread 名はカテゴリへフォールバックします。

設定項目は以下です。

- `DISCORD_NEXUS_NOTIFY_CHANNEL_ID`
- `DISCORD_NEXUS_MEDIA_CHANNEL_ID`
- `DISCORD_NEXUS_NOTIFY_THREAD_NAME`
- `DISCORD_NEXUS_NOTIFY_TAG_NAME`
- `FAVORITE_MEDIA_TAG_NAME`
- `WP_NEXUS_CATEGORIES_ENDPOINT`
- `NEXUS_NOTIFY_POLL_SECONDS`
- `NEXUS_NOTIFY_STATE_FILE`
- `NEXUS_NOTIFY_PRIME_ON_START`
- `NEXUS_MEDIA_INIT_TAGS_ON_START`
- `WP_NEXUS_WATCH_ENDPOINT`
- `WP_NEXUS_WATCH_TOKEN`
- `WP_NEXUS_FALLBACK_ENABLED`
- `WP_NEXUS_FALLBACK_POSTS_ENDPOINT`
- `WP_NEXUS_FALLBACK_CATEGORY_IDS`
- `WP_NEXUS_FALLBACK_MAX_AGE_HOURS`

状態確認は `GET /nexus/watch/latest`、手動実行は `POST /bridge/nexus/sync` で行えます。手動実行時は JSON body に `limit` と `backfill_days` を渡せます。例: `{"limit":100,"backfill_days":7}`。`backfill_days` 指定時は既読 state を無視して、その期間内にある取得済み item を再投稿します。

既存の Discord 通知 message を通知 thread から作成者 thread へだけ再振り分けしたい場合は、`POST /bridge/nexus/rebucket` を使えます。こちらは通知 thread へ再投稿せず、既存 message の embed と component をそのまま使って作成者 thread へコピーします。JSON body では `limit`、`before_message_id`、`source_channel_id`、`force` を受け取ります。通常は `{"limit":100}` を繰り返し実行し、応答の `next_before_message_id` を次回の `before_message_id` へ渡して過去 message まで遡ります。既定 source は `DISCORD_NEXUS_NOTIFY_THREAD_NAME` の通知 thread ですが、過去に通常 channel へ直接投稿していた期間がある場合は `source_channel_id` で元 channel / thread を指定できます。処理済み message ID は state に保存されるため、同じ batch の再実行時は既定で二重投入を避けます。`force=true` を付けた場合のみ処理済み判定を無視します。

既存の creator thread の tag だけを現在の starter message に合わせて再同期したい場合は、`POST /bridge/nexus/retag` を使えます。こちらは message を増やさず、既存 thread の tag のみを更新します。JSON body では `limit` を受け取り、既定は 200 thread です。通知 thread と旧カテゴリ thread は自動で対象外になります。

## Social Watch 連携（Web側フィルタ済み通知）

Webサイト側でフィルタ済みの動画・配信候補を定期通知する場合は次を設定します。

- `DISCORD_SOCIAL_NOTIFY_CHANNEL_ID`
- `WP_SOCIAL_WATCH_ENDPOINT`
- `WP_SOCIAL_WATCH_TOKEN`
- `SOCIAL_NOTIFY_POLL_SECONDS`
- `SOCIAL_NOTIFY_STATE_FILE`

この構成では Bot 側が Web 側 endpoint を優先利用し、利用できない場合のみ各サービス API への直接取得へフォールバックします。
状態確認は `GET /social/watch/latest`、手動実行は `POST /bridge/social/sync` で行えます。

## Twitch 通知連携

Twitch 通知は watcher 構成で動作し、優先順は次の通りです。

1. `WP_TWITCH_WATCH_ENDPOINT` が設定されている場合は、WordPress の `twitch-updates` API を使用
2. `WP_TWITCH_WATCH_ENDPOINT` が未設定でも `WP_SOCIAL_WATCH_ENDPOINT` に `watch-updates` が含まれる場合は、自動的に `twitch-updates` へ変換して使用
3. どちらも使えない場合のみ、従来どおり Twitch Helix API を直接検索

ローカル vhost 経由で WordPress を参照する環境では、`WP_TWITCH_WATCH_ENDPOINT` に `http://127.0.0.1/...` を設定できます。この場合、Bot は site host を `Host` header に自動付与して WordPress route へ到達します。

`DISCORD_TWITCH_MEDIA_CHANNEL_ID` が設定されている場合は、Twitch 通知を media channel 配下の `DISCORD_TWITCH_NOTIFY_THREAD_NAME` thread へ集約し、同時に creator 名 thread にも自動投稿します。Twitch 側では forum tag 上限対策として、投稿時の forum tag 自動生成・自動付与は行いません。通知メッセージには `お気に入り / Favorite` ボタンが付き、押下すると対象 creator thread に共有の `FAVORITE_MEDIA_TAG_NAME` tag のみを付与します。creator 名は `member_display_name` を優先し、未連携時は `Streamer` を使用します。notification thread と creator thread は新着投稿時に starter message を最新 payload へ更新するため、media channel の表紙も最新に追従します。

設定項目は以下です。

- `TWITCH_NOTIFY_ENABLED`
- `TWITCH_NOTIFY_CHANNEL_ID`
- `DISCORD_TWITCH_MEDIA_CHANNEL_ID`
- `DISCORD_TWITCH_NOTIFY_THREAD_NAME`
- `FAVORITE_MEDIA_TAG_NAME`
- `TWITCH_NOTIFY_POLL_SECONDS`
- `TWITCH_NOTIFY_STATE_FILE`
- `TWITCH_NOTIFY_PRIME_ON_START`
- `TWITCH_NOTIFY_FETCH_LIMIT`
- `WP_TWITCH_WATCH_ENDPOINT`（任意）
- `WP_TWITCH_WATCH_TOKEN`（任意。未設定時は `WP_SOCIAL_WATCH_TOKEN` を流用）

`DISCORD_TWITCH_NOTIFY_TAG_NAME` と `TWITCH_MEDIA_INIT_TAGS_ON_START` は後方互換のため設定値読み込みは残っていますが、現在の Twitch media 投稿では forum tag 自動生成に使用しません。

WordPress 側の `twitch-updates` API が利用できない場合のフォールバック用に、従来の直接検索設定も残せます。

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`
- `TWITCH_NOTIFY_USER_LOGINS`

状態確認は `GET /social/watch/latest` の `twitch` フィールド、手動実行は `POST /bridge/twitch/sync` で行えます。手動実行時は JSON body に `limit` と `backfill_days` を渡せます。例: `{"limit":100,"backfill_days":7}`。`backfill_days` 指定時は既読 state を無視して、その期間内にある取得済み item を再投稿します。Twitch 側ソースが返す件数上限を超える過去分は取得できません。

VRC 向けの静的ミラー生成元として `GET /twitch/vrc/playlist?limit=20` も追加しています。返却 JSON には `title` `url` `video_url` `thumbnail_url` `user_name` `game_name` `broadcast_state` `timestamp` が入り、WordPress bot 側で正規化済みの Twitch 一覧をそのまま GitHub Pages へ書き出せます。`/health` 以外の通常 API と同じく `X-Api-Key` が必要です。

GitHub Pages 側の JSON 更新には [deploy/export_twitch_vrc_playlist.py](deploy/export_twitch_vrc_playlist.py) を使えます。例:

```bash
cd /root/DiscordBot/WordPress
./.venv/bin/python deploy/export_twitch_vrc_playlist.py \
	--output /path/to/VRC-Integration/docs/twitch_playlist.json \
	--git-repo /path/to/VRC-Integration \
	--push
```

このスクリプトは `.env` から `API_PORT` と `BOT_API_SHARED_KEY` を読み、既定では `http://127.0.0.1:${API_PORT}/twitch/vrc/playlist` を取得します。`--endpoint` を渡せば別 URL へ切り替えられます。`--git-repo` か `--public-base-url` を与えると、同じ公開ディレクトリへ `twitch_thumb_00.jpg` から `twitch_thumb_23.jpg` までの固定名サムネも書き出し、JSON の `thumbnail_url` と `image_url` は GitHub Pages 側の trusted URL に差し替えられます。

Community Server Hub を VRC へ出す場合は、site 側の公開 endpoint `https://7daystodie.jp/wp-json/sevendtd/v1/server-hub/vrc?limit=8` を使います。返却 JSON には `community_discord.summary`、`community_discord.invite_url`、`items[].title`、`items[].subtitle`、`items[].description`、`items[].content`、`items[].comment_preview`、`items[].invite_url`、`items[].website_url`、`items[].board_url` が入り、VRChat 側はこの feed をそのまま trusted static mirror から読めます。member-only の接続情報やパスワードは含みません。

GitHub Pages 側の JSON 更新には [deploy/export_server_hub_vrc_feed.py](deploy/export_server_hub_vrc_feed.py) を使えます。例:

```bash
cd /root/DiscordBot/WordPress
python3 deploy/export_server_hub_vrc_feed.py \
	--output /path/to/VRC-Integration/docs/server_hub_vrc_feed.json \
	--git-repo /path/to/VRC-Integration \
	--push
```

既定では公開 endpoint を取得します。ローカル vhost へ向けたい場合は `--endpoint http://127.0.0.1/wp-json/sevendtd/v1/server-hub/vrc --host-header 7daystodie.jp` のように渡せます。

VRChat では `VRCUrl` を runtime 生成できないため、feed 内の招待 URL をそのまま world からクリック遷移させる設計はできません。`ServerHubVrcBoard` は URL を表示し、固定導線や別端末側で扱う前提です。

Twitch の thread card サムネは、starter message の最新 embed image が表示元になります。ただし Twitch 側が archive thumbnail として processing placeholder しか返さない場合は有効な画像が無いため、その投稿ではサムネ表示を保証できません。

## Twitch Chat Relay / Slash Commands

Twitch chat の Discord 片方向 relay は、IRC ではなく Twitch 公式の EventSub WebSocket と Send Chat Message API を使います。WordPress bot 側では次の slash command を追加しています。

- `/notify mode:twitch`
- `/notify mode:profile`
- `/twitch mode:v2.6コマンド`

`/notify mode:twitch` は relay 状態、現在の Twitch 認証状態、OAuth URL、保持方針を表示します。このコマンドは Twitch chat 認可 owner の Discord ユーザー、または owner 未確定時の Discord 管理者のみ使用できます。`operation` では `status`、`status_detail`、`reconnect`、`disconnect`、`clear_auth` を選べます。`status_detail` は EventSub session / 購読 streamer 一覧 / sender identity / creator thread routing / game filter 設定まで表示し、`clear_auth` は保存済み OAuth cache を削除します。

`/notify mode:profile` は Discord 管理者向けの VC 入室プロフィール通知設定です。`operation:set` で監視対象の VC を `voice_channel` に指定し、`post_channel` を省略した場合は現在コマンドを実行した text channel を投稿先として保存します。指定 VC に入室したメンバーが WordPress 側の中央プロフィールと連携済みであれば、Bot はプロフィール Embed を投稿し、Discord プロフィール、専用スレッド、連携アカウント、招待サーバーへのリンクをボタンで表示します。`operation` では `status`、`set`、`clear`、`test` を使用できます。`test` はコマンド実行者自身のプロフィールで 1 回テスト投稿します。

`/twitch mode:v2.6コマンド` は `TWITCH_CHAT_XML_PATH` の `twitch.xml` を解析し、action 一覧の表示、個別 action の詳細表示、`execute=true` 指定時の Twitch chat 実行を行います。`execute=true` は Discord 管理者のみ許可されます。一覧は 12 件単位の page 表示で、Prev / Next と select UI から詳細へ進めます。詳細画面には管理者向け実行ボタンも付きます。

action 詳細では事前判定を 3 段階で表示します。

- `実行可能 / Ready`: Discord から送信可能
- `ゲーム側条件待ち / Waiting`: game stage / special requirement / cooldown など、Discord 側では確定できない条件あり
- `非対応 / Unsupported`: Bits 専用、未対応 permission、Broadcaster 不一致など Discord 側から送信不可

`execute=true` と詳細画面の実行ボタンは、この事前判定が `実行可能 / Ready` の action に限定して許可します。`ゲーム側条件待ち / Waiting` は誤送信防止のため Discord 側で block します。

必要な設定は次の通りです。

- `TWITCH_CHAT_ENABLED`
- `TWITCH_CHAT_DISCORD_CHANNEL_ID`（未設定時は `TWITCH_NOTIFY_CHANNEL_ID` を流用）
- `TWITCH_CHAT_OWNER_DISCORD_USER_ID`（任意。設定時はこの Discord user id のみが OAuth を開始・更新できます）
- `TWITCH_CHAT_BROADCASTER_LOGIN` または `TWITCH_CHAT_BROADCASTER_USER_ID`（未設定時は OAuth 認可した Twitch ユーザー本人を配信元として扱います）
- `TWITCH_CHAT_BROADCASTER_LOGINS`（任意。chat relay の受信対象 streamer login 一覧。既定は `TWITCH_NOTIFY_USER_LOGINS`）
- `TWITCH_CHAT_XML_PATH`（既定: `/home/steam/7dtd/Data/Config/twitch.xml`）
- `TWITCH_CHAT_AUTH_STATE_FILE`
- `TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS`
- `TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS`（既定: `DISCORD_TWITCH_MEDIA_CHANNEL_ID` 設定時に有効）
- `TWITCH_CHAT_ALLOWED_GAME_NAMES`（任意。CSV）

`TWITCH_CHAT_OWNER_DISCORD_USER_ID` が未設定の場合は、最初に成功した OAuth の Discord user id と Twitch user id を bot が保存し、その組み合わせを以後の正本として固定します。つまり、初回認可後は別の Discord ユーザーや別の Twitch アカウントで上書きできません。

`TWITCH_CHAT_BROADCASTER_LOGIN` または `TWITCH_CHAT_BROADCASTER_USER_ID` を設定した場合、OAuth で許可する Twitch アカウントもその ID / login と一致している必要があります。`私の Twitch ID で固定したい` 場合は、この 2 項目のどちらかを入れておくと明示固定できます。

OAuth 認可を slash command から始める場合、`/notify mode:twitch` が表示する URL をブラウザで開き、Twitch で許可します。必要 scope は次の 2 つだけです。

- `user:read:chat`
- `user:write:chat`

Twitch Developer Console 側には、次の redirect URL を登録してください。

- `${BOT_PUBLIC_BASE_URL}/oauth/twitch/callback`

Discord 側の relay メッセージは Twitch ソース URL を必ず併記し、既定では `TWITCH_CHAT_RELAY_DELETE_AFTER_SECONDS=3600` により自動削除されます。これは Twitch chat 内容を Discord 側に長期保存しないための最小保持方針です。あわせて EventSub の `channel.chat.message_delete`、`channel.chat.clear_user_messages`、`channel.chat.clear` を購読し、Twitch 側で削除・一括削除・ユーザー単位削除が発生した時は Discord 側の直近 relay も追従削除します。

chat relay の Source URL は Discord の自動 embed preview を避けるため、`<https://...>` 形式で表示します。リンク自体はクリック可能ですが、毎回 Twitch card は展開されません。

`TWITCH_CHAT_BROADCASTER_LOGINS` を設定した場合、chat relay の受信購読はその login 群を対象に行います。未設定時は `TWITCH_NOTIFY_USER_LOGINS`、さらに未設定時は `TWITCH_CHAT_BROADCASTER_LOGIN` を fallback として使用します。加えて、現在の実装では WordPress 側 `twitch-updates` が返す最新 item に含まれる streamer login も購読対象へ補完します。これにより、今 live の streamer で chat relay を試しやすくしています。

`DISCORD_TWITCH_MEDIA_CHANNEL_ID` が設定され、かつ `TWITCH_CHAT_ROUTE_TO_CREATOR_THREADS=1` の場合、chat relay は固定 channel ではなく Twitch 通知と同じ creator thread へ投稿します。thread 名は `member_display_name` を優先し、取得できない場合は `user_name` / `user_login` を使用します。既存 thread が見つからない場合のみ thread を自動作成します。

`TWITCH_CHAT_ALLOWED_GAME_NAMES` に CSV でゲーム名を設定すると、chat relay はその game_name に一致する streamer のみ中継します。空のままなら game filter は無効で、購読対象 streamer の chat をそのまま中継します。

WordPress 側 `twitch-updates` の item に `game_name` が入らない場合でも、chat relay 側は Helix live stream 情報で `game_name` を補完します。これにより `TWITCH_CHAT_ALLOWED_GAME_NAMES` を使った game filter を live 配信へ適用できます。

削除追従は bot が保持している直近 relay 対応表に対してのみ有効です。通常運用では自動削除時間内のメッセージが対象になり、古い relay や既に Discord 側で消えている message は `missing` として同期だけ完了します。

WordPress 側の Web 表示用に、Bot は `GET /twitch/chat/recent` も公開します。ここでは削除追従後の recent live chat だけを返し、共有鍵付きの read-only API として利用します。Twitch の comment 本文を公式 API 準拠で継続取得する stable endpoint は現状使っていないため、Web 側へ広げる対象も Twitch live chat のみです。

利用規約面では、次の前提で実装しています。

- 受信は EventSub `channel.chat.message` と `channel.chat.notification`
- 削除追従は EventSub `channel.chat.message_delete` `channel.chat.clear_user_messages` `channel.chat.clear`
- 送信は Helix `Send Chat Message`
- 要求 scope は chat 読み書きの最小 2 つのみ
- Discord 側表示には Twitch ソース URL を付与
- 永続保持は access token cache と直近状態のみ。chat 本文は長期保存しない設計

注意点として、Discord channel 自体が恒久アーカイブになっている運用は Twitch コンテンツ再配布の観点でリスクがあります。既定の自動削除を無効にする場合は、保持期間と公開範囲を運用側で必ず見直してください。

## Twitter/X 通知連携

Twitter/X 通知は WordPress の `twitter-updates` API を定期取得し、`DISCORD_TWITTER_MEDIA_CHANNEL_ID` が設定されている場合は media channel 配下の `DISCORD_TWITTER_NOTIFY_THREAD_NAME` thread へ集約し、同時に creator 名 thread にも自動投稿します。Twitter/X 側でも forum tag 上限対策として、投稿時の forum tag 自動生成・自動付与は行いません。通知メッセージには `お気に入り / Favorite` ボタンが付き、押下すると対象 creator thread に共有の `FAVORITE_MEDIA_TAG_NAME` tag のみを付与します。creator 名は `member_display_name` を優先し、未連携時は投稿者名または `@username` を使用します。starter embed では、投稿添付画像がある場合は embed image に使い、リンク先 preview thumbnail がある場合は embed thumbnail に使います。

取得間隔は既定で 24 時間です（`TWITTER_NOTIFY_POLL_SECONDS=86400`）。WordPress の 7DTD Social Watch API 設定画面にある `Twitter/X 取得間隔（分）` が設定されている場合でも、bot 側では `TWITTER_NOTIFY_POLL_SECONDS` を下限として適用します。つまり、WordPress 側がより短い間隔を返しても bot は短縮しません。

ローカル vhost 経由で WordPress を参照する環境では、`WP_TWITTER_WATCH_ENDPOINT` に `http://127.0.0.1/...` を設定できます。この場合、Bot は site host を `Host` header に自動付与して WordPress route へ到達します。

設定項目は以下です。

- `TWITTER_NOTIFY_ENABLED`
- `TWITTER_NOTIFY_CHANNEL_ID`
- `DISCORD_TWITTER_MEDIA_CHANNEL_ID`
- `DISCORD_TWITTER_NOTIFY_THREAD_NAME`
- `FAVORITE_MEDIA_TAG_NAME`
- `TWITTER_NOTIFY_POLL_SECONDS`（下限。既定 86400 秒）
- `TWITTER_NOTIFY_STATE_FILE`
- `TWITTER_NOTIFY_PRIME_ON_START`
- `TWITTER_NOTIFY_FETCH_LIMIT`
- `WP_TWITTER_WATCH_ENDPOINT`（任意。未設定時は `WP_SOCIAL_WATCH_ENDPOINT` から自動変換）
- `WP_TWITTER_WATCH_TOKEN`（任意。未設定時は `WP_SOCIAL_WATCH_TOKEN` を流用）

`DISCORD_TWITTER_NOTIFY_TAG_NAME` と `TWITTER_MEDIA_INIT_TAGS_ON_START` は後方互換のため設定値読み込みは残っていますが、現在の Twitter/X media 投稿では forum tag 自動生成に使用しません。

状態確認は `GET /social/watch/latest` の `twitter` フィールド、手動実行は `POST /bridge/twitter/sync` で行えます。`twitter` state には `poll_interval_seconds` と `poll_interval_source` も入り、現在 bot が採用している取得間隔を確認できます。手動実行時は JSON body に `limit` と `backfill_days` を渡せます。例: `{"limit":100,"backfill_days":7}`。`backfill_days` 指定時は既読 state を無視して、その期間内にある取得済み item を再投稿します。

## コメント通知連携

## YouTube 通知連携

YouTube 通知は次の優先順で取得します。

1. `WP_YOUTUBE_WATCH_ENDPOINT` が設定されている場合は、WordPress の `youtube-updates` API を使用
2. `WP_YOUTUBE_WATCH_ENDPOINT` が未設定でも `WP_SOCIAL_WATCH_ENDPOINT` に `watch-updates` が含まれる場合は、自動的に `youtube-updates` へ変換して使用
3. Web 側 endpoint が利用できない場合のみ、従来どおり YouTube Data API v3 または Atom feed を直接取得

WordPress の `youtube-updates` API は `community/youtube` と同じ条件を返します。通常 poll では `language=ja` / `today_only=1` / `order=date` を使い、WordPress 側の 15 分 cache を尊重するため `force_refresh` は既定で使いません。これにより 7 Days to Die 関連の日本語動画を member 優先順で通知しつつ、YouTube Data API quota の無駄消費を抑えます。手動 backfill 実行時のみ `today_only=0` へ切り替え、既読 state を無視した再送に対応します。

`DISCORD_YOUTUBE_MEDIA_CHANNEL_ID` が設定されている場合は media channel 配下の `DISCORD_YOUTUBE_NOTIFY_THREAD_NAME` thread へ集約し、同時に creator 名 thread にも自動投稿します。YouTube 側では forum tag 上限対策として、投稿時の forum tag 自動生成・自動付与は行いません。通知メッセージには `お気に入り / Favorite` ボタンが付き、押下すると対象 creator thread に共有の `FAVORITE_MEDIA_TAG_NAME` tag のみを付与します。creator 名は動画 channel 名を使用します。notification thread と creator thread は新着投稿時に starter message を最新 payload へ更新するため、media channel の表紙も最新に追従します。

2026-04-20 時点では、YouTube Atom feed が Python / curl の両方で 404 になる時間帯がありました。このため direct fallback では `YOUTUBE_NOTIFY_API_KEY` が設定されている場合は YouTube Data API v3 を優先使用し、未設定時のみ従来の Atom feed を curl 優先でフォールバックします。

設定項目は以下です。

- `YOUTUBE_NOTIFY_ENABLED`
- `WP_YOUTUBE_WATCH_ENDPOINT`（任意。未設定時は `WP_SOCIAL_WATCH_ENDPOINT` から自動変換）
- `WP_YOUTUBE_WATCH_TOKEN`（任意。未設定時は `WP_SOCIAL_WATCH_TOKEN` を流用）
- `YOUTUBE_NOTIFY_CHANNEL_ID`
- `DISCORD_YOUTUBE_MEDIA_CHANNEL_ID`
- `DISCORD_YOUTUBE_NOTIFY_THREAD_NAME`
- `FAVORITE_MEDIA_TAG_NAME`
- `YOUTUBE_NOTIFY_POLL_SECONDS`
- `YOUTUBE_NOTIFY_STATE_FILE`
- `YOUTUBE_NOTIFY_PRIME_ON_START`

WordPress 側 endpoint が利用できない場合の direct fallback 用に、従来設定も残せます。

- `YOUTUBE_NOTIFY_CHANNEL_IDS`
- `YOUTUBE_NOTIFY_API_KEY`

`DISCORD_YOUTUBE_NOTIFY_TAG_NAME` と `YOUTUBE_MEDIA_INIT_TAGS_ON_START` は後方互換のため設定値読み込みは残っていますが、現在の YouTube media 投稿では forum tag 自動生成に使用しません。

状態確認は `GET /social/watch/latest` の `youtube` フィールド、手動実行は `POST /bridge/youtube/sync` で行えます。手動実行時は JSON body に `limit` と `backfill_days` を渡せます。例: `{"limit":100,"backfill_days":7}`。`backfill_days` 指定時は既読 state を無視して、その期間内にある取得済み item を再投稿します。必要な場合のみ `force_refresh=1` を付けると WordPress 側 cache を無視して最新取得を試みます。`WP_YOUTUBE_WATCH_ENDPOINT` が設定されている環境では、quota 保護のため direct fallback は既定で無効です。どうしても direct fetch を試す場合だけ `allow_direct_fallback=1` を明示指定します。`youtube.last_source` で現在採用中の取得元を確認できます。

### YouTube 動画コメント通知

YouTube 動画コメント通知は WordPress の `youtube-updates` route とは分離し、Bot が YouTube Data API v3 を直接参照します。`YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS` に設定した channel ID ごとに uploads playlist を引き、最新動画群へ `commentThreads.list` を当てます。`search.list` は使わないため、recent video 発見コストは `channels.list + playlistItems.list` に抑えています。

`DISCORD_YOUTUBE_MEDIA_CHANNEL_ID` が設定されている場合は media channel 配下の `DISCORD_YOUTUBE_COMMENTS_NOTIFY_THREAD_NAME` thread に集約し、同時に creator 名 thread にも自動投稿します。creator thread 側のお気に入りタグ運用は通常の YouTube 動画通知と同じです。初回起動時は既存コメントを prime して通知スパムを防ぎます。

設定項目は以下です。

- `YOUTUBE_COMMENTS_NOTIFY_ENABLED`
- `YOUTUBE_COMMENTS_NOTIFY_CHANNEL_IDS`
- `YOUTUBE_COMMENTS_NOTIFY_CHANNEL_ID`
- `DISCORD_YOUTUBE_COMMENTS_NOTIFY_THREAD_NAME`
- `YOUTUBE_COMMENTS_NOTIFY_POLL_SECONDS`
- `YOUTUBE_COMMENTS_NOTIFY_STATE_FILE`
- `YOUTUBE_COMMENTS_NOTIFY_PRIME_ON_START`
- `YOUTUBE_COMMENTS_FETCH_LIMIT`
- `YOUTUBE_COMMENTS_VIDEO_LIMIT`
- `YOUTUBE_COMMENTS_PER_VIDEO_LIMIT`

状態確認は `GET /social/watch/latest` の `youtube_comments` または `GET /youtube/comments/watch/latest`、Web 表示用の recent feed 取得は `GET /youtube/comments/recent`、手動実行は `POST /bridge/youtube/comments/sync` です。手動実行時は `limit` と `backfill_days` を渡せます。

### YouTube Live Chat 通知

YouTube live chat 通知も WordPress route を使わず、Bot が `uploads playlist -> videos.list(liveStreamingDetails) -> liveChatMessages.list` の順で直接取得します。active live chat が見つかった stream だけを対象にし、stream ごとの `nextPageToken` を state file に保持して差分だけを継続取得します。新しい live chat が始まった直後は backlog を流さず cursor だけ prime するため、接続タイミングで古い chat がまとめて飛ぶことを防ぎます。

通知先は通常の YouTube media routing を流用し、notification thread 名だけ `DISCORD_YOUTUBE_LIVECHAT_NOTIFY_THREAD_NAME` で分離します。creator thread 側には動画通知・コメント通知と同じ creator 名でまとまります。

設定項目は以下です。

- `YOUTUBE_LIVECHAT_NOTIFY_ENABLED`
- `YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_IDS`
- `YOUTUBE_LIVECHAT_NOTIFY_CHANNEL_ID`
- `DISCORD_YOUTUBE_LIVECHAT_NOTIFY_THREAD_NAME`
- `YOUTUBE_LIVECHAT_POLL_SECONDS`
- `YOUTUBE_LIVECHAT_STATE_FILE`
- `YOUTUBE_LIVECHAT_NOTIFY_PRIME_ON_START`
- `YOUTUBE_LIVECHAT_FETCH_LIMIT`
- `YOUTUBE_LIVECHAT_VIDEO_LIMIT`

状態確認は `GET /social/watch/latest` の `youtube_livechat` または `GET /youtube/livechat/watch/latest`、Web 表示用の recent feed 取得は `GET /youtube/livechat/recent`、手動実行は `POST /bridge/youtube/livechat/sync` です。`limit` と `backfill_days` は指定できますが、live chat は現在進行中の stream に対する最新 page が対象です。

WordPress のコメント更新を Discord に通知する場合は次を設定します。

ローカル vhost 経由で WordPress を参照する環境では、`WP_COMMENTS_WATCH_ENDPOINT` に `http://127.0.0.1/...` を設定できます。この場合も Bot は site host を `Host` header に自動付与します。

- `COMMENTS_NOTIFY_ENABLED`
- `WP_COMMENTS_WATCH_ENDPOINT`
- `WP_COMMENTS_WATCH_TOKEN`
- `DISCORD_COMMENTS_NOTIFY_CHANNEL_ID`
- `COMMENTS_NOTIFY_POLL_SECONDS`
- `COMMENTS_NOTIFY_STATE_FILE`

状態確認は `GET /comments/watch/latest`、手動実行は `POST /bridge/comments/sync` で行えます。

## WordPress 側の設定

WordPress プラグイン設定画面で次を設定します。

- `Discord Bot API Base URL`: `https://bot.7daystodie.jp`
- `Discord Bot API Shared Key`: VPS の `BOT_API_SHARED_KEY`

これにより WordPress は Discord トークンを持たず、VPS 上の Bot API を参照します。

### Bot -> WordPress Bearer 受け渡しの補足

一部のリバースプロキシ環境では `Authorization` ヘッダーが WordPress まで届かないことがあります。
この Bot は既定で次のヘッダーを同時送信します。

- `Authorization: Bearer ...`
- `X-Sevendtd-Bearer: ...`
- `X-Authorization: Bearer ...`（`WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER=1` 時）
- `X-Auth-Token: ...`（`WP_BRIDGE_SEND_FALLBACK_AUTH_HEADER=1` 時）

切り分け時は `WP_BRIDGE_DEBUG=1` を有効化すると、送信ヘッダー名一覧とトークン指紋（先頭12桁）を標準出力に表示します。

## systemd 導入例

```bash
sudo cp /root/DiscordBot/deploy/systemd/wordpress-discordbot.service /etc/systemd/system/wordpress-discordbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now wordpress-discordbot.service
sudo systemctl status wordpress-discordbot.service
```

Current VPS launcher:
- `/root/DiscordBot/deploy/bin/run_wordpress_discordbot.sh`
