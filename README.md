# NexusModsNotifier

7DAYSTODIE.JP の Nexus Mods 通知実装を、Nexus Mods API 利用審査向けに整理した公開リポジトリです。

このリポジトリには 2 つの責務を分けて収録しています。

- `discord-bot/`: WordPress 側の `watch-updates` を受け取り、Discord へ通知する配送コンポーネント
- `wordpress-plugin/`: Nexus Mods API へ直接アクセスし、WordPress 側の表示データと通知用データを生成するコンポーネント

## Why Two Components

7DAYSTODIE.JP の実装では、Discord bot が Nexus Mods API を直接呼びません。
Nexus Mods API への直接アクセスは WordPress plugin 側に集約し、Discord bot 側は WordPress の内部 endpoint を購読して通知だけを担当します。

このため、Nexus Mods API 利用の審査観点では `wordpress-plugin/` が API-facing component であり、`discord-bot/` は delivery component です。

## Repository Layout

- `discord-bot/README.md`: Discord 配送側の説明
- `wordpress-plugin/README.md`: Nexus API 側の説明
- `wordpress-plugin/includes/plugin.php`: Nexus API 呼び出しと watch-updates 生成の本体
- `discord-bot/watchers/nexus_watcher.py`: Discord 通知の本体

## Current Status

- **承認取得済み（2026-06）。** Nexus Mods サポートより、本ツールの **keyless GraphQL V2 公開モデル（匿名公開）** について "Yes, it all sounds fine." と明示承認を得ました。アプリ登録/slug はユーザーログイン(SSO)を行う場合のみ必要で、discovery 機能には不要（Application-Name/Version ヘッダーの付与で十分）。キャッシュ時間は裁量で可（Nexus 側でレート制限/キャッシュを保持）。
- discovery は公開 GraphQL V2（`api.nexusmods.com/v2/graphql`・キー/登録不要）。サーバー側キー保存・キーによる自動ポーリング・ファイルミラーは行わず、常に原ページへリンク。本人確認のみユーザー自身のキーをその場で使用。
- この公開スナップショットでは secrets、runtime state、log、pid などの運用生成物は含めていません。

## English Summary

This repository is a review-oriented public snapshot of the Nexus Mods notification stack used by 7DAYSTODIE.JP.

- `wordpress-plugin/` is the API-facing component that talks to the Nexus Mods API and prepares WordPress-side data.
- `discord-bot/` is the delivery component that consumes the internal WordPress watch endpoint and posts notifications to Discord.
- Runtime secrets, logs, pid files, and generated state files are intentionally excluded.
- The discovery layer now uses the **public GraphQL V2 API with no API key or registration** (`api.nexusmods.com/v2/graphql`), per guidance from Nexus Mods Support. No personal key is stored server-side; only the user-initiated identity check uses the visitor's own key. See `wordpress-plugin/README.md` for the full AUP-compliance notes.