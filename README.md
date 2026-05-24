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

- 現在は Nexus Mods からの正式な API 利用許可待ちです。
- そのため、サイト本番では Nexus API 経由の情報収集を一時停止した状態を前提にしています。
- この公開スナップショットでは secrets、runtime state、log、pid などの運用生成物は含めていません。

## English Summary

This repository is a review-oriented public snapshot of the Nexus Mods notification stack used by 7DAYSTODIE.JP.

- `wordpress-plugin/` is the API-facing component that talks to the Nexus Mods API and prepares WordPress-side data.
- `discord-bot/` is the delivery component that consumes the internal WordPress watch endpoint and posts notifications to Discord.
- Runtime secrets, logs, pid files, and generated state files are intentionally excluded.
- The current snapshot reflects a temporary pause of Nexus API collection while official API approval is pending.