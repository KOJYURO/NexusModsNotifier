# 7DTD Nexus Browser

7DAYSTODIE.JP 向けの WordPress plugin です。Nexus Mods API を利用して 7 Days to Die の MOD 情報を取得し、Web 表示と通知用データを提供します。

## 役割

- Nexus Mods API へ直接アクセスするコンポーネントです。
- Web サイト側の MOD 一覧、カテゴリ情報、watch-updates 用データ生成を担当します。
- Discord 通知そのものは別コンポーネントの WordPress bot が担当し、この plugin が返す WordPress endpoint を購読します。

## 現在の公開スナップショット

- 現在は Nexus Mods からの正式な API 利用許可待ちのため、API 経由の情報収集は一時停止中です。
- そのため、この公開スナップショットは「実装構造と責務の説明」を主目的とし、常時収集を有効化した状態では公開していません。
- API キーは WordPress 設定値としてサーバー側で保持し、リポジトリへは含めません。

## 主な実装ポイント

- `sevendtd-nexus-browser.php`: plugin bootstrap
- `includes/plugin.php`: Nexus API 呼び出し、カテゴリ取得、watch-updates 生成、REST route 登録
- 既定の API Base: `https://api.nexusmods.com/v1`
- アプリ識別ヘッダー: `Application-Name`, `Application-Version`, `User-Agent`

## Related Component

- Discord 投稿側は別の WordPress bot リポジトリが担当します。
- その bot は Nexus Mods API を直接呼ばず、この plugin が返す `watch-updates` endpoint を利用します。

## English Summary For Nexus Review

- This plugin is the Nexus Mods API-facing component for 7DAYSTODIE.JP.
- It is responsible for fetching Nexus data, preparing category data, and exposing WordPress-side endpoints used by the Discord delivery bot.
- The current public snapshot keeps Nexus API collection disabled while official API usage approval is pending.
- API keys are kept in server-side WordPress settings and are not committed to version control.
- The Discord bot is a separate component and consumes the WordPress `watch-updates` output instead of calling the Nexus Mods API directly.