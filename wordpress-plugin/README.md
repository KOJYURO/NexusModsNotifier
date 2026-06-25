# 7DTD Nexus Browser

A WordPress plugin that powers a **7 Days to Die mod discovery interface** for the Japanese community site [7daystodie.jp](https://7daystodie.jp). It surfaces recently updated / newly added / trending mods, keyword & category search, and always links users back to the canonical Nexus Mods page.

> **English-friendly notes for the Nexus Mods team:** see [Acceptable Use compliance](#acceptable-use-aup-compliance) below. This plugin uses the **public GraphQL V2 API with no API key**, does not store any key server-side, does not mirror files, and always provides the canonical source link.

## What it does

- **Discovery feeds** — latest updated / latest added / trending lists for the `7daystodie` game domain.
- **Keyword search** — mod-name wildcard search, surfaced with a Japanese-oriented UI for JP players.
- **Category browsing** — mod categories with counts, derived live from the API.
- **Per-mod discussion pages** — a local WordPress CPT (`sevendtd_nexus_mod`) auto-generated from public metadata, with site-local comments/reactions and a cross-link to a hand-written Japanese explainer article when one exists.
- **Attribution-first** — every card and page links to the original Nexus Mods mod page.

Community comments and reactions are **the site's own WordPress content**, stored locally and kept separate from Nexus data.

## Acceptable Use (AUP) compliance

This plugin is built to follow the [Nexus Mods API Acceptable Use Policy](https://help.nexusmods.com/article/114-api-acceptable-use-policy):

- **Public GraphQL V2 only.** Discovery data is fetched from `https://api.nexusmods.com/v2/graphql`, which serves public data **without an API key or registration**.
- **No server-side key storage / no automated key usage.** No personal API key is stored on the server or used by background jobs to populate a global cache.
- **No rehosting / no scraping.** Only limited discovery metadata is displayed (name, summary, author, version, dates, thumbnail, endorsement/download counts). Raw API responses are not republished and downloadable files are never mirrored. Any caching is short-lived and exists solely to reduce duplicate requests for the same public query.
- **Identity check uses the user's own key.** The optional "link your Nexus account" feature validates with **the visitor's own API key, initiated by that visitor** (legacy `v1/users/validate.json`); the key is used in-request and not retained.
- **Best-practice headers.** Every request sends `Application-Name` and `Application-Version` headers; backoff / short-TTL caching are applied.

For any future **authenticated** features (endorsing, tracking, downloads) the project will follow the registered-application + per-user SSO key model.

## Shortcodes

| Shortcode | Purpose |
|---|---|
| `[sevendtd_nexus_mod_search]` | Search box + result cards (source selector: latest updated / added / trending) |
| `[sevendtd_nexus_mod_categories]` | Category list with sample mods |
| `[sevendtd_nexus_weekly_rank]` | Weekly ranking view |
| `[sevendtd_nexus_mod_discussions]` | Index of local per-mod discussion pages |
| `[sevendtd_nexus_account_link]` | Optional self-service Nexus account link (user's own key) |

Example:

```text
[sevendtd_nexus_mod_search per_page="12" source="latest_updated" show_source_selector="1"]
[sevendtd_nexus_mod_categories per_category="6" max_categories="10"]
```

## Installation

1. Copy this folder to `wp-content/plugins/sevendtd-nexus-browser/`.
2. Activate **7DTD Nexus Browser** in the WordPress admin.
3. (Optional) Under **Settings → 7DTD Nexus Browser** you can tune cache TTLs and the `Application-Name` / `Application-Version` headers. **No API key is required** for the public discovery features.
4. Place the shortcodes above on any page.

## Data layer

The data layer (`includes/plugin.php`) calls GraphQL V2 and maps each `Mod` node back into a legacy-REST-compatible array so the rendering layer stays simple. Key building blocks:

- `sevendtd_nb_gql_request()` — keyless POST to the GraphQL endpoint, short-TTL transient cache.
- `sevendtd_nb_gql_fetch_mods( $filter, $sort, $limit )` — builds a `ModsFilter` (always scoped to `gameDomainName: 7daystodie`, adult content excluded) and `ModsSort`, returns mapped rows.
- `sevendtd_nb_map_gql_mod()` — GraphQL node → display row.

Discovery maps to GraphQL as:

| Feature | `ModsSort` | Notes |
|---|---|---|
| Latest updated | `updatedAt DESC` | |
| Latest added | `createdAt DESC` | |
| Trending | `endorsements DESC` | |
| Keyword search | `relevance DESC` | `name` filter, `WILDCARD` op |
| Category | (default) | `categoryName` filter, `EQUALS` op |

## License

GPL-2.0-or-later (matching WordPress).
