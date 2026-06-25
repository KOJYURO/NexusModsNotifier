<?php
/**
 * 7DTD Nexus Browser の本体処理。
 *
 * @package sevendtd-nexus-browser
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * プラグイン有効化時に初期設定を投入する。
 */
function sevendtd_nb_activate_plugin() {
	$defaults = sevendtd_nb_get_default_settings();
	$current  = get_option( 'sevendtd_nb_settings', array() );

	if ( ! is_array( $current ) ) {
		$current = array();
	}

	update_option( 'sevendtd_nb_settings', array_merge( $defaults, $current ) );
}

/**
 * 設定のデフォルト値を返す。
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_default_settings() {
	return array(
		'api_base'                     => 'https://api.nexusmods.com/v2/graphql',
		'api_key'                      => '',
		'application_name'             => '7DTD Nexus Mod Notifier',
		'application_version'          => '0.1.0-review',
		'user_agent'                   => '7DTD-Nexus-Web/1.0',
		'game_domain'                  => '7daystodie',
		'cache_ttl'                    => 600,
		'category_cache_ttl'           => 3600,
		'timeout'                      => 15,
		'score_weight_downloads'       => 45,
		'score_weight_endorsements'    => 30,
		'score_weight_freshness'       => 25,
		'game_version_aliases'         => '',
		'discord_notify_token'         => '',
		'discord_notify_min_score'     => 55,
		'discord_notify_limit'         => 10,
		'discord_notify_category_ids'  => '',
		'discord_notify_max_age_hours' => 72,
		'deepl_api_key'                => '',
	);
}

/**
 * 設定値を返す。
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_settings() {
	$stored = get_option( 'sevendtd_nb_settings', array() );
	if ( ! is_array( $stored ) ) {
		$stored = array();
	}

	return array_merge( sevendtd_nb_get_default_settings(), $stored );
}

/**
 * 設定画面を登録する。
 */
function sevendtd_nb_register_settings_menu() {
	add_options_page(
		'7DTD Nexus Browser',
		'7DTD Nexus Browser',
		'manage_options',
		'sevendtd-nexus-browser',
		'sevendtd_nb_render_settings_page'
	);
}
add_action( 'admin_menu', 'sevendtd_nb_register_settings_menu' );

/**
 * 設定項目を登録する。
 */
function sevendtd_nb_register_settings() {
	register_setting(
		'sevendtd_nb_settings_group',
		'sevendtd_nb_settings',
		array(
			'type'              => 'array',
			'sanitize_callback' => 'sevendtd_nb_sanitize_settings',
			'default'           => sevendtd_nb_get_default_settings(),
		)
	);
}
add_action( 'admin_init', 'sevendtd_nb_register_settings' );

/**
 * Nexus MOD 議論用投稿タイプを登録する。
 */
function sevendtd_nb_register_discussion_post_type() {
	register_post_type(
		'sevendtd_nexus_mod',
		array(
			'labels'       => array(
				'name'          => __( 'Nexus MOD Discussions', 'sevendtd' ),
				'singular_name' => __( 'Nexus MOD', 'sevendtd' ),
				'menu_name'     => __( 'Nexus MOD', 'sevendtd' ),
			),
			'public'       => true,
			'show_ui'      => true,
			'show_in_menu' => true,
			'show_in_rest' => true,
			'has_archive'  => 'nexus-mods',
			'rewrite'      => array( 'slug' => 'nexus-mods' ),
			'supports'     => array( 'title', 'editor', 'excerpt', 'comments', 'custom-fields' ),
		)
	);
}
add_action( 'init', 'sevendtd_nb_register_discussion_post_type' );

/**
 * 必要時のみサイドバーメニュー同期を実行する。
 */
function sevendtd_nb_maybe_sync_sidebar_menu() {
	if ( empty( $GLOBALS['sevendtd_nb_sidebar_needs_sync'] ) ) {
		return;
	}

	if ( function_exists( 'sevendtd_game_sync_sidebar_item_menu' ) ) {
		sevendtd_game_sync_sidebar_item_menu();
	}
}
add_action( 'shutdown', 'sevendtd_nb_maybe_sync_sidebar_menu' );

/**
 * 設定値をサニタイズする。
 *
 * @param array<string,mixed> $input 入力値.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_sanitize_settings( $input ) {
	$defaults = sevendtd_nb_get_default_settings();
	$input    = is_array( $input ) ? $input : array();

	return array(
		'api_base'                     => esc_url_raw( isset( $input['api_base'] ) ? (string) $input['api_base'] : $defaults['api_base'] ),
		'api_key'                      => isset( $input['api_key'] ) ? sanitize_text_field( (string) $input['api_key'] ) : $defaults['api_key'],
		'application_name'             => isset( $input['application_name'] ) ? sanitize_text_field( (string) $input['application_name'] ) : $defaults['application_name'],
		'application_version'          => isset( $input['application_version'] ) ? sanitize_text_field( (string) $input['application_version'] ) : $defaults['application_version'],
		'user_agent'                   => isset( $input['user_agent'] ) ? sanitize_text_field( (string) $input['user_agent'] ) : $defaults['user_agent'],
		'game_domain'                  => isset( $input['game_domain'] ) ? sanitize_key( (string) $input['game_domain'] ) : $defaults['game_domain'],
		'cache_ttl'                    => max( 60, absint( isset( $input['cache_ttl'] ) ? $input['cache_ttl'] : $defaults['cache_ttl'] ) ),
		'category_cache_ttl'           => max( 300, absint( isset( $input['category_cache_ttl'] ) ? $input['category_cache_ttl'] : $defaults['category_cache_ttl'] ) ),
		'timeout'                      => max( 5, absint( isset( $input['timeout'] ) ? $input['timeout'] : $defaults['timeout'] ) ),
		'score_weight_downloads'       => max( 0, min( 100, absint( isset( $input['score_weight_downloads'] ) ? $input['score_weight_downloads'] : $defaults['score_weight_downloads'] ) ) ),
		'score_weight_endorsements'    => max( 0, min( 100, absint( isset( $input['score_weight_endorsements'] ) ? $input['score_weight_endorsements'] : $defaults['score_weight_endorsements'] ) ) ),
		'score_weight_freshness'       => max( 0, min( 100, absint( isset( $input['score_weight_freshness'] ) ? $input['score_weight_freshness'] : $defaults['score_weight_freshness'] ) ) ),
		'game_version_aliases'         => isset( $input['game_version_aliases'] ) ? sanitize_textarea_field( (string) $input['game_version_aliases'] ) : $defaults['game_version_aliases'],
		'discord_notify_token'         => isset( $input['discord_notify_token'] ) ? sanitize_text_field( (string) $input['discord_notify_token'] ) : $defaults['discord_notify_token'],
		'discord_notify_min_score'     => max( 0, min( 100, absint( isset( $input['discord_notify_min_score'] ) ? $input['discord_notify_min_score'] : $defaults['discord_notify_min_score'] ) ) ),
		'discord_notify_limit'         => max( 1, min( 50, absint( isset( $input['discord_notify_limit'] ) ? $input['discord_notify_limit'] : $defaults['discord_notify_limit'] ) ) ),
		'discord_notify_category_ids'  => isset( $input['discord_notify_category_ids'] ) ? sanitize_text_field( (string) $input['discord_notify_category_ids'] ) : $defaults['discord_notify_category_ids'],
		'discord_notify_max_age_hours' => max( 1, min( 720, absint( isset( $input['discord_notify_max_age_hours'] ) ? $input['discord_notify_max_age_hours'] : $defaults['discord_notify_max_age_hours'] ) ) ),
		'deepl_api_key'                => isset( $input['deepl_api_key'] ) ? sanitize_text_field( (string) $input['deepl_api_key'] ) : $defaults['deepl_api_key'],
	);
}

/**
 * 設定画面を描画する。
 */
function sevendtd_nb_render_settings_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}

	$settings = sevendtd_nb_get_settings();
	?>
	<div class="wrap">
		<h1>7DTD Nexus Browser</h1>
		<p>Nexus Mods API を使うための接続設定です。API キーはサーバー側だけで保持してください。</p>

		<form method="post" action="options.php">
			<?php settings_fields( 'sevendtd_nb_settings_group' ); ?>
			<table class="form-table" role="presentation">
				<tr>
					<th scope="row"><label for="sevendtd_nb_api_base">GraphQL Endpoint</label></th>
					<td><input id="sevendtd_nb_api_base" name="sevendtd_nb_settings[api_base]" type="url" class="regular-text" value="<?php echo esc_attr( (string) $settings['api_base'] ); ?>"><p class="description">公開 discovery は Nexus GraphQL V2（<code>https://api.nexusmods.com/v2/graphql</code>）を使用します。API キー不要・公開データのみ取得します。</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_api_key">API Key（任意・未使用）</label></th>
					<td><input id="sevendtd_nb_api_key" name="sevendtd_nb_settings[api_key]" type="password" class="regular-text" value="<?php echo esc_attr( (string) $settings['api_key'] ); ?>"><p class="description">公開検索では使用しません（AUP 準拠: サーバー側にキーを保存・自動利用しない）。本人確認はユーザー自身のキーをその場限りで使います。空欄で構いません。</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_application_name">Application Name</label></th>
					<td><input id="sevendtd_nb_application_name" name="sevendtd_nb_settings[application_name]" type="text" class="regular-text" value="<?php echo esc_attr( (string) $settings['application_name'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_application_version">Application Version</label></th>
					<td><input id="sevendtd_nb_application_version" name="sevendtd_nb_settings[application_version]" type="text" class="regular-text" value="<?php echo esc_attr( (string) $settings['application_version'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_user_agent">User Agent</label></th>
					<td><input id="sevendtd_nb_user_agent" name="sevendtd_nb_settings[user_agent]" type="text" class="regular-text" value="<?php echo esc_attr( (string) $settings['user_agent'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_game_domain">Game Domain</label></th>
					<td><input id="sevendtd_nb_game_domain" name="sevendtd_nb_settings[game_domain]" type="text" class="regular-text" value="<?php echo esc_attr( (string) $settings['game_domain'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_cache_ttl">検索キャッシュ秒数</label></th>
					<td><input id="sevendtd_nb_cache_ttl" name="sevendtd_nb_settings[cache_ttl]" type="number" min="60" step="60" value="<?php echo esc_attr( (string) $settings['cache_ttl'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_category_cache_ttl">カテゴリキャッシュ秒数</label></th>
					<td><input id="sevendtd_nb_category_cache_ttl" name="sevendtd_nb_settings[category_cache_ttl]" type="number" min="300" step="300" value="<?php echo esc_attr( (string) $settings['category_cache_ttl'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_timeout">タイムアウト秒数</label></th>
					<td><input id="sevendtd_nb_timeout" name="sevendtd_nb_settings[timeout]" type="number" min="5" step="1" value="<?php echo esc_attr( (string) $settings['timeout'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_score_weight_downloads">スコア重み: DL</label></th>
					<td><input id="sevendtd_nb_score_weight_downloads" name="sevendtd_nb_settings[score_weight_downloads]" type="number" min="0" max="100" step="1" value="<?php echo esc_attr( (string) $settings['score_weight_downloads'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_score_weight_endorsements">スコア重み: Endorse</label></th>
					<td><input id="sevendtd_nb_score_weight_endorsements" name="sevendtd_nb_settings[score_weight_endorsements]" type="number" min="0" max="100" step="1" value="<?php echo esc_attr( (string) $settings['score_weight_endorsements'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_score_weight_freshness">スコア重み: 鮮度</label></th>
					<td><input id="sevendtd_nb_score_weight_freshness" name="sevendtd_nb_settings[score_weight_freshness]" type="number" min="0" max="100" step="1" value="<?php echo esc_attr( (string) $settings['score_weight_freshness'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_game_version_aliases">7DTD バージョン辞書</label></th>
					<td>
						<textarea id="sevendtd_nb_game_version_aliases" name="sevendtd_nb_settings[game_version_aliases]" rows="4" class="large-text"><?php echo esc_textarea( (string) $settings['game_version_aliases'] ); ?></textarea>
						<p class="description">形式: v2.0:2.0,alpha22,a22 のように1行ずつ追加できます。</p>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_discord_notify_token">Discord 通知トークン</label></th>
					<td><input id="sevendtd_nb_discord_notify_token" name="sevendtd_nb_settings[discord_notify_token]" type="password" class="regular-text" value="<?php echo esc_attr( (string) $settings['discord_notify_token'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_discord_notify_min_score">Discord 通知最小スコア</label></th>
					<td><input id="sevendtd_nb_discord_notify_min_score" name="sevendtd_nb_settings[discord_notify_min_score]" type="number" min="0" max="100" step="1" value="<?php echo esc_attr( (string) $settings['discord_notify_min_score'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_discord_notify_limit">Discord 通知取得件数</label></th>
					<td><input id="sevendtd_nb_discord_notify_limit" name="sevendtd_nb_settings[discord_notify_limit]" type="number" min="1" max="50" step="1" value="<?php echo esc_attr( (string) $settings['discord_notify_limit'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_discord_notify_category_ids">Discord 通知カテゴリID</label></th>
					<td><input id="sevendtd_nb_discord_notify_category_ids" name="sevendtd_nb_settings[discord_notify_category_ids]" type="text" class="regular-text" value="<?php echo esc_attr( (string) $settings['discord_notify_category_ids'] ); ?>"><p class="description">カンマ区切り（例: 5,7,11）。空欄で全カテゴリ対象。</p></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_discord_notify_max_age_hours">Discord 通知対象時間（時間）</label></th>
					<td><input id="sevendtd_nb_discord_notify_max_age_hours" name="sevendtd_nb_settings[discord_notify_max_age_hours]" type="number" min="1" max="720" step="1" value="<?php echo esc_attr( (string) $settings['discord_notify_max_age_hours'] ); ?>"></td>
				</tr>
				<tr>
					<th scope="row"><label for="sevendtd_nb_deepl_api_key">DeepL API キー（MOD解説日本語訳）</label></th>
					<td><input id="sevendtd_nb_deepl_api_key" name="sevendtd_nb_settings[deepl_api_key]" type="password" class="regular-text" value="<?php echo esc_attr( (string) $settings['deepl_api_key'] ); ?>"><p class="description">DeepL 無料プランは末尾が :fx のキーです。空欄の場合は翻訳を行いません。</p></td>
				</tr>
			</table>
			<?php submit_button(); ?>
		</form>

		<h2>利用するショートコード</h2>
		<ul>
			<li><code>[sevendtd_nexus_mod_search]</code></li>
			<li><code>[sevendtd_nexus_mod_categories]</code></li>
		</ul>
	</div>
	<?php
}

/**
 * 共通ヘッダーを返す。
 *
 * @return array<string,string>
 */
function sevendtd_nb_get_request_headers() {
	$settings = sevendtd_nb_get_settings();

	return array(
		'apikey'              => (string) $settings['api_key'],
		'Accept'              => 'application/json',
		'User-Agent'          => (string) $settings['user_agent'],
		'Application-Name'    => (string) $settings['application_name'],
		'Application-Version' => (string) $settings['application_version'],
	);
}

/**
 * API の GET リクエストを行う。
 *
 * @param string              $path      API パス.
 * @param array<string,mixed> $query     クエリ.
 * @param string              $cache_key キャッシュキー.
 * @param int                 $ttl       キャッシュ秒数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_request_json( $path, array $query = array(), $cache_key = '', $ttl = 0 ) {
	$settings = sevendtd_nb_get_settings();

	if ( '' === (string) $settings['api_key'] ) {
		return array(
			'ok'      => false,
			'message' => 'Nexus API Key が未設定です。',
		);
	}

	if ( '' !== $cache_key && $ttl > 0 ) {
		$cached = get_transient( $cache_key );
		if ( false !== $cached && is_array( $cached ) ) {
			return array(
				'ok'     => true,
				'data'   => $cached,
				'cached' => true,
			);
		}
	}

	$base_url = untrailingslashit( (string) $settings['api_base'] );
	$url      = $base_url . $path;

	if ( ! empty( $query ) ) {
		$url = add_query_arg( $query, $url );
	}

	$response = wp_remote_get(
		$url,
		array(
			'timeout' => (int) $settings['timeout'],
			'headers' => sevendtd_nb_get_request_headers(),
		)
	);

	if ( is_wp_error( $response ) ) {
		return array(
			'ok'      => false,
			'message' => 'Nexus API への接続に失敗しました。',
			'error'   => $response->get_error_message(),
		);
	}

	$code = (int) wp_remote_retrieve_response_code( $response );
	$body = (string) wp_remote_retrieve_body( $response );
	$data = json_decode( $body, true );

	if ( $code < 200 || $code >= 300 || ! is_array( $data ) ) {
		return array(
			'ok'      => false,
			'message' => 'Nexus API の応答が不正です。',
			'status'  => $code,
		);
	}

	if ( '' !== $cache_key && $ttl > 0 ) {
		set_transient( $cache_key, $data, $ttl );
	}

	return array(
		'ok'   => true,
		'data' => $data,
	);
}

/**
 * ゲームドメインを返す。
 *
 * @return string
 */
function sevendtd_nb_get_game_domain() {
	$settings = sevendtd_nb_get_settings();
	return (string) $settings['game_domain'];
}

/**
 * 最新・注目系の MOD を取得して統合する。
 *
 * @return array<int,array<string,mixed>>
 */
/**
 * Nexus GraphQL V2 公開エンドポイント URL を返す（API キー不要・公開データのみ）。
 *
 * @return string
 */
function sevendtd_nb_get_graphql_endpoint() {
	$settings = sevendtd_nb_get_settings();
	$base     = trim( (string) $settings['api_base'] );
	if ( '' === $base || false === strpos( $base, 'graphql' ) ) {
		$base = 'https://api.nexusmods.com/v2/graphql';
	}
	return $base;
}

/**
 * GraphQL V2 へ POST する。
 *
 * 公開データのみを取得し、API キーは送らない（AUP 準拠: サーバー側キー保存・自動利用なし）。
 *
 * @param string              $query     GraphQL クエリ.
 * @param array<string,mixed> $variables 変数.
 * @param string              $cache_key キャッシュキー（重複リクエスト削減目的）.
 * @param int                 $ttl       キャッシュ秒数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_gql_request( $query, array $variables = array(), $cache_key = '', $ttl = 0 ) {
	$settings = sevendtd_nb_get_settings();

	if ( '' !== $cache_key && $ttl > 0 ) {
		$cached = get_transient( $cache_key );
		if ( false !== $cached && is_array( $cached ) ) {
			return array(
				'ok'     => true,
				'data'   => $cached,
				'cached' => true,
			);
		}
	}

	$response = wp_remote_post(
		sevendtd_nb_get_graphql_endpoint(),
		array(
			'timeout' => (int) $settings['timeout'],
			'headers' => array(
				'Content-Type'        => 'application/json',
				'Accept'              => 'application/json',
				'User-Agent'          => (string) $settings['user_agent'],
				'Application-Name'    => (string) $settings['application_name'],
				'Application-Version' => (string) $settings['application_version'],
			),
			'body'    => wp_json_encode(
				array(
					'query'     => $query,
					'variables' => (object) $variables,
				)
			),
		)
	);

	if ( is_wp_error( $response ) ) {
		return array(
			'ok'      => false,
			'message' => 'Nexus GraphQL API への接続に失敗しました。',
			'error'   => $response->get_error_message(),
		);
	}

	$code = (int) wp_remote_retrieve_response_code( $response );
	$body = (string) wp_remote_retrieve_body( $response );
	$json = json_decode( $body, true );

	if ( $code < 200 || $code >= 300 || ! is_array( $json ) || isset( $json['errors'] ) || ! isset( $json['data'] ) ) {
		return array(
			'ok'      => false,
			'message' => 'Nexus GraphQL API の応答が不正です。',
			'status'  => $code,
		);
	}

	if ( '' !== $cache_key && $ttl > 0 ) {
		set_transient( $cache_key, $json['data'], $ttl );
	}

	return array(
		'ok'   => true,
		'data' => $json['data'],
	);
}

/**
 * GraphQL の Mod ノードをレガシー REST 互換の配列へ変換する（表示層を無改修で再利用するため）。
 *
 * @param array<string,mixed> $node GraphQL Mod ノード.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_map_gql_mod( array $node ) {
	$game_domain = sevendtd_nb_get_game_domain();
	$mod_id      = isset( $node['modId'] ) ? (int) $node['modId'] : 0;
	$uploader    = ( isset( $node['uploader'] ) && is_array( $node['uploader'] ) && isset( $node['uploader']['name'] ) ) ? (string) $node['uploader']['name'] : '';
	$author      = isset( $node['author'] ) && '' !== (string) $node['author'] ? (string) $node['author'] : $uploader;
	$cat         = ( isset( $node['modCategory'] ) && is_array( $node['modCategory'] ) ) ? $node['modCategory'] : array();
	$cat_name    = isset( $cat['name'] ) && '' !== (string) $cat['name'] ? (string) $cat['name'] : ( isset( $node['category'] ) ? (string) $node['category'] : '' );
	$cat_id      = isset( $cat['categoryId'] ) ? (int) $cat['categoryId'] : 0;
	$updated_at  = isset( $node['updatedAt'] ) ? (string) $node['updatedAt'] : '';
	$mod_url     = $mod_id > 0
		? 'https://www.nexusmods.com/' . rawurlencode( $game_domain ) . '/mods/' . $mod_id
		: 'https://www.nexusmods.com/' . rawurlencode( $game_domain );

	return array(
		'mod_id'        => $mod_id,
		'name'          => isset( $node['name'] ) ? (string) $node['name'] : '',
		'summary'       => isset( $node['summary'] ) ? (string) $node['summary'] : '',
		'version'       => isset( $node['version'] ) ? (string) $node['version'] : '',
		'author'        => $author,
		'uploaded_by'   => '' !== $uploader ? $uploader : $author,
		'user'          => '' !== $uploader ? $uploader : $author,
		'category_id'   => $cat_id,
		'category_name' => $cat_name,
		'category'      => $cat_name,
		'picture_url'   => isset( $node['pictureUrl'] ) ? (string) $node['pictureUrl'] : '',
		'downloads'     => isset( $node['downloads'] ) ? (int) $node['downloads'] : 0,
		'endorsements'  => isset( $node['endorsements'] ) ? (int) $node['endorsements'] : 0,
		'updated_at'    => $updated_at,
		'updated_date'  => $updated_at,
		'created_at'    => isset( $node['createdAt'] ) ? (string) $node['createdAt'] : '',
		'url'           => $mod_url,
		'mod_url'       => $mod_url,
	);
}

/**
 * GraphQL で MOD を取得し、レガシー互換の配列群で返す共通関数。
 *
 * @param array<string,mixed>           $filter    追加 ModsFilter 条件.
 * @param array<int,array<string,mixed>> $sort      ModsSort 配列.
 * @param int                           $limit     件数.
 * @param string                        $cache_key キャッシュキー.
 * @param int                           $ttl       キャッシュ秒数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_gql_fetch_mods( array $filter, array $sort = array(), $limit = 12, $cache_key = '', $ttl = 0 ) {
	$limit = max( 1, min( 50, absint( $limit ) ) );

	$base_filter = array(
		'gameDomainName' => array(
			'value' => sevendtd_nb_get_game_domain(),
			'op'    => 'EQUALS',
		),
		'adultContent'   => array(
			'value' => false,
			'op'    => 'EQUALS',
		),
	);
	$filter = array_merge( $base_filter, $filter );

	$query = 'query($filter: ModsFilter, $sort: [ModsSort!], $count: Int!) {'
		. ' mods(filter: $filter, sort: $sort, count: $count, offset: 0) {'
		. ' nodes { modId name summary version author uploader { name } updatedAt createdAt endorsements downloads pictureUrl category modCategory { categoryId name } }'
		. ' totalCount } }';

	$variables = array(
		'filter' => (object) $filter,
		'count'  => $limit,
	);
	if ( ! empty( $sort ) ) {
		$variables['sort'] = $sort;
	}

	$result = sevendtd_nb_gql_request( $query, $variables, $cache_key, $ttl );

	if ( empty( $result['ok'] ) || empty( $result['data']['mods']['nodes'] ) || ! is_array( $result['data']['mods']['nodes'] ) ) {
		return array(
			'ok'      => false,
			'data'    => array(),
			'message' => isset( $result['message'] ) ? (string) $result['message'] : 'MOD 取得に失敗しました。',
		);
	}

	$mods = array();
	foreach ( $result['data']['mods']['nodes'] as $node ) {
		if ( is_array( $node ) ) {
			$mods[] = sevendtd_nb_map_gql_mod( $node );
		}
	}

	return array(
		'ok'    => true,
		'data'  => $mods,
		'total' => isset( $result['data']['mods']['totalCount'] ) ? (int) $result['data']['mods']['totalCount'] : count( $mods ),
	);
}

function sevendtd_nb_get_merged_feed_mods() {
	$settings = sevendtd_nb_get_settings();
	$ttl      = (int) $settings['cache_ttl'];
	$sources  = array(
		'latest_updated' => array( array( 'updatedAt' => array( 'direction' => 'DESC' ) ) ),
		'latest_added'   => array( array( 'createdAt' => array( 'direction' => 'DESC' ) ) ),
		'trending'       => array( array( 'endorsements' => array( 'direction' => 'DESC' ) ) ),
	);

	$merged = array();

	foreach ( $sources as $label => $sort ) {
		$result = sevendtd_nb_gql_fetch_mods( array(), $sort, 24, 'sevendtd_nb_gql_' . $label, $ttl );
		if ( empty( $result['ok'] ) || empty( $result['data'] ) || ! is_array( $result['data'] ) ) {
			continue;
		}

		foreach ( $result['data'] as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}

			$mod_id = isset( $row['mod_id'] ) ? (string) $row['mod_id'] : '';
			$key    = '' !== $mod_id && '0' !== $mod_id ? $mod_id : md5( wp_json_encode( $row ) );
			if ( ! isset( $merged[ $key ] ) ) {
				$merged[ $key ] = $row;
			}
		}
	}

	return array_values( $merged );
}

/**
 * カテゴリ一覧を取得する。
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_categories() {
	$settings = sevendtd_nb_get_settings();
	$ttl      = (int) $settings['category_cache_ttl'];

	// GraphQL には「ゲームの MOD カテゴリ一覧」専用クエリが無いため、人気上位サンプルの
	// modCategory(id+name) からカテゴリ集合を導出する（カテゴリ ID は modCategory.categoryId）。
	$sample = sevendtd_nb_gql_fetch_mods(
		array(),
		array( array( 'endorsements' => array( 'direction' => 'DESC' ) ) ),
		50,
		'sevendtd_nb_gql_category_sample',
		$ttl
	);

	$rows = ( ! empty( $sample['ok'] ) && ! empty( $sample['data'] ) )
		? sevendtd_nb_derive_categories_from_feed( $sample['data'] )
		: array();
	$rows = sevendtd_nb_merge_category_rows(
		$rows,
		sevendtd_nb_derive_categories_from_feed( sevendtd_nb_get_merged_feed_mods() ),
		sevendtd_nb_get_categories_from_search_samples()
	);

	if ( ! empty( $rows ) ) {
		return array(
			'ok'   => true,
			'data' => $rows,
		);
	}

	return array(
		'ok'      => false,
		'message' => 'カテゴリ取得に失敗しました。',
		'data'    => array(),
	);
}

/**
 * カテゴリ配列を正規化して重複除去する。
 *
 * @param array<int,array<string,mixed>> ...$groups カテゴリ配列群.
 *
 * @return array<int,array<string,mixed>>
 */
function sevendtd_nb_merge_category_rows( ...$groups ) {
	$merged = array();

	foreach ( $groups as $rows ) {
		if ( ! is_array( $rows ) ) {
			continue;
		}

		foreach ( $rows as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}

			$category_id = absint( isset( $row['category_id'] ) ? $row['category_id'] : ( isset( $row['categoryid'] ) ? $row['categoryid'] : 0 ) );
			$name        = trim( (string) ( isset( $row['name'] ) ? $row['name'] : ( isset( $row['category_name'] ) ? $row['category_name'] : '' ) ) );
			if ( '' === $name ) {
				continue;
			}

			$key = $category_id > 0 ? 'id:' . (string) $category_id : 'name:' . sanitize_title( $name );
			if ( isset( $merged[ $key ] ) ) {
				continue;
			}

			$merged[ $key ] = array(
				'category_id'   => $category_id,
				'name'          => $name,
				'category_name' => $name,
			);
		}
	}

	usort(
		$merged,
		static function ( $left, $right ) {
			return strcmp( (string) $left['name'], (string) $right['name'] );
		}
	);

	return array_values( $merged );
}

/**
 * 検索 API のサンプル結果からカテゴリ候補を補完する。
 *
 * @return array<int,array<string,mixed>>
 */
function sevendtd_nb_get_categories_from_search_samples() {
	$settings = sevendtd_nb_get_settings();
	$ttl      = (int) $settings['category_cache_ttl'];

	// GraphQL の複数ソート（人気/最新/新着）サンプルから modCategory を集約してカテゴリを補完する。
	$sorts = array(
		'pop'  => array( array( 'endorsements' => array( 'direction' => 'DESC' ) ) ),
		'dl'   => array( array( 'downloads' => array( 'direction' => 'DESC' ) ) ),
		'new'  => array( array( 'createdAt' => array( 'direction' => 'DESC' ) ) ),
	);

	$categories = array();
	foreach ( $sorts as $label => $sort ) {
		$result = sevendtd_nb_gql_fetch_mods( array(), $sort, 50, 'sevendtd_nb_gql_catsample_' . $label, $ttl );
		if ( empty( $result['ok'] ) || empty( $result['data'] ) || ! is_array( $result['data'] ) ) {
			continue;
		}
		$categories = sevendtd_nb_merge_category_rows( $categories, sevendtd_nb_derive_categories_from_feed( $result['data'] ) );
	}

	return $categories;
}

/**
 * MOD 検索を行う。
 *
 * @param string $terms       検索語.
 * @param int    $category_id カテゴリ ID.
 * @param int    $limit       最大件数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_search_mods( $terms = '', $category_id = 0, $limit = 12 ) {
	$settings    = sevendtd_nb_get_settings();
	$game_domain = sevendtd_nb_get_game_domain();
	$terms       = trim( (string) $terms );
	$category_id = absint( $category_id );
	$limit       = max( 1, min( 24, absint( $limit ) ) );

	$filter = array();
	$sort   = array( array( 'endorsements' => array( 'direction' => 'DESC' ) ) );

	if ( '' !== $terms ) {
		// 名前のワイルドカード部分一致（生の語をそのまま渡す＝部分一致）。
		$filter['name'] = array(
			'value' => $terms,
			'op'    => 'WILDCARD',
		);
		$sort = array( array( 'relevance' => array( 'direction' => 'DESC' ) ) );
	}

	if ( $category_id > 0 ) {
		$lookup = sevendtd_nb_get_category_lookup_map();
		if ( isset( $lookup['by_id'][ $category_id ] ) ) {
			$filter['categoryName'] = array(
				'value' => (string) $lookup['by_id'][ $category_id ],
				'op'    => 'EQUALS',
			);
		}
	}

	$cache_key = 'sevendtd_nb_gql_search_' . md5( wp_json_encode( array( $terms, $category_id, $limit ) ) );
	$result    = sevendtd_nb_gql_fetch_mods( $filter, $sort, $limit, $cache_key, (int) $settings['cache_ttl'] );

	if ( ! empty( $result['ok'] ) && ! empty( $result['data'] ) && is_array( $result['data'] ) ) {
		return array(
			'ok'   => true,
			'data' => array_slice( $result['data'], 0, $limit ),
		);
	}

	$fallback = sevendtd_nb_filter_feed_mods( sevendtd_nb_get_merged_feed_mods(), $terms, $category_id, $limit );

	return array(
		'ok'       => true,
		'data'     => $fallback,
		'fallback' => true,
		'message'  => '検索 API が利用できなかったため、最新取得データから絞り込み表示しています。',
	);
}

/**
 * カテゴリ別の MOD 一覧を返す。
 *
 * @param int $category_id カテゴリ ID.
 * @param int $limit       件数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_category_mods( $category_id, $limit = 6 ) {
	return sevendtd_nb_search_mods( '', absint( $category_id ), absint( $limit ) );
}

/**
 * フィードデータからカテゴリ一覧を推定する。
 *
 * @param array<int,array<string,mixed>> $mods MOD 配列.
 *
 * @return array<int,array<string,mixed>>
 */
function sevendtd_nb_derive_categories_from_feed( array $mods ) {
	$categories = array();

	foreach ( $mods as $mod ) {
		$category_id   = sevendtd_nb_get_mod_value( $mod, array( 'category_id', 'categoryid' ) );
		$category_name = sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) );

		if ( '' === $category_name ) {
			continue;
		}

		$key = '' !== $category_id ? (string) $category_id : sanitize_title( $category_name );

		if ( ! isset( $categories[ $key ] ) ) {
			$categories[ $key ] = array(
				'category_id'   => '' !== $category_id ? (int) $category_id : 0,
				'name'          => $category_name,
				'category_name' => $category_name,
			);
		}
	}

	usort(
		$categories,
		static function ( $left, $right ) {
			return strcmp( (string) $left['name'], (string) $right['name'] );
		}
	);

	return array_values( $categories );
}

/**
 * フィードデータを検索条件で絞り込む。
 *
 * @param array<int,array<string,mixed>> $mods        MOD 配列.
 * @param string                         $terms       検索語.
 * @param int                            $category_id カテゴリ ID.
 * @param int                            $limit       最大件数.
 *
 * @return array<int,array<string,mixed>>
 */
function sevendtd_nb_filter_feed_mods( array $mods, $terms, $category_id, $limit ) {
	$terms       = trim( sevendtd_safe_strtolower( (string) $terms ) );
	$category_id = absint( $category_id );
	$results     = array();

	foreach ( $mods as $mod ) {
		$haystack_parts = array(
			sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ),
			sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ),
			sevendtd_nb_get_mod_value( $mod, array( 'author', 'uploaded_by', 'user' ) ),
			sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) ),
		);

		$haystack = sevendtd_safe_strtolower( implode( ' ', array_filter( $haystack_parts ) ) );
		$mod_cat  = absint( sevendtd_nb_get_mod_value( $mod, array( 'category_id', 'categoryid' ) ) );

		if ( '' !== $terms && false === mb_strpos( $haystack, $terms ) ) {
			continue;
		}

		if ( $category_id > 0 && $mod_cat !== $category_id ) {
			continue;
		}

		$results[] = $mod;

		if ( count( $results ) >= $limit ) {
			break;
		}
	}

	return $results;
}

/**
 * MOD 配列から値を柔軟に取り出す。
 *
 * @param array<string,mixed> $mod  MOD データ.
 * @param array<int,string>   $keys 候補キー.
 *
 * @return string
 */
function sevendtd_nb_get_mod_value( array $mod, array $keys ) {
	foreach ( $keys as $key ) {
		if ( isset( $mod[ $key ] ) && ! is_array( $mod[ $key ] ) ) {
			return trim( (string) $mod[ $key ] );
		}
	}

	return '';
}

/**
 * MOD の URL を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_url( array $mod ) {
	$url = sevendtd_nb_get_mod_value( $mod, array( 'url', 'mod_url' ) );
	if ( '' !== $url ) {
		return $url;
	}

	$mod_id      = sevendtd_nb_get_mod_value( $mod, array( 'mod_id', 'id' ) );
	$game_domain = sevendtd_nb_get_game_domain();

	if ( '' === $mod_id ) {
		return 'https://www.nexusmods.com/' . rawurlencode( $game_domain );
	}

	return 'https://www.nexusmods.com/' . rawurlencode( $game_domain ) . '/mods/' . rawurlencode( $mod_id );
}

/**
 * 更新日時を整形する。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_updated_label( array $mod ) {
	$timestamp = sevendtd_nb_get_mod_value( $mod, array( 'updated_timestamp', 'updated_time' ) );
	if ( '' !== $timestamp && ctype_digit( $timestamp ) ) {
		return wp_date( 'Y-m-d H:i', (int) $timestamp );
	}

	return sevendtd_nb_get_mod_value( $mod, array( 'updated_at', 'updated_date' ) );
}

/**
 * バージョン表示を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_version_label( array $mod ) {
	return sevendtd_nb_get_mod_value( $mod, array( 'version', 'mod_version' ) );
}

/** * MOD ダウンロード数を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return int
 */
function sevendtd_nb_get_mod_downloads( array $mod ) {
	$downloads = sevendtd_nb_get_mod_value( $mod, array( 'downloads', 'download_count' ) );
	return absint( $downloads );
}

/**
 * MOD Endorse 数を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return int
 */
function sevendtd_nb_get_mod_endorsements( array $mod ) {
	$endorsements = sevendtd_nb_get_mod_value( $mod, array( 'endorsements', 'endorse_count' ) );
	return absint( $endorsements );
}

/** * MOD 画像 URL を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_image_url( array $mod ) {
	return sevendtd_nb_get_mod_value( $mod, array( 'picture_url', 'image', 'thumbnail_url', 'mod_image' ) );
}

/**
 * MOD 固有キーを返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_key( array $mod ) {
	$mod_id = sevendtd_nb_get_mod_value( $mod, array( 'mod_id', 'id' ) );
	if ( '' !== $mod_id ) {
		return $mod_id;
	}

	return md5( wp_json_encode( $mod ) );
}

/**
 * 更新日時をUnixタイムスタンプで返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return int
 */
function sevendtd_nb_get_mod_updated_timestamp( array $mod ) {
	$timestamp = sevendtd_nb_get_mod_value( $mod, array( 'updated_timestamp', 'updated_time' ) );
	if ( '' !== $timestamp && ctype_digit( $timestamp ) ) {
		return (int) $timestamp;
	}

	$date_text = sevendtd_nb_get_mod_value( $mod, array( 'updated_at', 'updated_date' ) );
	if ( '' === $date_text ) {
		return 0;
	}

	$parsed = strtotime( $date_text );
	return false === $parsed ? 0 : (int) $parsed;
}

/**
 * MOD の簡易導入判断スコアを返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return int
 */
function sevendtd_nb_get_mod_score( array $mod ) {
	$downloads    = sevendtd_nb_get_mod_downloads( $mod );
	$endorsements = sevendtd_nb_get_mod_endorsements( $mod );
	$updated_ts   = sevendtd_nb_get_mod_updated_timestamp( $mod );
	$days_elapsed = $updated_ts > 0 ? max( 0, (int) floor( ( time() - $updated_ts ) / DAY_IN_SECONDS ) ) : 365;
	$settings     = sevendtd_nb_get_settings();
	$w_downloads  = max( 0, absint( $settings['score_weight_downloads'] ) );
	$w_endorse    = max( 0, absint( $settings['score_weight_endorsements'] ) );
	$w_fresh      = max( 0, absint( $settings['score_weight_freshness'] ) );
	$weight_sum   = max( 1, $w_downloads + $w_endorse + $w_fresh );

	$download_signal = min( 100, (int) round( log( max( 1, $downloads ) + 1, 10 ) * 22 ) );
	$endorse_signal  = min( 100, (int) round( log( max( 1, $endorsements ) + 1, 10 ) * 24 ) );
	$fresh_signal    = max( 0, 100 - min( 100, $days_elapsed * 4 ) );

	$score = ( $download_signal * $w_downloads ) + ( $endorse_signal * $w_endorse ) + ( $fresh_signal * $w_fresh );

	return max( 0, min( 100, (int) round( $score / $weight_sum ) ) );
}

/**
 * 7DTD バージョン辞書を返す。
 *
 * @return array<string,array<int,string>>
 */
function sevendtd_nb_get_7dtd_version_alias_map() {
	$map = array(
		'v2.0' => array( '2.0', 'v2.0', 'alpha22', 'a22' ),
		'v1.0' => array( '1.0', 'v1.0', 'alpha21', 'a21' ),
		'v0.9' => array( '0.9', 'v0.9', 'alpha20', 'a20' ),
	);

	$settings = sevendtd_nb_get_settings();
	$raw      = isset( $settings['game_version_aliases'] ) ? (string) $settings['game_version_aliases'] : '';

	if ( '' === trim( $raw ) ) {
		return $map;
	}

	$lines = preg_split( '/\r\n|\r|\n/', $raw );
	if ( ! is_array( $lines ) ) {
		return $map;
	}

	foreach ( $lines as $line ) {
		$line = trim( (string) $line );
		if ( '' === $line || false === strpos( $line, ':' ) ) {
			continue;
		}

		list( $canonical, $aliases ) = array_map( 'trim', explode( ':', $line, 2 ) );
		if ( '' === $canonical ) {
			continue;
		}

		$key = sevendtd_safe_strtolower( $canonical );
		if ( ! isset( $map[ $key ] ) || ! is_array( $map[ $key ] ) ) {
			$map[ $key ] = array();
		}

		$map[ $key ][] = $canonical;
		foreach ( explode( ',', $aliases ) as $alias ) {
			$alias = trim( $alias );
			if ( '' !== $alias ) {
				$map[ $key ][] = $alias;
			}
		}

		$map[ $key ] = array_values( array_unique( $map[ $key ] ) );
	}

	return $map;
}

/**
 * 互換性判定用の検索語群を返す。
 *
 * @param string $game_version 入力値.
 *
 * @return array<int,string>
 */
function sevendtd_nb_expand_game_version_terms( $game_version ) {
	$needle = sevendtd_safe_strtolower( trim( (string) $game_version ) );
	if ( '' === $needle ) {
		return array();
	}

	$terms = array( $needle );
	$map   = sevendtd_nb_get_7dtd_version_alias_map();

	foreach ( $map as $canonical => $aliases ) {
		$all        = array_merge( array( $canonical ), is_array( $aliases ) ? $aliases : array() );
		$normalized = array_map(
			static function ( $item ) {
				return sevendtd_safe_strtolower( trim( (string) $item ) );
			},
			$all
		);

		if ( in_array( $needle, $normalized, true ) ) {
			$terms = array_merge( $terms, $normalized );
		}
	}

	return array_values( array_unique( array_filter( $terms ) ) );
}

/**
 * スコアバッジ名を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 * @param int                 $score スコア.
 *
 * @return string
 */
function sevendtd_nb_get_mod_score_badge( array $mod, $score ) {
	$downloads    = sevendtd_nb_get_mod_downloads( $mod );
	$updated_ts   = sevendtd_nb_get_mod_updated_timestamp( $mod );
	$is_new       = $updated_ts > 0 && ( time() - $updated_ts ) <= ( 3 * DAY_IN_SECONDS ) && $downloads < 5000;
	$is_stable    = $downloads >= 30000 || $score >= 75;
	$is_attention = $score >= 55;

	if ( $is_new ) {
		return '新規';
	}

	if ( $is_stable ) {
		return '安定';
	}

	if ( $is_attention ) {
		return '注目';
	}

	return '';
}

/**
 * MOD から議論ページ向けの用途ラベルを推定する。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_detect_mod_side_label( array $mod ) {
	$haystack = sevendtd_safe_strtolower(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) )
	);

	if ( false !== mb_strpos( $haystack, 'server' ) || false !== mb_strpos( $haystack, 'dedicated' ) ) {
		return 'サーバー向け';
	}
	if ( false !== mb_strpos( $haystack, 'client' ) || false !== mb_strpos( $haystack, 'hud' ) || false !== mb_strpos( $haystack, 'ui' ) ) {
		return 'クライアント向け';
	}

	return '汎用';
}

/**
 * MOD 議論投稿の署名を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_build_mod_discussion_signature( array $mod ) {
	$tags = array_merge(
		sevendtd_nb_extract_japanese_tags( $mod, 6 ),
		sevendtd_nb_detect_mod_side_tags( $mod )
	);
	$tags = array_values( array_unique( array_filter( array_map( 'trim', $tags ) ) ) );

	$parts = array(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ),
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ),
		sevendtd_nb_get_mod_value( $mod, array( 'author', 'uploaded_by', 'user' ) ),
		sevendtd_nb_get_mod_image_url( $mod ),
		sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) ),
		sevendtd_nb_get_mod_version_label( $mod ),
		sevendtd_nb_get_mod_updated_label( $mod ),
		sevendtd_nb_get_mod_url( $mod ),
		sevendtd_nb_detect_mod_side_label( $mod ),
		implode( ',', $tags ),
	);

	return md5( implode( '|', $parts ) );
}

/**
 * MOD ID から既存の議論投稿 ID を返す。
 *
 * @param string $mod_id MOD ID.
 *
 * @return int
 */
function sevendtd_nb_get_mod_discussion_post_id( $mod_id ) {
	$mod_id = trim( (string) $mod_id );
	if ( '' === $mod_id ) {
		return 0;
	}

	$posts = get_posts(
		array(
			'post_type'      => 'sevendtd_nexus_mod',
			'post_status'    => array( 'publish', 'draft', 'pending', 'private' ),
			'posts_per_page' => 1,
			'fields'         => 'ids',
			'meta_key'       => 'nexus_mod_id',
			'meta_value'     => $mod_id,
		)
	);

	if ( empty( $posts ) ) {
		return 0;
	}

	return (int) $posts[0];
}

/**
 * MOD データを議論投稿として作成/更新する。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return int
 */
function sevendtd_nb_upsert_mod_discussion_post( array $mod ) {
	$mod_id = sevendtd_nb_get_mod_value( $mod, array( 'mod_id', 'id' ) );
	if ( '' === $mod_id ) {
		return 0;
	}

	$title      = sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) );
	$summary    = sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) );
	$author     = sevendtd_nb_get_mod_value( $mod, array( 'author', 'uploaded_by', 'user' ) );
	$version    = sevendtd_nb_get_mod_version_label( $mod );
	$updated    = sevendtd_nb_get_mod_updated_label( $mod );
	$mod_url    = sevendtd_nb_get_mod_url( $mod );
	$image_url  = sevendtd_nb_get_mod_image_url( $mod );
	$category   = sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) );
	$side_label = sevendtd_nb_detect_mod_side_label( $mod );
	$tags       = array_merge(
		sevendtd_nb_extract_japanese_tags( $mod, 6 ),
		sevendtd_nb_detect_mod_side_tags( $mod )
	);
	$tags       = array_values( array_unique( array_filter( array_map( 'trim', $tags ) ) ) );
	$signature  = sevendtd_nb_build_mod_discussion_signature( $mod );
	$post_title = '' !== $title ? $title : 'Nexus MOD ' . $mod_id;

	$post_content = "Nexus MOD 議論ページです。\n\n";
	if ( '' !== $summary ) {
		$post_content .= $summary . "\n\n";
	}
	$post_content .= '作者: ' . ( '' !== $author ? $author : '不明' ) . "\n";
	if ( '' !== $version ) {
		$post_content .= 'バージョン: ' . $version . "\n";
	}
	if ( '' !== $updated ) {
		$post_content .= '更新日: ' . $updated . "\n";
	}
	$post_content .= '用途: ' . $side_label . "\n\n";
	if ( '' !== $category ) {
		$post_content .= 'カテゴリ: ' . $category . "\n";
	}
	if ( '' !== $mod_url ) {
		$post_content .= 'Nexus 原ページ: ' . $mod_url . "\n";
	}

	$post_id = sevendtd_nb_get_mod_discussion_post_id( $mod_id );
	if ( $post_id > 0 ) {
		$current_signature = (string) get_post_meta( $post_id, 'nexus_mod_signature', true );
		if ( $current_signature !== $signature ) {
			wp_update_post(
				array(
					'ID'           => $post_id,
					'post_title'   => $post_title,
					'post_content' => $post_content,
					'post_excerpt' => wp_trim_words( $summary, 28, '...' ),
				)
			);
			$GLOBALS['sevendtd_nb_sidebar_needs_sync'] = true;
		}
	} else {
		$post_id = (int) wp_insert_post(
			array(
				'post_type'      => 'sevendtd_nexus_mod',
				'post_status'    => 'publish',
				'post_title'     => $post_title,
				'post_name'      => sanitize_title( 'nexus-mod-' . $mod_id ),
				'post_content'   => $post_content,
				'post_excerpt'   => wp_trim_words( $summary, 28, '...' ),
				'comment_status' => 'open',
			)
		);
		if ( $post_id <= 0 ) {
			return 0;
		}
		$GLOBALS['sevendtd_nb_sidebar_needs_sync'] = true;
	}

	update_post_meta( $post_id, 'nexus_mod_id', $mod_id );
	update_post_meta( $post_id, 'nexus_mod_url', $mod_url );
	update_post_meta( $post_id, 'nexus_mod_author', $author );
	update_post_meta( $post_id, 'nexus_mod_version', $version );
	update_post_meta( $post_id, 'nexus_mod_updated_at', $updated );
	update_post_meta( $post_id, 'nexus_mod_category', $category );
	update_post_meta( $post_id, 'nexus_mod_image_url', $image_url );
	update_post_meta( $post_id, 'nexus_mod_description', wp_strip_all_tags( (string) $summary ) );
	update_post_meta( $post_id, 'nexus_mod_side', $side_label );
	update_post_meta( $post_id, 'nexus_mod_tags', array_slice( $tags, 0, 8 ) );
	update_post_meta( $post_id, 'nexus_mod_signature', $signature );

	// 前提MOD / 競合MOD（Nexus API が返すフィールドがある場合のみ保存）
	$requirements = sevendtd_nb_get_mod_value( $mod, array( 'requirements', 'required_mods', 'dependencies' ) );
	if ( '' !== $requirements ) {
		update_post_meta( $post_id, 'nexus_mod_requirements', wp_strip_all_tags( (string) $requirements ) );
	}
	$incompatible = sevendtd_nb_get_mod_value( $mod, array( 'incompatible_mods', 'incompatible', 'conflicts' ) );
	if ( '' !== $incompatible ) {
		update_post_meta( $post_id, 'nexus_mod_incompatible', wp_strip_all_tags( (string) $incompatible ) );
	}

	return $post_id;
}

/**
 * MOD 議論ページ URL を返す。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_get_mod_discussion_url( array $mod ) {
	$post_id = sevendtd_nb_upsert_mod_discussion_post( $mod );
	if ( $post_id <= 0 ) {
		return sevendtd_nb_get_mod_url( $mod );
	}

	$link = get_permalink( $post_id );
	if ( ! is_string( $link ) || '' === $link ) {
		return sevendtd_nb_get_mod_url( $mod );
	}

	return $link;
}

/**
 * MOD スナップショットを返す。
 *
 * @return array<string,array<string,mixed>>
 */
function sevendtd_nb_get_mod_snapshot_store() {
	$store = get_option( 'sevendtd_nb_mod_snapshot_store', array() );
	return is_array( $store ) ? $store : array();
}

/**
 * MOD スナップショットを保存する。
 *
 * @param array<string,array<string,mixed>> $store スナップショット.
 */
function sevendtd_nb_update_mod_snapshot_store( array $store ) {
	if ( count( $store ) > 1200 ) {
		$store = array_slice( $store, -1200, null, true );
	}

	update_option( 'sevendtd_nb_mod_snapshot_store', $store, false );
}

/**
 * MOD 差分ラベルを返す。
 *
 * @param array<string,mixed>               $mod   MOD データ.
 * @param array<string,array<string,mixed>> $store スナップショット.
 *
 * @return string
 */
function sevendtd_nb_get_mod_diff_label( array $mod, array $store ) {
	$key     = sevendtd_nb_get_mod_key( $mod );
	$current = array(
		'updated' => sevendtd_nb_get_mod_updated_label( $mod ),
		'version' => sevendtd_nb_get_mod_version_label( $mod ),
	);

	if ( ! isset( $store[ $key ] ) || ! is_array( $store[ $key ] ) ) {
		return '';
	}

	$prev         = $store[ $key ];
	$updated_diff = isset( $prev['updated'] ) && (string) $prev['updated'] !== $current['updated'];
	$version_diff = isset( $prev['version'] ) && (string) $prev['version'] !== $current['version'];

	if ( $version_diff ) {
		return 'バージョン更新';
	}

	if ( $updated_diff ) {
		return '更新日のみ変更';
	}

	return '';
}

/**
 * 日本語タグ辞書を返す。
 *
 * @return array<string,string>
 */
function sevendtd_nb_get_japanese_tag_dictionary() {
	return array(
		'total conversion' => '大型改変',
		'conversion'    => '大型改変',
		'overhaul'      => '大型改変',
		'quality of life' => '快適化',
		'qol'           => '快適化',
		'inventory'     => 'UI',
		'interface'     => 'UI',
		'backpack'      => 'UI',
		'loadout'       => 'UI',
		'ui'            => 'UI',
		'crosshair'     => 'HUD',
		'hud'           => 'HUD',
		'crafting'      => 'クラフト',
		'craft'         => 'クラフト',
		'recipes'       => 'クラフト',
		'recipe'        => 'クラフト',
		'foods'         => 'クラフト',
		'food'          => 'クラフト',
		'drinks'        => 'クラフト',
		'drink'         => 'クラフト',
		'smoothie'      => 'クラフト',
		'cook'          => 'クラフト',
		'cooking'       => 'クラフト',
		'vehicles'      => 'クラフト',
		'vehicle'       => 'クラフト',
		'truck'         => 'クラフト',
		'car'           => 'クラフト',
		'bike'          => 'クラフト',
		'uaz'           => 'クラフト',
		'weapons'       => '武器',
		'weapon'        => '武器',
		'melee'         => '武器',
		'brawler'       => '武器',
		'guns'          => '武器',
		'gun'           => '武器',
		'rifle'         => '武器',
		'pistol'        => '武器',
		'shotgun'       => '武器',
		'bow'           => '武器',
		'spear'         => '武器',
		'ammo'          => '武器',
		'server tools'  => 'サーバー向け',
		'server'        => 'サーバー向け',
		'server-side'   => 'サーバー向け',
		'serverside'    => 'サーバー向け',
		'dedicated'     => 'サーバー向け',
		'admin tool'    => 'サーバー向け',
		'client'        => 'クライアント向け',
		'client-side'   => 'クライアント向け',
		'clientside'    => 'クライアント向け',
		'optimization'  => '軽量化',
		'optimisation'  => '軽量化',
		'fps'           => '軽量化',
		'lag'           => '軽量化',
		'performance'   => '軽量化',
		'visual'        => 'グラフィック',
		'graphics'      => 'グラフィック',
		'weather'       => 'グラフィック',
		'lighting'      => 'グラフィック',
		'shader'        => 'グラフィック',
		'texture'       => 'グラフィック',
		'zombies'       => 'ゾンビ',
		'zombie'        => 'ゾンビ',
		'undead'        => 'ゾンビ',
		'horde'         => 'ゾンビ',
		'quests'        => 'クエスト',
		'quest'         => 'クエスト',
		'trader'        => 'クエスト',
		'mission'       => 'クエスト',
		'objective'     => 'クエスト',
		'buildings'     => '建築',
		'building'      => '建築',
		'prefabs'       => '建築',
		'prefab'        => '建築',
		'map'           => '建築',
		'world'         => '建築',
		'compatibility' => '互換性',
		'compatible'    => '互換性',
		'balanced'      => 'バランス調整',
		'balance'       => 'バランス調整',
		'progression'   => 'バランス調整',
		'perk'          => 'バランス調整',
		'perks'         => 'バランス調整',
		'skill'         => 'バランス調整',
		'skills'        => 'バランス調整',
		'loot'          => 'バランス調整',
		'economy'       => 'バランス調整',
	);
}

/**
 * 任意テキストから日本語タグ候補を抽出する。
 *
 * @param string $text 対象文字列.
 * @param int    $limit 最大件数.
 *
 * @return array<int,string>
 */
function sevendtd_nb_extract_japanese_tags_from_text( $text, $limit = 4 ) {
	$limit    = max( 1, absint( $limit ) );
	$haystack = sevendtd_safe_strtolower( (string) $text );
	if ( '' === trim( $haystack ) ) {
		return array();
	}

	$tags = array();
	foreach ( sevendtd_nb_get_japanese_tag_dictionary() as $keyword => $translated ) {
		if ( false === mb_strpos( $haystack, $keyword ) ) {
			continue;
		}
		if ( in_array( $translated, $tags, true ) ) {
			continue;
		}
		$tags[] = $translated;
		if ( count( $tags ) >= $limit ) {
			break;
		}
	}

	return $tags;
}

/**
 * 文字列に日本語が含まれるか返す。
 *
 * @param string $text 判定文字列.
 *
 * @return bool
 */
function sevendtd_nb_text_has_japanese( $text ) {
	return 1 === preg_match( '/[\p{Han}\p{Hiragana}\p{Katakana}]/u', (string) $text );
}

/**
 * category_id からカテゴリ名を引くための lookup を返す。
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_category_lookup_map() {
	static $lookup = null;
	if ( null !== $lookup ) {
		return $lookup;
	}

	$categories = sevendtd_nb_get_categories();
	$rows       = ( ! empty( $categories['ok'] ) && ! empty( $categories['data'] ) && is_array( $categories['data'] ) )
		? $categories['data']
		: array();

	$rows   = sevendtd_nb_merge_category_rows( $rows, sevendtd_nb_derive_categories_from_feed( sevendtd_nb_get_merged_feed_mods() ) );
	$lookup = array(
		'by_id' => array(),
		'rows'  => $rows,
	);

	foreach ( $rows as $row ) {
		if ( ! is_array( $row ) ) {
			continue;
		}
		$category_id = absint( isset( $row['category_id'] ) ? $row['category_id'] : 0 );
		$name        = trim( (string) ( isset( $row['name'] ) ? $row['name'] : ( isset( $row['category_name'] ) ? $row['category_name'] : '' ) ) );
		if ( $category_id > 0 && '' !== $name ) {
			$lookup['by_id'][ $category_id ] = $name;
		}
	}

	return $lookup;
}

/**
 * MOD のカテゴリ名を Discord 通知向けに補完する。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return string
 */
function sevendtd_nb_resolve_mod_category_label( array $mod ) {
	$candidates   = array();
	$raw_category = trim( sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) ) );
	if ( '' !== $raw_category ) {
		$candidates[] = $raw_category;
	}

	$category_id = absint( sevendtd_nb_get_mod_value( $mod, array( 'category_id', 'categoryid' ) ) );
	if ( $category_id > 0 ) {
		$lookup = sevendtd_nb_get_category_lookup_map();
		if ( isset( $lookup['by_id'][ $category_id ] ) ) {
			$candidates[] = (string) $lookup['by_id'][ $category_id ];
		}
	}

	foreach ( $candidates as $candidate ) {
		$candidate = trim( (string) $candidate );
		if ( '' === $candidate ) {
			continue;
		}
		if ( sevendtd_nb_text_has_japanese( $candidate ) ) {
			return $candidate;
		}
		$translated = sevendtd_nb_extract_japanese_tags_from_text( $candidate, 1 );
		if ( ! empty( $translated ) ) {
			return (string) $translated[0];
		}
	}

	$inferred = sevendtd_nb_extract_japanese_tags_from_text(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ),
		1
	);
	if ( ! empty( $inferred ) ) {
		return (string) $inferred[0];
	}

	$side_tags = sevendtd_nb_detect_mod_side_tags( $mod );
	if ( ! empty( $side_tags ) ) {
		return (string) $side_tags[0];
	}

	return '';
}

/**
 * MOD から日本語タグ候補を抽出する。
 *
 * @param array<string,mixed> $mod MOD データ.
 * @param int                 $limit 最大件数.
 *
 * @return array<int,string>
 */
function sevendtd_nb_extract_japanese_tags( array $mod, $limit = 4 ) {
	$limit = max( 1, absint( $limit ) );
	$tags  = sevendtd_nb_extract_japanese_tags_from_text(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) ),
		max( $limit, 6 )
	);

	$category = sevendtd_nb_resolve_mod_category_label( $mod );
	if ( '' !== $category ) {
		array_unshift( $tags, $category );
	}

	$tags = array_merge( $tags, sevendtd_nb_detect_mod_side_tags( $mod ) );
	$tags = array_values( array_unique( array_filter( array_map( 'trim', $tags ) ) ) );

	return array_slice( $tags, 0, $limit );
}

/**
 * MOD からサーバー/クライアント傾向タグを推定する。
 *
 * @param array<string,mixed> $mod MOD データ.
 *
 * @return array<int,string>
 */
function sevendtd_nb_detect_mod_side_tags( array $mod ) {
	$haystack = sevendtd_safe_strtolower(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) )
	);

	$server_terms = array( 'server', 'server-side', 'serverside', 'dedicated', 'admin tool' );
	$client_terms = array( 'client', 'client-side', 'clientside', 'hud', 'ui', 'texture', 'sound' );
	$tags         = array();

	foreach ( $server_terms as $term ) {
		if ( false !== mb_strpos( $haystack, $term ) ) {
			$tags[] = 'サーバー向け';
			break;
		}
	}

	foreach ( $client_terms as $term ) {
		if ( false !== mb_strpos( $haystack, $term ) ) {
			$tags[] = 'クライアント向け';
			break;
		}
	}

	return array_values( array_unique( $tags ) );
}

/**
 * 指定ゲームバージョンとの互換候補か判定する。
 *
 * @param array<string,mixed> $mod MOD データ.
 * @param string              $game_version ゲームバージョン.
 *
 * @return bool
 */
function sevendtd_nb_is_compatible_with_game_version( array $mod, $game_version ) {
	$game_version = trim( (string) $game_version );
	if ( '' === $game_version ) {
		return true;
	}

	$haystack = sevendtd_safe_strtolower(
		sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) ) . ' ' .
		sevendtd_nb_get_mod_value( $mod, array( 'version', 'mod_version' ) )
	);

	$terms = sevendtd_nb_expand_game_version_terms( $game_version );
	foreach ( $terms as $term ) {
		if ( false !== mb_strpos( $haystack, $term ) ) {
			return true;
		}
	}

	return false;
}

/**
 * プリセット検索定義を返す。
 *
 * @return array<string,array<string,string>>
 */
function sevendtd_nb_get_search_presets() {
	return array(
		'solo'     => array(
			'label' => 'ソロ向け',
			'query' => 'qol balance quest',
		),
		'hardcore' => array(
			'label' => '高難度向け',
			'query' => 'hardcore zombie difficulty',
		),
		'light_ui' => array(
			'label' => '軽量UI向け',
			'query' => 'ui hud performance',
		),
		'server_side' => array(
			'label' => 'サーバー向け',
			'query' => 'server dedicated admin tool',
		),
		'client_side' => array(
			'label' => 'クライアント向け',
			'query' => 'client ui hud texture sound',
		),
		'overhaul' => array(
			'label' => '大型改変',
			'query' => 'overhaul conversion',
		),
		'qol_focus' => array(
			'label' => '快適化',
			'query' => 'qol quality of life balance',
		),
	);
}

/**
 * フィード名の表示ラベルを返す。
 *
 * @param string $source フィード名.
 *
 * @return string
 */
function sevendtd_nb_get_source_label( $source ) {
	$map = array(
		'latest_updated' => '最新更新',
		'latest_added'   => '新着',
		'trending'       => 'トレンド',
	);

	return isset( $map[ $source ] ) ? $map[ $source ] : '最新更新';
}

/**
 * ページ表示と通知で共通利用する既定 feed を返す。
 *
 * @param string $source フィード種別.
 * @param int    $limit  最大件数.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_default_feed_result( $source = 'latest_updated', $limit = 12 ) {
	$settings = sevendtd_nb_get_settings();
	$source   = sanitize_key( (string) $source );
	$limit    = max( 1, min( 50, absint( $limit ) ) );

	if ( ! in_array( $source, array( 'latest_updated', 'latest_added', 'trending' ), true ) ) {
		$source = 'latest_updated';
	}

	$sorts = array(
		'latest_updated' => array( array( 'updatedAt' => array( 'direction' => 'DESC' ) ) ),
		'latest_added'   => array( array( 'createdAt' => array( 'direction' => 'DESC' ) ) ),
		'trending'       => array( array( 'endorsements' => array( 'direction' => 'DESC' ) ) ),
	);

	$result = sevendtd_nb_gql_fetch_mods(
		array(),
		$sorts[ $source ],
		$limit,
		'sevendtd_nb_gql_direct_' . $source,
		(int) $settings['cache_ttl']
	);

	if ( ! empty( $result['ok'] ) && ! empty( $result['data'] ) && is_array( $result['data'] ) ) {
		return array(
			'ok'       => true,
			'data'     => array_slice( $result['data'], 0, $limit ),
			'source'   => $source,
			'fallback' => false,
		);
	}

	return array(
		'ok'       => true,
		'data'     => array_slice( sevendtd_nb_get_merged_feed_mods(), 0, $limit ),
		'source'   => $source,
		'fallback' => true,
		'message'  => '既定フィードの取得に失敗したため、統合キャッシュから表示しています。',
	);
}

/**
 * MOD 概要文の元テキストを返す。
 *
 * @param array<string,mixed> $mod   MOD データ.
 * @param int                 $limit 最大文字数.
 *
 * @return string
 */
function sevendtd_nb_cleanup_mod_summary_text( $text ) {
	$text = html_entity_decode( (string) $text, ENT_QUOTES | ENT_HTML5, 'UTF-8' );
	$text = preg_replace( '/\[(?:\/?[a-z*][^\]\n]{0,80})\]/iu', ' ', $text );
	$text = wp_strip_all_tags( $text );
	$text = preg_replace( "/\r\n|\r/u", "\n", (string) $text );
	$text = preg_replace( "/[ \t]+/u", ' ', (string) $text );
	$text = preg_replace( "/\n{3,}/u", "\n\n", (string) $text );

	return trim( (string) $text );
}

/**
 * MOD 概要文の元テキストを返す。
 *
 * @param array<string,mixed> $mod   MOD データ.
 * @param int                 $limit 最大文字数.
 *
 * @return string
 */
function sevendtd_nb_get_mod_summary_source_text( array $mod, $limit = 1200 ) {
	$best = '';
	$keys = array( 'description', 'summary', 'mod_description', 'mod_summary' );

	foreach ( $keys as $key ) {
		if ( ! isset( $mod[ $key ] ) || is_array( $mod[ $key ] ) ) {
			continue;
		}

		$candidate = sevendtd_nb_cleanup_mod_summary_text( $mod[ $key ] );
		if ( '' === $candidate ) {
			continue;
		}

		if ( mb_strlen( $candidate ) > mb_strlen( $best ) ) {
			$best = $candidate;
		}
	}

	$max_length = max( 0, absint( $limit ) );
	if ( $max_length > 0 && mb_strlen( $best ) > $max_length ) {
		return trim( mb_substr( $best, 0, max( 1, $max_length - 1 ) ) ) . '…';
	}

	return $best;
}

/**
 * Discord 通知向けに日本語優先の概要文を組み立てる。
 *
 * @param array<string,mixed> $mod      MOD データ.
 * @param string              $category 表示カテゴリ.
 * @param array<int,string>   $tags_ja  日本語タグ.
 *
 * @return string
 */
function sevendtd_nb_build_watch_summary( array $mod, $category = '', array $tags_ja = array() ) {
	$source_text   = sevendtd_nb_get_mod_summary_source_text( $mod, 1200 );
	$summary_parts = array();
	$detail_lines  = array();
	$category      = trim( (string) $category );
	$tags_ja       = array_values( array_filter( array_map( 'trim', $tags_ja ) ) );
	$author        = sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) );
	$version       = sevendtd_nb_get_mod_version_label( $mod );
	$downloads     = sevendtd_nb_get_mod_downloads( $mod );
	$endorsements  = sevendtd_nb_get_mod_endorsements( $mod );

	if ( '' !== $category ) {
		$detail_lines[] = 'カテゴリは「' . $category . '」です。';
	}
	if ( ! empty( $tags_ja ) ) {
		$detail_lines[] = '主な注目ポイントは ' . implode( ' / ', array_slice( $tags_ja, 0, 4 ) ) . ' です。';
	}
	if ( '' !== $author ) {
		$detail_lines[] = '作者は ' . $author . ' です。';
	}
	if ( '' !== $version ) {
		$detail_lines[] = '現在確認できるバージョンは ' . $version . ' です。';
	}
	if ( $downloads > 0 || $endorsements > 0 ) {
		$detail_lines[] = 'Nexus 指標はダウンロード ' . number_format_i18n( $downloads ) . ' 件、Endorse ' . number_format_i18n( $endorsements ) . ' 件です。';
	}

	if ( '' !== $source_text ) {
		if ( sevendtd_nb_text_has_japanese( $source_text ) ) {
			$summary_parts[] = $source_text;
		} else {
			$translated_text = sevendtd_nb_translate_to_japanese( $source_text );
			if ( '' !== $translated_text ) {
				$summary_parts[] = $translated_text;
			} else {
				if ( ! empty( $detail_lines ) ) {
					$summary_parts[] = implode( ' ', $detail_lines );
					$detail_lines    = array();
				}
				$summary_parts[] = '原文概要: ' . $source_text;
			}
		}
	}

	if ( ! empty( $detail_lines ) ) {
		$summary_parts[] = implode( ' ', $detail_lines );
	}

	if ( empty( $summary_parts ) ) {
		return '紹介文はまだ取得できていません。';
	}

	$summary = trim( implode( "\n\n", array_filter( $summary_parts ) ) );
	if ( mb_strlen( $summary ) > 1800 ) {
		$summary = trim( mb_substr( $summary, 0, 1799 ) ) . '…';
	}

	return $summary;
}

/**
 * Discord 通知向けの MOD 項目へ正規化する。
 *
 * @param array<string,mixed> $mod    MOD データ.
 * @param array<string,mixed> $store  差分ストア.
 * @param string              $source 取得元フィード.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_normalize_watch_item( array $mod, array $store, $source = 'latest_updated' ) {
	$score = sevendtd_nb_get_mod_score( $mod );
	$title = sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) );
	$title = '' !== $title ? $title : '名称未取得の MOD';
	$category = sevendtd_nb_resolve_mod_category_label( $mod );
	$tags_ja  = sevendtd_nb_extract_japanese_tags( $mod, 4 );
	$summary  = sevendtd_nb_build_watch_summary( $mod, $category, $tags_ja );

	return array(
		'id'           => sevendtd_nb_get_mod_key( $mod ),
		'title'        => $title,
		// Discord導線をWPベースページへ向ける。get_mod_discussion_url が
		// 議論ページ(ベースページ)を upsert で自動生成し、その permalink を返す。
		// Nexus 原ページは nexus_url に分離(WPページ側に導線あり)。
		'url'          => sevendtd_nb_get_mod_discussion_url( $mod ),
		'nexus_url'    => sevendtd_nb_get_mod_url( $mod ),
		'score'        => $score,
		'badge'        => sevendtd_nb_get_mod_score_badge( $mod, $score ),
		'diff'         => sevendtd_nb_get_mod_diff_label( $mod, $store ),
		'updated_at'   => sevendtd_nb_get_mod_updated_label( $mod ),
		'updated_ts'   => sevendtd_nb_get_mod_updated_timestamp( $mod ),
		'downloads'    => sevendtd_nb_get_mod_downloads( $mod ),
		'endorsements' => sevendtd_nb_get_mod_endorsements( $mod ),
		'category'     => $category,
		'tags_ja'      => $tags_ja,
		'author'       => sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) ),
		'version'      => sevendtd_nb_get_mod_version_label( $mod ),
		'summary'      => $summary,
		'image_url'    => sevendtd_nb_get_mod_image_url( $mod ),
		'source'       => sanitize_key( (string) $source ),
	);
}

/**
 * Discord 通知向けに page 準拠の候補一覧を返す。
 *
 * @param array<string,mixed> $args 条件.
 *
 * @return array<string,mixed>
 */
function sevendtd_nb_get_discord_watch_items( array $args = array() ) {
	$settings      = sevendtd_nb_get_settings();
	$limit_default = isset( $settings['discord_notify_limit'] ) ? absint( $settings['discord_notify_limit'] ) : 10;
	$limit         = max( 1, min( 50, absint( isset( $args['limit'] ) ? $args['limit'] : $limit_default ) ) );
	$source        = isset( $args['source'] ) ? sanitize_key( (string) $args['source'] ) : 'latest_updated';
	$feed_result   = sevendtd_nb_get_default_feed_result( $source, $limit );
	$mods          = ! empty( $feed_result['data'] ) && is_array( $feed_result['data'] ) ? $feed_result['data'] : array();
	$store         = sevendtd_nb_get_mod_snapshot_store();
	$items         = array();

	foreach ( $mods as $mod ) {
		if ( ! is_array( $mod ) ) {
			continue;
		}

		$items[] = sevendtd_nb_normalize_watch_item( $mod, $store, $feed_result['source'] );
	}

	return array(
		'ok'            => true,
		'generated_at'  => gmdate( 'c' ),
		'count'         => count( $items ),
		'source'        => $feed_result['source'],
		'fallback'      => ! empty( $feed_result['fallback'] ),
		'message'       => isset( $feed_result['message'] ) ? (string) $feed_result['message'] : '',
		'items'         => $items,
	);
}

/**
 * カテゴリ件数マップを返す。
 *
 * @param array<int,array<string,mixed>> $mods MOD 配列.
 *
 * @return array<int,int>
 */
function sevendtd_nb_get_category_counts_from_feed( array $mods ) {
	$counts = array();

	foreach ( $mods as $mod ) {
		$category_id = absint( sevendtd_nb_get_mod_value( $mod, array( 'category_id', 'categoryid' ) ) );
		if ( $category_id <= 0 ) {
			continue;
		}

		if ( ! isset( $counts[ $category_id ] ) ) {
			$counts[ $category_id ] = 0;
		}

		++$counts[ $category_id ];
	}

	return $counts;
}

/**
 * 共有スタイルを一度だけ出力する。
 *
 * @return string
 */
function sevendtd_nb_get_shared_styles() {
	static $printed = false;

	if ( $printed ) {
		return '';
	}

	$printed = true;

	return '<style>
	.sevendtd-nexus-box{border:1px solid #d8dfd9;border-radius:16px;background:#fbfcfb;padding:16px;margin:18px 0;box-shadow:0 12px 28px rgba(22,36,28,.05)}
	.sevendtd-nexus-box h2,.sevendtd-nexus-box h3{margin:0 0 10px;color:#1e4c3c}
	.sevendtd-nexus-form{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(180px,.65fr) minmax(150px,.5fr) auto;gap:10px;align-items:end;margin:0 0 14px}
	.sevendtd-nexus-form label{display:block;font-size:12px;font-weight:700;color:#406255;margin:0 0 4px}
	.sevendtd-nexus-form input:not([type="checkbox"]):not([type="radio"]),.sevendtd-nexus-form select{width:100%;border:1px solid #c9d7cf;border-radius:10px;padding:10px 12px;background:#fff;box-sizing:border-box}
	.sevendtd-nexus-inline-check{grid-column:1/-1;display:flex;align-items:center;justify-content:flex-end}
	.sevendtd-nexus-inline-check label{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:#406255;margin:0}
	.sevendtd-nexus-inline-check input[type="checkbox"]{width:16px;height:16px;margin:0}
	.sevendtd-nexus-form button{border:0;border-radius:999px;padding:11px 18px;background:#1e4c3c;color:#fff;font-weight:700;cursor:pointer}
	.sevendtd-nexus-muted{color:#61766d;font-size:13px;margin:0 0 12px}
	.sevendtd-nexus-notice{margin:0 0 12px;padding:10px 12px;border-radius:10px;background:#eef6f2;color:#315546;font-size:13px}
	.sevendtd-nexus-result-summary{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
	.sevendtd-nexus-pill{display:inline-block;background:#ecf4ef;color:#2b5d49;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700}
	.sevendtd-nexus-pill-strong{background:#e4f0ff;color:#1e4f8a}
	.sevendtd-nexus-pill-diff{background:#fff2dd;color:#8a4e00}
	.sevendtd-nexus-pill-score{background:#e8f8ea;color:#1e6b2b}
	.sevendtd-nexus-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
	.sevendtd-nexus-card{border:1px solid #dde6e0;border-radius:14px;padding:14px;background:#fff}
	.sevendtd-nexus-card-header{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}
	.sevendtd-nexus-card-cover{display:block;width:100%;height:132px;border-radius:10px;object-fit:cover;background:#eef3f0;margin:0 0 10px}
	.sevendtd-nexus-card-title{font-size:18px;line-height:1.35;margin:0 0 8px}
	.sevendtd-nexus-card-title a{text-decoration:none;color:#153d31}
	.sevendtd-nexus-card p{margin:0 0 10px;color:#4f635b;font-size:14px}
	.sevendtd-nexus-meta{display:grid;gap:6px;font-size:13px;color:#546961;margin:0 0 10px}
	.sevendtd-nexus-meta-inline{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 8px}
	.sevendtd-nexus-indicators{display:flex;gap:12px;justify-content:flex-start;font-size:12px;color:#4f635b;margin:0 0 8px}
	.sevendtd-nexus-indicator{display:flex;align-items:center;gap:4px}
	.sevendtd-nexus-indicator-icon{width:14px;height:14px;line-height:14px;text-align:center;font-size:11px}
	.sevendtd-nexus-actions{display:flex;flex-wrap:wrap;align-items:center;gap:6px 4px}
	.sevendtd-nexus-actions a{display:inline-block;color:#1e4c3c;font-weight:700;text-decoration:none;border-bottom:1px solid currentColor}
	.sevendtd-nexus-action-primary{background:#1e4c3c;color:#fff !important;padding:6px 12px;border-radius:999px;border-bottom:none !important}
	.sevendtd-nexus-action-primary:hover{background:#2a6a52}
	.sevendtd-nexus-action-sep{color:#9fb4aa}
	.sevendtd-nexus-summary{margin:8px 0;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
	.sevendtd-nexus-preset-row{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
	.sevendtd-nexus-preset-row a{display:inline-block;padding:6px 10px;border:1px solid #c8d8cf;border-radius:999px;background:#fff;text-decoration:none;color:#1e4c3c;font-size:12px;font-weight:700}
	.sevendtd-nexus-memo{margin-top:10px}
	.sevendtd-nexus-memo button{border:1px dashed #95afa2;background:#f5f8f6;color:#23463a;border-radius:8px;padding:6px 8px;font-size:12px;cursor:pointer}
	.sevendtd-nexus-category-list{display:grid;gap:18px}
	.sevendtd-nexus-category-block{padding-top:6px;border-top:1px solid #e3e9e5}
	.sevendtd-nexus-category-details{border:1px solid #dde5df;border-radius:12px;background:#fff;padding:0}
	.sevendtd-nexus-category-summary{cursor:pointer;list-style:none;padding:12px 14px;font-weight:700;display:flex;justify-content:space-between;gap:8px;align-items:center;color:#1f4d3d}
	.sevendtd-nexus-category-block:first-child{padding-top:0;border-top:0}
	.sevendtd-nexus-category-body{padding:0 14px 14px}
	.sevendtd-nexus-discussion-summary{display:grid;gap:10px;margin:0 0 12px}
	.sevendtd-nexus-discussion-meta{display:flex;gap:8px;flex-wrap:wrap}
	.sevendtd-nexus-discussion-cover{display:block;width:100%;max-width:520px;min-height:180px;max-height:320px;object-fit:cover;border-radius:12px;border:1px solid #dbe5df;background:#eef3f0;margin:0 0 10px}
	.sevendtd-nexus-discussion-tags{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
	.sevendtd-nexus-discussion-actions{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 0}
	.sevendtd-nexus-discussion-btn{display:inline-block;padding:9px 14px;border-radius:999px;text-decoration:none;font-weight:700;border:1px solid #b9cfc2;color:#1e4c3c;background:#f7fbf8}
	.sevendtd-nexus-discussion-btn-primary{background:#1e4c3c;border-color:#1e4c3c;color:#fff}
	.sevendtd-nexus-reaction-summary{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0}
	.sevendtd-nexus-comment-reaction{display:inline-block;padding:2px 8px;border-radius:999px;background:#e8f3ee;color:#1e4c3c;font-size:12px;font-weight:700;margin:0 6px 0 0}
	.sevendtd-nexus-reaction-recommended{background:#e8f8e8;color:#1f6c2f}
	.sevendtd-nexus-reaction-interested{background:#fff3dc;color:#845100}
	.sevendtd-nexus-reaction-installed{background:#e6f8e8;color:#1f6c2f}
	.sevendtd-nexus-reaction-testing{background:#e6f0ff;color:#1f4d8f}
	.sevendtd-nexus-reaction-caution{background:#ffe8e8;color:#8a2121}
	.sevendtd-nexus-discussion-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
	.sevendtd-nexus-discussion-card{border:1px solid #dde6e0;border-radius:12px;background:#fff;padding:12px}
	.sevendtd-nexus-discussion-card h3{font-size:17px;margin:0 0 8px}
	.sevendtd-nexus-discussion-card h3 a{text-decoration:none;color:#153d31}
	.sevendtd-nexus-discussion-card p{margin:0 0 8px;color:#4f635b;font-size:14px}
	.sevendtd-nexus-discussion-sort{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
	.sevendtd-nexus-discussion-sort .is-active{background:#1e4c3c;color:#fff;border-color:#1e4c3c}
	.comment-form-sevendtd-reaction{margin:10px 0}
	.comment-form-sevendtd-reaction label{display:block;font-weight:700;margin:0 0 4px}
	.comment-form-sevendtd-reaction select{min-width:180px;padding:8px 10px;border:1px solid #c9d7cf;border-radius:8px}
	.sevendtd-nexus-desc-raw{margin:0.8em 0 0;border:1px solid #dde6e0;border-radius:8px;padding:8px 12px;font-size:13px;color:#4f635b}
	.sevendtd-nexus-desc-raw summary{cursor:pointer;color:#1e4c3c;font-weight:700}
	.sevendtd-nexus-checklist-box{border-left:3px solid #e0a000}
	@media (max-width: 720px){.sevendtd-nexus-form{grid-template-columns:1fr}}
	</style>';
}

/**
 * 導入メモ用のスクリプトを一度だけ出力する。
 *
 * @return string
 */
function sevendtd_nb_get_shared_scripts() {
	static $printed = false;

	if ( $printed ) {
		return '';
	}

	$printed = true;

	return '<script>
	(function(){
		if (window.sevendtdMemoBound) return;
		window.sevendtdMemoBound = true;
		var STATES = ["未設定", "入れた", "検証中", "外した"];
		function key(modId){ return "sevendtd_mod_memo_" + modId; }
		function apply(btn){
			var modId = btn.getAttribute("data-mod-id");
			if (!modId) return;
			var state = localStorage.getItem(key(modId)) || STATES[0];
			btn.textContent = "導入メモ: " + state;
		}
		document.addEventListener("click", function(e){
			var btn = e.target.closest(".sevendtd-nexus-memo-btn");
			if (!btn) return;
			var modId = btn.getAttribute("data-mod-id");
			if (!modId) return;
			var current = localStorage.getItem(key(modId)) || STATES[0];
			var next = STATES[(STATES.indexOf(current) + 1) % STATES.length];
			localStorage.setItem(key(modId), next);
			apply(btn);
		});
		document.querySelectorAll(".sevendtd-nexus-memo-btn").forEach(apply);
	})();
	</script>';
}

/**
 * MOD カード群を描画する。
 *
 * @param array<int,array<string,mixed>> $mods MOD 配列.
 * @param array<string,mixed>            $args 表示オプション.
 *
 * @return string
 */
function sevendtd_nb_render_mod_cards( array $mods, array $args = array() ) {
	$args = array_merge(
		array(
			'show_image'   => true,
			'compact_meta' => false,
			'game_version' => '',
		),
		$args
	);

	if ( empty( $mods ) ) {
		return '<p class="sevendtd-nexus-muted">表示できる MOD がありません。</p>';
	}

	$items          = array();
	$snapshot_store = sevendtd_nb_get_mod_snapshot_store();
	$store_changed  = false;

	foreach ( $mods as $mod ) {
		if ( ! sevendtd_nb_is_compatible_with_game_version( $mod, (string) $args['game_version'] ) ) {
			continue;
		}

		$title           = sevendtd_nb_get_mod_value( $mod, array( 'name', 'title' ) );
		$summary         = sevendtd_nb_get_mod_value( $mod, array( 'summary', 'description' ) );
		$author          = sevendtd_nb_get_mod_value( $mod, array( 'author', 'uploaded_by', 'user' ) );
		$category        = sevendtd_nb_get_mod_value( $mod, array( 'category_name', 'category' ) );
		$updated         = sevendtd_nb_get_mod_updated_label( $mod );
		$version         = sevendtd_nb_get_mod_version_label( $mod );
		$mod_url         = sevendtd_nb_get_mod_url( $mod );
		$image           = sevendtd_nb_get_mod_image_url( $mod );
		$title           = '' !== $title ? $title : '名称未取得の MOD';
		$summary_en      = $summary;
		// 日本語サマリーは手書き解説記事の抜粋を正本にする（機械翻訳は使わない）。
		$mod_id_str      = (string) sevendtd_nb_get_mod_value( $mod, array( 'mod_id', 'id' ) );
		$article_id      = sevendtd_nb_get_linked_article_id( $mod_id_str );
		$article_excerpt = $article_id > 0 ? trim( wp_strip_all_tags( get_the_excerpt( $article_id ) ) ) : '';
		if ( '' !== $article_excerpt ) {
			$summary       = mb_strimwidth( $article_excerpt, 0, 140, '…', 'UTF-8' );
			$summary_is_ja = true;
		} elseif ( '' !== $summary_en ) {
			$summary       = wp_trim_words( $summary_en, 28, '...' );
			$summary_is_ja = false;
		} else {
			$summary       = '紹介文はまだ取得できていません。';
			$summary_is_ja = false;
		}
		$mod_key         = sevendtd_nb_get_mod_key( $mod );
		$score           = sevendtd_nb_get_mod_score( $mod );
		$score_badge     = sevendtd_nb_get_mod_score_badge( $mod, $score );
		$diff_badge      = sevendtd_nb_get_mod_diff_label( $mod, $snapshot_store );
		$translated_tags = sevendtd_nb_extract_japanese_tags( $mod, 4 );
		$side_tags       = sevendtd_nb_detect_mod_side_tags( $mod );

		$meta_rows = array();
		if ( '' !== $author ) {
			$meta_rows[] = '<div><strong>作者:</strong> ' . esc_html( $author ) . '</div>';
		}
		if ( '' !== $category ) {
			$meta_rows[] = '<div><strong>カテゴリ:</strong> ' . esc_html( $category ) . '</div>';
		}
		if ( '' !== $version ) {
			$meta_rows[] = '<div><strong>バージョン:</strong> ' . esc_html( $version ) . '</div>';
		}
		if ( '' !== $updated ) {
			$meta_rows[] = '<div><strong>更新日:</strong> ' . esc_html( $updated ) . '</div>';
		}

		$inline_meta = array();
		if ( '' !== $category ) {
			$inline_meta[] = '<span class="sevendtd-nexus-pill">' . esc_html( $category ) . '</span>';
		}
		if ( '' !== $version ) {
			$inline_meta[] = '<span class="sevendtd-nexus-pill">v' . esc_html( $version ) . '</span>';
		}

		$downloads    = sevendtd_nb_get_mod_downloads( $mod );
		$endorsements = sevendtd_nb_get_mod_endorsements( $mod );

		$indicators_html = '';
		if ( $downloads > 0 || $endorsements > 0 ) {
			$indicators_html = '<div class="sevendtd-nexus-indicators">';
			if ( $downloads > 0 ) {
				$indicators_html .= '<span class="sevendtd-nexus-indicator"><span class="sevendtd-nexus-indicator-icon">⬇️</span><span>' . esc_html( number_format( $downloads ) ) . '</span></span>';
			}
			if ( $endorsements > 0 ) {
				$indicators_html .= '<span class="sevendtd-nexus-indicator"><span class="sevendtd-nexus-indicator-icon">👍</span><span>' . esc_html( number_format( $endorsements ) ) . '</span></span>';
			}
			$indicators_html .= '</div>';
		}

		$cover_html = '';
		if ( ! empty( $args['show_image'] ) && '' !== $image ) {
			$cover_html = '<img class="sevendtd-nexus-card-cover" src="' . esc_url( $image ) . '" alt="' . esc_attr( $title ) . '">';
		}

		$meta_html = ! empty( $args['compact_meta'] )
			? '<div class="sevendtd-nexus-meta-inline">' . implode( '', $inline_meta ) . '</div>'
			: '<div class="sevendtd-nexus-meta">' . implode( '', $meta_rows ) . '</div>';

		$header_badges = array();
		if ( '' !== $score_badge ) {
			$header_badges[] = '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">' . esc_html( $score_badge ) . ' / ' . esc_html( (string) $score ) . '</span>';
		}
		if ( '' !== $diff_badge ) {
			$header_badges[] = '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-diff">' . esc_html( $diff_badge ) . '</span>';
		}
		foreach ( $translated_tags as $tag ) {
			$header_badges[] = '<span class="sevendtd-nexus-pill">' . esc_html( $tag ) . '</span>';
		}
		foreach ( $side_tags as $tag ) {
			$header_badges[] = '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-strong">' . esc_html( $tag ) . '</span>';
		}

		$header_badges_html = ! empty( $header_badges ) ? '<div class="sevendtd-nexus-card-header">' . implode( '', $header_badges ) . '</div>' : '';

		$memo_html      = '<div class="sevendtd-nexus-memo"><button type="button" class="sevendtd-nexus-memo-btn" data-mod-id="' . esc_attr( $mod_key ) . '">導入メモ: 未設定</button></div>';
		$discussion_url = sevendtd_nb_get_mod_discussion_url( $mod );

		// 概要は日本語で掴ませ、Nexus へは「記事 → 議論ページ → 原ページ」の順に誘導する（$article_id は上で算出済み）。
		$actions = array();
		if ( $article_id > 0 ) {
			$actions[] = '<a class="sevendtd-nexus-action-primary" href="' . esc_url( get_permalink( $article_id ) ) . '">📝 日本語解説を読む</a>';
		}
		$actions[] = '<a href="' . esc_url( $discussion_url ) . '">このMODを語る</a>';
		// Nexus 原ページへはカードタイトルがリンク済みのため、アクション側の重複リンクは省略。
		$actions_html = '<div class="sevendtd-nexus-actions">' . implode( '<span class="sevendtd-nexus-action-sep"> / </span>', $actions ) . '</div>';

		// 記事抜粋（日本語）を表示しているときは Nexus 原文を title 属性で添える（透明性のため）。
		$summary_attr = ( ! empty( $summary_is_ja ) && '' !== $summary_en ) ? ' title="' . esc_attr( wp_trim_words( $summary_en, 40, '...' ) ) . '"' : '';

		$items[] = '<article class="sevendtd-nexus-card">'
			. $cover_html
			. $header_badges_html
			. '<h3 class="sevendtd-nexus-card-title"><a href="' . esc_url( $mod_url ) . '" target="_blank" rel="noopener noreferrer">' . esc_html( $title ) . '</a></h3>'
			. ( ! empty( $args['compact_meta'] ) ? $meta_html : '' )
			. '<p class="sevendtd-nexus-summary"' . $summary_attr . '>' . esc_html( $summary ) . '</p>'
			. $indicators_html
			. $actions_html
			. $memo_html
			. '</article>';

		$snapshot_store[ $mod_key ] = array(
			'updated'  => $updated,
			'version'  => $version,
			'score'    => $score,
			'saved_at' => time(),
		);
		$store_changed              = true;
	}

	if ( $store_changed ) {
		sevendtd_nb_update_mod_snapshot_store( $snapshot_store );
	}

	if ( empty( $items ) ) {
		return '<p class="sevendtd-nexus-muted">条件に一致する MOD がありません。</p>';
	}

	return '<div class="sevendtd-nexus-grid">' . implode( '', $items ) . '</div>' . sevendtd_nb_get_shared_scripts();
}

/**
 * 現在ユーザーが Nexus 系ツールの利用条件を満たすか返す。
 *
 * 管理者は常に許可し、それ以外は Nexus アカウント連携済みのみ許可する。
 *
 * @return bool
 */
function sevendtd_nb_current_user_can_use_tools() {
	if ( current_user_can( 'manage_options' ) ) {
		return true;
	}

	if ( ! is_user_logged_in() ) {
		return false;
	}

	$account = sevendtd_nb_get_user_nexus_account( get_current_user_id() );
	return '' !== (string) $account['username'];
}

/**
 * Nexus 系ツールの利用案内メッセージを返す。
 *
 * @param string $label 表示ラベル.
 *
 * @return string
 */
function sevendtd_nb_render_tool_access_notice( $label = 'この機能' ) {
	$label = trim( (string) $label );
	if ( '' === $label ) {
		$label = 'この機能';
	}

	if ( ! is_user_logged_in() ) {
		return '<div class="sevendtd-nexus-notice">' . esc_html( $label ) . 'を利用するには <a href="' . esc_url( wp_login_url( get_permalink() ) ) . '">ログイン</a> が必要です。</div>';
	}

	return '<div class="sevendtd-nexus-notice">' . esc_html( $label ) . 'は Nexus連携 (Platinum) ユーザー向けです。<a href="' . esc_url( home_url( '/community/account-link/' ) ) . '">アカウント連携ページ</a>で Nexus Mods アカウントを登録してください。</div>';
}

/**
 * 検索ショートコードを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_mod_search_shortcode( $atts ) {
	$atts = shortcode_atts(
		array(
			'title'                => 'Nexus Mods 検索',
			'per_page'             => 12,
			'source'               => 'latest_updated',
			'show_source_selector' => 1,
		),
		$atts,
		'sevendtd_nexus_mod_search'
	);

	if ( ! sevendtd_nb_current_user_can_use_tools() ) {
		return sevendtd_nb_render_tool_access_notice( 'Nexus Mods 検索' );
	}

	$has_request = isset( $_GET['nb_mod_query'] ) || isset( $_GET['nb_mod_category'] ) || isset( $_GET['nb_my_mods'] );
	$nonce_valid = false;

	if ( $has_request && isset( $_GET['nb_mod_nonce'] ) ) {
		$nonce_valid = wp_verify_nonce( sanitize_text_field( wp_unslash( (string) $_GET['nb_mod_nonce'] ) ), 'sevendtd_nb_front_search' );
	}

	$query              = $nonce_valid && isset( $_GET['nb_mod_query'] ) ? sanitize_text_field( wp_unslash( (string) $_GET['nb_mod_query'] ) ) : '';
	$category_id        = $nonce_valid && isset( $_GET['nb_mod_category'] ) ? absint( wp_unslash( (string) $_GET['nb_mod_category'] ) ) : 0;
	$requested_source   = $nonce_valid && isset( $_GET['nb_mod_source'] ) ? sanitize_key( (string) wp_unslash( $_GET['nb_mod_source'] ) ) : '';
	$game_version       = $nonce_valid && isset( $_GET['nb_game_version'] ) ? sanitize_text_field( wp_unslash( (string) $_GET['nb_game_version'] ) ) : '';
	$preset_key         = $nonce_valid && isset( $_GET['nb_preset'] ) ? sanitize_key( (string) wp_unslash( $_GET['nb_preset'] ) ) : '';
	$filter_my_mods     = $nonce_valid && isset( $_GET['nb_my_mods'] ) && '1' === (string) $_GET['nb_my_mods'];
	$per_page           = max( 1, min( 24, absint( $atts['per_page'] ) ) );
	$source             = sanitize_key( (string) $atts['source'] );
	$source             = in_array( $requested_source, array( 'latest_updated', 'latest_added', 'trending' ), true ) ? $requested_source : $source;
	$show_source_select = absint( $atts['show_source_selector'] ) > 0;
	$presets            = sevendtd_nb_get_search_presets();

	if ( '' !== $preset_key && isset( $presets[ $preset_key ] ) ) {
		$query = (string) $presets[ $preset_key ]['query'];
	}

	$category_result = sevendtd_nb_get_categories();
	$categories      = ! empty( $category_result['data'] ) && is_array( $category_result['data'] ) ? $category_result['data'] : array();

	if ( '' !== $query || $category_id > 0 ) {
		$result = sevendtd_nb_search_mods( $query, $category_id, $per_page );
	} else {
		$result = sevendtd_nb_get_default_feed_result( $source, $per_page );
	}

	$options_html = '<option value="0">すべてのカテゴリ</option>';
	foreach ( $categories as $category ) {
		$option_id     = absint( isset( $category['category_id'] ) ? $category['category_id'] : 0 );
		$option_name   = isset( $category['name'] ) ? (string) $category['name'] : (string) $category['category_name'];
		$options_html .= '<option value="' . esc_attr( (string) $option_id ) . '"' . selected( $category_id, $option_id, false ) . '>' . esc_html( $option_name ) . '</option>';
	}

	$source_options = array(
		'latest_updated' => '最新更新',
		'latest_added'   => '新着',
		'trending'       => 'トレンド',
	);

	$source_options_html = '';
	foreach ( $source_options as $value => $label ) {
		$source_options_html .= '<option value="' . esc_attr( $value ) . '"' . selected( $source, $value, false ) . '>' . esc_html( $label ) . '</option>';
	}

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';
	$output .= '<p class="sevendtd-nexus-muted">MOD 名、作者名、紹介文の一部から検索できます。差分ハイライトと導入判断スコアを表示します。</p>';
	$output .= '<div class="sevendtd-nexus-preset-row">';
	foreach ( $presets as $preset_slug => $preset ) {
		$preset_url = add_query_arg(
			array(
				'nb_mod_nonce'  => wp_create_nonce( 'sevendtd_nb_front_search' ),
				'nb_preset'     => $preset_slug,
				'nb_mod_source' => $source,
			),
			remove_query_arg( array( 'nb_mod_query', 'nb_mod_category', 'nb_game_version' ) )
		);
		$output    .= '<a href="' . esc_url( $preset_url ) . '">' . esc_html( (string) $preset['label'] ) . '</a>';
	}
	$output .= '</div>';
	$output .= '<form class="sevendtd-nexus-form" method="get">';
	$output .= wp_nonce_field( 'sevendtd_nb_front_search', 'nb_mod_nonce', true, false );
	$output .= '<div><label for="nb_mod_query">キーワード</label><input id="nb_mod_query" name="nb_mod_query" type="search" value="' . esc_attr( $query ) . '" placeholder="例: UI, overhaul, admin"></div>';
	$output .= '<div><label for="nb_mod_category">カテゴリ</label><select id="nb_mod_category" name="nb_mod_category">' . $options_html . '</select></div>';
	$output .= '<div><label for="nb_game_version">互換性ウォッチ</label><input id="nb_game_version" name="nb_game_version" type="text" value="' . esc_attr( $game_version ) . '" placeholder="例: 2.0, v1.0"></div>';
	if ( $show_source_select ) {
		$output .= '<div><label for="nb_mod_source">表示ソース</label><select id="nb_mod_source" name="nb_mod_source">' . $source_options_html . '</select></div>';
	} else {
		$output .= '<input type="hidden" name="nb_mod_source" value="' . esc_attr( $source ) . '">';
	}
	if ( is_user_logged_in() ) {
		$current_account = sevendtd_nb_get_user_nexus_account( get_current_user_id() );
		if ( '' !== $current_account['username'] ) {
			$checked = $filter_my_mods ? ' checked' : '';
			$output .= '<div class="sevendtd-nexus-inline-check"><label>';
			$output .= '<input type="checkbox" name="nb_my_mods" value="1"' . $checked . '>';
			$output .= ' 自分の投稿 MOD のみ表示（' . esc_html( $current_account['username'] ) . '）</label></div>';
		}
	}
	$output .= '<div><button type="submit">検索する</button></div>';
	$output .= '</form>';

	if ( $has_request && ! $nonce_valid ) {
		$output .= '<div class="sevendtd-nexus-notice">検索リクエストの検証に失敗したため、入力値を破棄しました。再度検索してください。</div>';
	}

	if ( ! empty( $result['message'] ) ) {
		$output .= '<div class="sevendtd-nexus-notice">' . esc_html( (string) $result['message'] ) . '</div>';
	}

	$mods            = ! empty( $result['data'] ) && is_array( $result['data'] ) ? $result['data'] : array();
	$author_filtered = '';
	if ( $filter_my_mods && is_user_logged_in() ) {
		$linked_account = sevendtd_nb_get_user_nexus_account( get_current_user_id() );
		if ( '' !== $linked_account['username'] ) {
			$filter_author   = sevendtd_safe_strtolower( $linked_account['username'] );
			$author_filtered = $linked_account['username'];
			$mods            = array_values(
				array_filter(
					$mods,
					static function ( $mod ) use ( $filter_author ) {
						$author = sevendtd_safe_strtolower( sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) ) );
						return $author === $filter_author;
					}
				)
			);
		}
	}
	$output .= '<div class="sevendtd-nexus-result-summary">';
	$output .= '<span class="sevendtd-nexus-pill">表示件数: ' . esc_html( (string) count( $mods ) ) . '</span>';
	$output .= '<span class="sevendtd-nexus-pill">ソース: ' . esc_html( sevendtd_nb_get_source_label( $source ) ) . '</span>';
	if ( '' !== $game_version ) {
		$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-strong">互換性ウォッチ: ' . esc_html( $game_version ) . '</span>';
	}
	if ( '' !== $author_filtered ) {
		$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">🔗 Modder: ' . esc_html( $author_filtered ) . '</span>';
	}
	$output .= '</div>';
	$output .= sevendtd_nb_render_mod_cards(
		$mods,
		array(
			'show_image'   => true,
			'compact_meta' => false,
			'game_version' => $game_version,
		)
	);
	$output .= '</section>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_mod_search', 'sevendtd_nb_render_mod_search_shortcode' );

/**
 * 今週の更新重要度ランキングを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_weekly_ranking_shortcode( $atts ) {
	$atts = shortcode_atts(
		array(
			'title' => '今週の更新重要度ランキング',
			'limit' => 10,
		),
		$atts,
		'sevendtd_nexus_weekly_rank'
	);

	if ( ! sevendtd_nb_current_user_can_use_tools() ) {
		return sevendtd_nb_render_tool_access_notice( '今週の更新重要度ランキング' );
	}

	$limit = max( 3, min( 20, absint( $atts['limit'] ) ) );
	$mods  = sevendtd_nb_get_merged_feed_mods();

	$this_week_start = strtotime( 'monday this week 00:00:00' );
	$ranked          = array();

	foreach ( $mods as $mod ) {
		$updated_ts = sevendtd_nb_get_mod_updated_timestamp( $mod );
		if ( $updated_ts <= 0 || $updated_ts < $this_week_start ) {
			continue;
		}

		$base_score   = sevendtd_nb_get_mod_score( $mod );
		$recent_boost = max( 0, 14 - (int) floor( ( time() - $updated_ts ) / DAY_IN_SECONDS ) );
		$ranked[]     = array(
			'priority' => $base_score + $recent_boost,
			'mod'      => $mod,
		);
	}

	usort(
		$ranked,
		static function ( $left, $right ) {
			return (int) $right['priority'] <=> (int) $left['priority'];
		}
	);

	$ranked         = array_slice( $ranked, 0, $limit );
	$mods_to_render = array_map(
		static function ( $item ) {
			$mod                  = is_array( $item['mod'] ) ? $item['mod'] : array();
			$mod['category_name'] = '重要度 ' . (string) $item['priority'];
			return $mod;
		},
		$ranked
	);

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';
	$output .= '<p class="sevendtd-nexus-muted">更新頻度・評価・鮮度を組み合わせた今週の優先確認リストです。</p>';
	$output .= sevendtd_nb_render_mod_cards(
		$mods_to_render,
		array(
			'show_image'   => true,
			'compact_meta' => false,
		)
	);
	$output .= '</section>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_weekly_rank', 'sevendtd_nb_render_weekly_ranking_shortcode' );

/**
 * カテゴリ別一覧ショートコードを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_categories_shortcode( $atts ) {
	$atts = shortcode_atts(
		array(
			'title'          => 'カテゴリ別 MOD リスト',
			'per_category'   => 5,
			'max_categories' => 8,
			'category_ids'   => '',
		),
		$atts,
		'sevendtd_nexus_mod_categories'
	);

	if ( ! sevendtd_nb_current_user_can_use_tools() ) {
		return sevendtd_nb_render_tool_access_notice( 'カテゴリ別 MOD リスト' );
	}

	$per_category   = max( 1, min( 12, absint( $atts['per_category'] ) ) );
	$max_categories = max( 1, min( 12, absint( $atts['max_categories'] ) ) );
	$category_ids   = array_filter( array_map( 'absint', array_map( 'trim', explode( ',', (string) $atts['category_ids'] ) ) ) );

	$category_result = sevendtd_nb_get_categories();
	$categories      = ! empty( $category_result['data'] ) && is_array( $category_result['data'] ) ? $category_result['data'] : array();
	$feed_counts     = sevendtd_nb_get_category_counts_from_feed( sevendtd_nb_get_merged_feed_mods() );

	if ( ! empty( $category_ids ) ) {
		$categories = array_values(
			array_filter(
				$categories,
				static function ( $category ) use ( $category_ids ) {
					$category_id = absint( isset( $category['category_id'] ) ? $category['category_id'] : 0 );
					return in_array( $category_id, $category_ids, true );
				}
			)
		);
	}

	$categories = array_slice( $categories, 0, $max_categories );

	if ( empty( $category_ids ) ) {
		usort(
			$categories,
			static function ( $left, $right ) use ( $feed_counts ) {
				$left_id     = absint( isset( $left['category_id'] ) ? $left['category_id'] : 0 );
				$right_id    = absint( isset( $right['category_id'] ) ? $right['category_id'] : 0 );
				$left_count  = isset( $feed_counts[ $left_id ] ) ? (int) $feed_counts[ $left_id ] : 0;
				$right_count = isset( $feed_counts[ $right_id ] ) ? (int) $feed_counts[ $right_id ] : 0;

				if ( $left_count === $right_count ) {
					$left_name  = isset( $left['name'] ) ? (string) $left['name'] : '';
					$right_name = isset( $right['name'] ) ? (string) $right['name'] : '';
					return strcmp( $left_name, $right_name );
				}

				return $right_count <=> $left_count;
			}
		);
	}

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';
	$output .= '<p class="sevendtd-nexus-muted">カテゴリごとに、レビュー用の MOD 一覧を表示します。API が制限される場合はキャッシュ済みデータから代替表示します。</p>';

	if ( ! empty( $category_result['message'] ) ) {
		$output .= '<div class="sevendtd-nexus-notice">' . esc_html( (string) $category_result['message'] ) . '</div>';
	}

	if ( empty( $categories ) ) {
		$output .= '<p class="sevendtd-nexus-muted">表示できるカテゴリがありません。</p></section>';
		return $output;
	}

	$output .= '<div class="sevendtd-nexus-category-list">';

	$category_index = 0;

	foreach ( $categories as $category ) {
		$category_id    = absint( isset( $category['category_id'] ) ? $category['category_id'] : 0 );
		$category_name  = isset( $category['name'] ) ? (string) $category['name'] : (string) $category['category_name'];
		$category_count = isset( $feed_counts[ $category_id ] ) ? (int) $feed_counts[ $category_id ] : 0;
		$result         = sevendtd_nb_get_category_mods( $category_id, $per_category );
		$mods           = ! empty( $result['data'] ) && is_array( $result['data'] ) ? $result['data'] : array();
		$open_attr      = 0 === $category_index ? ' open' : '';

		$output .= '<section class="sevendtd-nexus-category-block">';
		$output .= '<details class="sevendtd-nexus-category-details"' . $open_attr . '>';
		$output .= '<summary class="sevendtd-nexus-category-summary"><span>' . esc_html( $category_name ) . '</span><span class="sevendtd-nexus-pill">候補 ' . esc_html( (string) $category_count ) . '</span></summary>';
		$output .= '<div class="sevendtd-nexus-category-body">';

		if ( ! empty( $result['message'] ) ) {
			$output .= '<div class="sevendtd-nexus-notice">' . esc_html( (string) $result['message'] ) . '</div>';
		}

		$output .= sevendtd_nb_render_mod_cards(
			$mods,
			array(
				'show_image'   => false,
				'compact_meta' => true,
			)
		);
		$output .= '</div></details></section>';
		++$category_index;
	}

	$output .= '</div></section>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_mod_categories', 'sevendtd_nb_render_categories_shortcode' );

/**
 * MOD 議論ページ向けリアクション定義を返す。
 *
 * @return array<string,string>
 */
function sevendtd_nb_get_discussion_reaction_options() {
	return array(
		'recommended' => 'おすすめ',
		'interested' => '気になる',
		'installed'  => '導入済み',
		'testing'    => '検証中',
		'caution'    => '要注意',
	);
}

/**
 * リアクションキーを正規化する。
 *
 * @param string $reaction リアクションキー.
 *
 * @return string
 */
function sevendtd_nb_normalize_discussion_reaction_key( $reaction ) {
	$reaction = sanitize_key( (string) $reaction );
	$aliases  = array(
		'issue'     => 'caution',
		'warn'      => 'caution',
		'warning'   => 'caution',
		'recommend' => 'recommended',
	);

	return isset( $aliases[ $reaction ] ) ? $aliases[ $reaction ] : $reaction;
}

/**
 * nexus_mod_updated_at メタ値（Y-m-d H:i 形式）から経過日数のラベルを返す。
 *
 * @param string $updated_at 保存済み更新日文字列.
 *
 * @return string 「3日前」「2週間前」「1ヶ月前」など。解析不能なら空文字。
 */
function sevendtd_nb_get_elapsed_days_label( $updated_at ) {
	$updated_at = trim( (string) $updated_at );
	if ( '' === $updated_at ) {
		return '';
	}

	// Y-m-d H:i または Y-m-d の両方を受け付ける
	$dt = DateTime::createFromFormat( 'Y-m-d H:i', $updated_at, new DateTimeZone( 'UTC' ) );
	if ( false === $dt ) {
		$dt = DateTime::createFromFormat( 'Y-m-d', $updated_at, new DateTimeZone( 'UTC' ) );
	}
	if ( false === $dt ) {
		return '';
	}

	$now  = new DateTime( 'now', new DateTimeZone( 'UTC' ) );
	$diff = (int) $now->diff( $dt )->days;

	if ( $diff <= 0 ) {
		return '今日更新';
	}
	if ( $diff <= 6 ) {
		return $diff . '日前';
	}
	if ( $diff <= 29 ) {
		return (int) round( $diff / 7 ) . '週間前';
	}
	if ( $diff <= 364 ) {
		return (int) round( $diff / 30 ) . 'ヶ月前';
	}

	return (int) round( $diff / 365 ) . '年前';
}

/**
 * DeepL API を使って英語テキストを日本語に翻訳する。
 * 翻訳結果は transient に 24 時間キャッシュする。
 * API キーが未設定の場合は空文字を返す。
 *
 * @param string $text 翻訳元テキスト（英語）.
 *
 * @return string 翻訳済み日本語テキスト。失敗時は空文字。
 */
function sevendtd_nb_translate_to_japanese( $text ) {
	$text = trim( (string) $text );
	if ( '' === $text ) {
		return '';
	}

	$settings = sevendtd_nb_get_settings();
	$api_key  = trim( (string) ( isset( $settings['deepl_api_key'] ) ? $settings['deepl_api_key'] : '' ) );
	if ( '' === $api_key && defined( 'SEVENDTD_NB_DEEPL_API_KEY' ) ) {
		$api_key = trim( (string) SEVENDTD_NB_DEEPL_API_KEY );
	}
	if ( '' === $api_key ) {
		$api_key = trim( (string) getenv( 'SEVENDTD_NB_DEEPL_API_KEY' ) );
	}
	if ( '' === $api_key ) {
		$api_key = trim( (string) getenv( 'DEEPL_API_KEY' ) );
	}
	if ( '' === $api_key ) {
		return '';
	}

	// transient キャッシュ（テキスト内容のハッシュで一意化）
	$cache_key = 'sevendtd_nb_trans_' . md5( $text );
	$cached    = get_transient( $cache_key );
	if ( false !== $cached ) {
		return (string) $cached;
	}

	// 無料プランは :fx で終わるキー
	$endpoint = ( false !== strpos( $api_key, ':fx' ) )
		? 'https://api-free.deepl.com/v2/translate'
		: 'https://api.deepl.com/v2/translate';

	$response = wp_remote_post(
		$endpoint,
		array(
			'timeout' => 10,
			'headers' => array( 'Authorization' => 'DeepL-Auth-Key ' . $api_key ),
			'body'    => array(
				'text'        => $text,
				'target_lang' => 'JA',
				'source_lang' => 'EN',
			),
		)
	);

	if ( is_wp_error( $response ) ) {
		return '';
	}

	$body = json_decode( wp_remote_retrieve_body( $response ), true );
	$ja   = isset( $body['translations'][0]['text'] ) ? (string) $body['translations'][0]['text'] : '';

	if ( '' !== $ja ) {
		set_transient( $cache_key, $ja, DAY_IN_SECONDS );
	}

	return $ja;
}

/**
 * リアクション重みを返す。
 *
 * @return array<string,int>
 */
function sevendtd_nb_get_discussion_reaction_weights() {
	// caution は負寄与にして「要注意多数」のMODが人気順で下がるようにする
	return array(
		'recommended' => 4,
		'installed'   => 3,
		'interested'  => 2,
		'testing'     => 2,
		'caution'     => -2,
	);
}

/**
 * MOD 議論投稿の人気スコアを返す。
 *
 * @param int               $post_id 投稿 ID.
 * @param array<string,int> $counts リアクション件数.
 *
 * @return int
 */
function sevendtd_nb_get_discussion_popularity_score( $post_id, array $counts = array() ) {
	$comment_count = (int) get_comments_number( $post_id );
	$score         = max( 0, $comment_count ) * 5;
	$weights       = sevendtd_nb_get_discussion_reaction_weights();

	if ( empty( $counts ) ) {
		$counts = sevendtd_nb_get_discussion_reaction_counts( $post_id );
	}

	foreach ( $weights as $key => $weight ) {
		$score += (int) ( isset( $counts[ $key ] ) ? $counts[ $key ] : 0 ) * (int) $weight;
	}

	return $score;
}

/**
 * MOD 議論投稿のタグメタを返す。
 *
 * @param int $post_id 投稿 ID.
 *
 * @return array<int,string>
 */
function sevendtd_nb_get_discussion_tags( $post_id ) {
	$tags = get_post_meta( $post_id, 'nexus_mod_tags', true );
	if ( ! is_array( $tags ) ) {
		$tags = array();
	}

	$tags = array_values(
		array_unique(
			array_filter(
				array_map(
					static function ( $tag ) {
						return sanitize_text_field( (string) $tag );
					},
					$tags
				)
			)
		)
	);

	return array_slice( $tags, 0, 8 );
}

/**
 * MOD 議論投稿のリアクション件数を返す。
 *
 * @param int $post_id 投稿 ID.
 *
 * @return array<string,int>
 */
function sevendtd_nb_get_discussion_reaction_counts( $post_id ) {
	$options = sevendtd_nb_get_discussion_reaction_options();
	$counts  = array_fill_keys( array_keys( $options ), 0 );

	$comment_ids = get_comments(
		array(
			'post_id' => absint( $post_id ),
			'status'  => 'approve',
			'fields'  => 'ids',
			'number'  => 0,
		)
	);

	if ( empty( $comment_ids ) || ! is_array( $comment_ids ) ) {
		return $counts;
	}

	foreach ( $comment_ids as $comment_id ) {
		$reaction = sevendtd_nb_normalize_discussion_reaction_key(
			(string) get_comment_meta( (int) $comment_id, 'sevendtd_nexus_reaction', true )
		);
		if ( isset( $counts[ $reaction ] ) ) {
			$counts[ $reaction ]++;
		}
	}

	return $counts;
}

/**
 * MOD 議論本文を見やすいカード形式に変換する。
 *
 * @param string $content 本文.
 *
 * @return string
 */
function sevendtd_nb_render_discussion_post_content( $content ) {
	if ( ! is_singular( 'sevendtd_nexus_mod' ) || ! in_the_loop() || ! is_main_query() ) {
		return $content;
	}

	$post_id      = get_the_ID();
	$mod_id       = (string) get_post_meta( $post_id, 'nexus_mod_id', true );
	$mod_url      = (string) get_post_meta( $post_id, 'nexus_mod_url', true );
	$author       = (string) get_post_meta( $post_id, 'nexus_mod_author', true );
	$version      = (string) get_post_meta( $post_id, 'nexus_mod_version', true );
	$updated      = (string) get_post_meta( $post_id, 'nexus_mod_updated_at', true );
	$category     = (string) get_post_meta( $post_id, 'nexus_mod_category', true );
	$image        = (string) get_post_meta( $post_id, 'nexus_mod_image_url', true );
	$desc         = (string) get_post_meta( $post_id, 'nexus_mod_description', true );
	$requirements = (string) get_post_meta( $post_id, 'nexus_mod_requirements', true );
	$incompatible = (string) get_post_meta( $post_id, 'nexus_mod_incompatible', true );
	$side         = (string) get_post_meta( $post_id, 'nexus_mod_side', true );
	$tags         = sevendtd_nb_get_discussion_tags( $post_id );
	$counts       = sevendtd_nb_get_discussion_reaction_counts( $post_id );
	$pop          = sevendtd_nb_get_discussion_popularity_score( $post_id, $counts );
	$summary      = trim( (string) get_the_excerpt( $post_id ) );
	$raw_body     = trim( wp_strip_all_tags( (string) $content ) );
	$elapsed      = sevendtd_nb_get_elapsed_days_label( $updated );

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<div class="sevendtd-nexus-discussion-summary">';

	if ( '' !== $image ) {
		$output .= '<img class="sevendtd-nexus-discussion-cover" src="' . esc_url( $image ) . '" alt="' . esc_attr( get_the_title( $post_id ) ) . '">';
	}

	if ( '' !== $summary ) {
		$output .= '<p class="sevendtd-nexus-muted" style="margin:0">' . esc_html( $summary ) . '</p>';
	}

	$output .= '<div class="sevendtd-nexus-discussion-meta">';
	if ( '' !== $mod_id ) {
		$output .= '<span class="sevendtd-nexus-pill">MOD ID: ' . esc_html( $mod_id ) . '</span>';
	}
	if ( '' !== $author ) {
		$output .= '<span class="sevendtd-nexus-pill">作者: ' . esc_html( $author ) . '</span>';
	}
	if ( '' !== $category ) {
		$output .= '<span class="sevendtd-nexus-pill">カテゴリ: ' . esc_html( $category ) . '</span>';
	}
	if ( '' !== $version ) {
		$output .= '<span class="sevendtd-nexus-pill">バージョン: ' . esc_html( $version ) . '</span>';
	}
	if ( '' !== $updated ) {
		$updated_label = $updated . ( '' !== $elapsed ? '（' . $elapsed . '）' : '' );
		$output .= '<span class="sevendtd-nexus-pill">更新日: ' . esc_html( $updated_label ) . '</span>';
	}
	if ( '' !== $side ) {
		$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-strong">用途: ' . esc_html( $side ) . '</span>';
	}
	$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">人気スコア: ' . esc_html( (string) $pop ) . '</span>';
	$output .= '</div>';

	if ( ! empty( $tags ) ) {
		$output .= '<div class="sevendtd-nexus-discussion-tags">';
		foreach ( $tags as $tag ) {
			$output .= '<span class="sevendtd-nexus-pill">#' . esc_html( $tag ) . '</span>';
		}
		$output .= '</div>';
	}

	$output .= '<div class="sevendtd-nexus-discussion-actions">';
	if ( '' !== $mod_url ) {
		$output .= '<a class="sevendtd-nexus-discussion-btn sevendtd-nexus-discussion-btn-primary" href="' . esc_url( $mod_url ) . '" target="_blank" rel="noopener noreferrer">Nexus 原ページを開く</a>';
	}
	$output .= '<a class="sevendtd-nexus-discussion-btn" href="' . esc_url( get_post_type_archive_link( 'sevendtd_nexus_mod' ) ) . '">MOD 議論一覧を見る</a>';
	$output .= '</div>';

	$options = sevendtd_nb_get_discussion_reaction_options();
	$output .= '<div class="sevendtd-nexus-reaction-summary">';
	foreach ( $options as $key => $label ) {
		$count = isset( $counts[ $key ] ) ? (int) $counts[ $key ] : 0;
		if ( $count <= 0 ) {
			continue;
		}
		$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-reaction-' . esc_attr( $key ) . '">' . esc_html( $label ) . ': ' . esc_html( (string) $count ) . '</span>';
	}
	$output .= '</div>';

	$output .= '</div></section>';

	// ─── 詳しい解説記事（案A: articles/mod/*.md と nexus_mod_id で紐付け）───
	$article_id = sevendtd_nb_get_linked_article_id( $mod_id );
	if ( $article_id > 0 ) {
		$art_url = get_permalink( $article_id );
		$art_exc = trim( (string) get_the_excerpt( $article_id ) );
		$output .= '<section class="sevendtd-nexus-box sevendtd-nexus-article-box">';
		$output .= '<h3>📝 このMODの詳しい解説記事</h3>';
		$output .= '<p style="margin:0 0 0.6em"><a class="sevendtd-nexus-discussion-btn sevendtd-nexus-discussion-btn-primary" href="' . esc_url( $art_url ) . '">' . esc_html( get_the_title( $article_id ) ) . ' を読む</a></p>';
		if ( '' !== $art_exc ) {
			$output .= '<p class="sevendtd-nexus-muted" style="margin:0">' . esc_html( $art_exc ) . '</p>';
		}
		$output .= '</section>';
	} else {
		// 解説記事が未作成 → リクエストボタン(mu-plugin: sevendtd-article-request が受付)。
		$rcount = (int) get_post_meta( $post_id, '_sevendtd_article_request_count', true );
		$output .= '<section class="sevendtd-nexus-box sevendtd-nexus-reqbox">';
		$output .= '<h3>📝 このMODの解説記事</h3>';
		$output .= '<p class="sevendtd-nexus-muted" style="margin:0 0 .7em">まだ解説記事はありません。読みたい方はリクエストできます（運営が記事化を検討します）。</p>';
		$output .= '<button type="button" class="sevendtd-nexus-discussion-btn sevendtd-nexus-discussion-btn-primary sevendtd-nexus-reqbtn" data-mod="' . esc_attr( $mod_id ) . '">📝 解説記事をリクエスト</button>';
		$output .= ' <span class="sevendtd-nexus-reqcount"' . ( $rcount > 0 ? '' : ' style="display:none"' ) . '>🙋 <span class="n">' . (int) $rcount . '</span> 人がリクエスト中</span>';
		$output .= '<p class="sevendtd-nexus-reqmsg" role="status" style="margin:.5em 0 0;font-size:13px;color:#2c6653"></p>';
		$output .= '</section>';
	}

	// ─── MOD 解説セクション（原文 + 日本語訳）───
	if ( '' !== $desc ) {
		$ja_desc = sevendtd_nb_translate_to_japanese( $desc );
		$output .= '<section class="sevendtd-nexus-box">';
		$output .= '<h3>MOD 解説</h3>';
		if ( '' !== $ja_desc ) {
			// 日本語訳を主表示、原文を折りたたみで補足
			$output .= '<p style="margin:0 0 0.8em">' . nl2br( esc_html( $ja_desc ) ) . '</p>';
			$output .= '<details class="sevendtd-nexus-desc-raw"><summary>原文（英語）を表示</summary>';
			$output .= '<p style="margin:0.5em 0 0">' . esc_html( $desc ) . '</p>';
			$output .= '</details>';
		} else {
			// 翻訳なし：原文をフルで表示（120語制限解除）
			$output .= '<p style="margin:0">' . esc_html( $desc ) . '</p>';
		}
		$output .= '</section>';
	}

	// ─── 導入前チェック項目セクション ───
	$output .= '<section class="sevendtd-nexus-box sevendtd-nexus-checklist-box">';
	$output .= '<h3>導入前チェック（前提 / 競合 MOD）</h3>';
	$has_checklist = false;
	if ( '' !== $requirements ) {
		$output .= '<p><strong>前提 MOD:</strong> ' . esc_html( $requirements ) . '</p>';
		$has_checklist = true;
	}
	if ( '' !== $incompatible ) {
		$output .= '<p><strong>競合 MOD:</strong> ' . esc_html( $incompatible ) . '</p>';
		$has_checklist = true;
	}
	if ( ! $has_checklist ) {
		$output .= '<p class="sevendtd-nexus-muted">情報はまだありません。導入済みの方はコメントで情報をお寄せください。</p>';
	}
	$output .= '</section>';

	$auto_generated = false !== mb_strpos( $raw_body, 'Nexus MOD 議論ページです' );
	if ( ! $auto_generated && '' !== trim( wp_strip_all_tags( (string) $content ) ) ) {
		$output .= '<section class="sevendtd-nexus-box"><h3>概要メモ</h3>' . wp_kses_post( $content ) . '</section>';
	}

	return $output;
}
add_filter( 'the_content', 'sevendtd_nb_render_discussion_post_content', 25 );

/**
 * 案A: MOD ID に紐付く解説記事(articles/mod/*.md 由来の通常投稿)の ID を返す。
 * sync_articles.php が frontmatter `nexus_mod_id` を `_sevendtd_nexus_mod_id` メタに保存する。
 *
 * @param string $mod_id Nexus MOD ID.
 *
 * @return int 公開済み記事の投稿 ID。無ければ 0。
 */
function sevendtd_nb_get_linked_article_id( $mod_id ) {
	$mod_id = trim( (string) $mod_id );
	if ( '' === $mod_id ) {
		return 0;
	}
	$posts = get_posts(
		array(
			'post_type'      => 'post',
			'post_status'    => 'publish',
			'posts_per_page' => 1,
			'fields'         => 'ids',
			'meta_key'       => '_sevendtd_nexus_mod_id',
			'meta_value'     => $mod_id,
			'orderby'        => 'date',
			'order'          => 'DESC',
		)
	);
	return $posts ? (int) $posts[0] : 0;
}

/**
 * 案A: 解説記事(通常投稿)の末尾に、対応する nexus_mod 議論ページへの逆リンクを足す。
 *
 * @param string $content 本文.
 *
 * @return string
 */
function sevendtd_nb_render_article_nexus_backlink( $content ) {
	if ( ! is_singular( 'post' ) || ! in_the_loop() || ! is_main_query() ) {
		return $content;
	}
	$mod_id = (string) get_post_meta( get_the_ID(), '_sevendtd_nexus_mod_id', true );
	if ( '' === $mod_id ) {
		return $content;
	}
	$disc_id = sevendtd_nb_get_mod_discussion_post_id( $mod_id );
	if ( $disc_id <= 0 ) {
		return $content;
	}
	$box  = sevendtd_nb_get_shared_styles();
	$box .= '<section class="sevendtd-nexus-box sevendtd-nexus-article-box" style="margin-top:1.5em">';
	$box .= '<h3>🔧 このMODのNexus情報ページ</h3>';
	$box .= '<p style="margin:0"><a class="sevendtd-nexus-discussion-btn" href="' . esc_url( get_permalink( $disc_id ) ) . '">Nexus情報・前提/競合・コメントを見る</a></p>';
	$box .= '</section>';
	return $content . $box;
}
add_filter( 'the_content', 'sevendtd_nb_render_article_nexus_backlink', 26 );

/**
 * コメントフォームにリアクション項目を追加する。
 */
function sevendtd_nb_render_discussion_comment_reaction_field() {
	if ( ! is_singular( 'sevendtd_nexus_mod' ) ) {
		return;
	}

	$options = sevendtd_nb_get_discussion_reaction_options();
	$value   = '';
	if ( isset( $_POST['sevendtd_nexus_reaction'] ) ) {
		$value = sanitize_key( wp_unslash( $_POST['sevendtd_nexus_reaction'] ) );
	}

	echo '<p class="comment-form-sevendtd-reaction">';
	echo '<label for="sevendtd_nexus_reaction">リアクション</label>';
	echo '<select id="sevendtd_nexus_reaction" name="sevendtd_nexus_reaction">';
	echo '<option value="">選択なし</option>';
	foreach ( $options as $key => $label ) {
		echo '<option value="' . esc_attr( $key ) . '"' . selected( $value, $key, false ) . '>' . esc_html( $label ) . '</option>';
	}
	echo '</select>';
	echo '<input type="hidden" id="sevendtd_nexus_reaction_fallback" name="sevendtd_nexus_reaction_fallback" value="' . esc_attr( $value ) . '">';
	echo '</p>';
	echo '<script>(function(){var sel=document.getElementById("sevendtd_nexus_reaction");var hid=document.getElementById("sevendtd_nexus_reaction_fallback");if(!sel||!hid){return;}var sync=function(){hid.value=sel.value||"";};sync();sel.addEventListener("change",sync);var form=sel.form||document.getElementById("commentform");if(form){form.addEventListener("submit",sync);}})();</script>';
}
add_action( 'comment_form_after_fields', 'sevendtd_nb_render_discussion_comment_reaction_field' );
add_action( 'comment_form_logged_in_after', 'sevendtd_nb_render_discussion_comment_reaction_field' );

/**
 * コメント送信時にリアクションを保存する。
 *
 * @param int $comment_id コメント ID.
 */
function sevendtd_nb_save_discussion_comment_reaction( $comment_id ) {
	$comment = get_comment( $comment_id );
	if ( ! ( $comment instanceof WP_Comment ) ) {
		return;
	}

	if ( 'sevendtd_nexus_mod' !== get_post_type( $comment->comment_post_ID ) ) {
		return;
	}

	if ( ! isset( $_POST['sevendtd_nexus_reaction'] ) && ! isset( $_POST['sevendtd_nexus_reaction_fallback'] ) ) {
		delete_comment_meta( $comment_id, 'sevendtd_nexus_reaction' );
		return;
	}

	$raw_reaction = '';
	if ( isset( $_POST['sevendtd_nexus_reaction'] ) ) {
		$raw_reaction = (string) wp_unslash( $_POST['sevendtd_nexus_reaction'] );
	}
	if ( '' === $raw_reaction && isset( $_POST['sevendtd_nexus_reaction_fallback'] ) ) {
		$raw_reaction = (string) wp_unslash( $_POST['sevendtd_nexus_reaction_fallback'] );
	}

	$reaction = sevendtd_nb_normalize_discussion_reaction_key(
		sanitize_key( $raw_reaction )
	);
	$options  = sevendtd_nb_get_discussion_reaction_options();

	if ( '' === $reaction || ! isset( $options[ $reaction ] ) ) {
		delete_comment_meta( $comment_id, 'sevendtd_nexus_reaction' );
		return;
	}

	update_comment_meta( $comment_id, 'sevendtd_nexus_reaction', $reaction );
}
add_action( 'comment_post', 'sevendtd_nb_save_discussion_comment_reaction', 10, 1 );

/**
 * コメント本文の先頭にリアクションバッジを表示する。
 *
 * @param string          $comment_text コメント本文.
 * @param WP_Comment|null $comment コメント.
 *
 * @return string
 */
function sevendtd_nb_prepend_discussion_comment_reaction( $comment_text, $comment = null ) {
	if ( ! ( $comment instanceof WP_Comment ) ) {
		$comment = get_comment( $comment );
	}

	if ( ! ( $comment instanceof WP_Comment ) ) {
		return $comment_text;
	}

	if ( 'sevendtd_nexus_mod' !== get_post_type( $comment->comment_post_ID ) ) {
		return $comment_text;
	}

	$reaction = sevendtd_nb_normalize_discussion_reaction_key(
		(string) get_comment_meta( $comment->comment_ID, 'sevendtd_nexus_reaction', true )
	);
	$options  = sevendtd_nb_get_discussion_reaction_options();

	if ( '' === $reaction || ! isset( $options[ $reaction ] ) ) {
		return $comment_text;
	}

	$badge = '<span class="sevendtd-nexus-comment-reaction sevendtd-nexus-reaction-' . esc_attr( sanitize_html_class( $reaction ) ) . '">' . esc_html( $options[ $reaction ] ) . '</span>';

	return $badge . $comment_text;
}
add_filter( 'comment_text', 'sevendtd_nb_prepend_discussion_comment_reaction', 10, 2 );

/**
 * MOD 議論一覧ショートコードを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_mod_discussions_shortcode( $atts ) {
	$atts = shortcode_atts(
		array(
			'title' => 'MOD 議論一覧',
			'order' => 'popular',
			'limit' => 12,
		),
		$atts,
		'sevendtd_nexus_mod_discussions'
	);

	$order_mode = strtolower( trim( (string) $atts['order'] ) );
	if ( ! in_array( $order_mode, array( 'popular', 'new' ), true ) ) {
		$order_mode = 'popular';
	}

	$limit      = max( 1, min( 30, absint( $atts['limit'] ) ) );
	$query_args = array(
		'post_type'      => 'sevendtd_nexus_mod',
		'post_status'    => 'publish',
		'posts_per_page' => 'new' === $order_mode ? $limit : max( 40, min( 200, $limit * 8 ) ),
	);

	if ( 'new' === $order_mode ) {
		$query_args['orderby'] = 'date';
		$query_args['order']   = 'DESC';
	} else {
		$query_args['orderby'] = array(
			'comment_count' => 'DESC',
			'modified'      => 'DESC',
			'date'          => 'DESC',
		);
		$query_args['order']   = 'DESC';
	}

	$posts = get_posts( $query_args );
	if ( 'popular' === $order_mode && ! empty( $posts ) ) {
		usort(
			$posts,
			static function ( $left, $right ) {
				$left_id       = (int) $left->ID;
				$right_id      = (int) $right->ID;
				$left_counts   = sevendtd_nb_get_discussion_reaction_counts( $left_id );
				$right_counts  = sevendtd_nb_get_discussion_reaction_counts( $right_id );
				$left_score    = sevendtd_nb_get_discussion_popularity_score( $left_id, $left_counts );
				$right_score   = sevendtd_nb_get_discussion_popularity_score( $right_id, $right_counts );

				if ( $left_score === $right_score ) {
					return strtotime( (string) $right->post_modified_gmt ) <=> strtotime( (string) $left->post_modified_gmt );
				}

				return $right_score <=> $left_score;
			}
		);
		$posts = array_slice( $posts, 0, $limit );
	}

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';
	$output .= '<p class="sevendtd-nexus-muted">Nexus API から取得して保存した最小限のメタ情報をもとに、議論トピックを並べています。</p>';
	$output .= '<div class="sevendtd-nexus-discussion-sort">';
	$output .= '<span class="sevendtd-nexus-discussion-btn ' . ( 'popular' === $order_mode ? 'is-active' : '' ) . '">人気順</span>';
	$output .= '<span class="sevendtd-nexus-discussion-btn ' . ( 'new' === $order_mode ? 'is-active' : '' ) . '">新着順</span>';
	$output .= '</div>';

	if ( empty( $posts ) ) {
		$output .= '<p class="sevendtd-nexus-muted">議論ページはまだありません。</p>';
		$output .= '</section>';
		return $output;
	}

	$output .= '<div class="sevendtd-nexus-discussion-list">';
	foreach ( $posts as $post ) {
		$post_id   = (int) $post->ID;
		$permalink = get_permalink( $post_id );
		$mod_url   = (string) get_post_meta( $post_id, 'nexus_mod_url', true );
		$image     = (string) get_post_meta( $post_id, 'nexus_mod_image_url', true );
		$updated   = (string) get_post_meta( $post_id, 'nexus_mod_updated_at', true );
		$author    = (string) get_post_meta( $post_id, 'nexus_mod_author', true );
		$category  = (string) get_post_meta( $post_id, 'nexus_mod_category', true );
		$tags      = sevendtd_nb_get_discussion_tags( $post_id );
		$counts    = sevendtd_nb_get_discussion_reaction_counts( $post_id );
		$pop       = sevendtd_nb_get_discussion_popularity_score( $post_id, $counts );
		$elapsed   = sevendtd_nb_get_elapsed_days_label( $updated );

		$output .= '<article class="sevendtd-nexus-discussion-card">';
		if ( '' !== $image ) {
			$output .= '<img class="sevendtd-nexus-card-cover" src="' . esc_url( $image ) . '" alt="' . esc_attr( get_the_title( $post_id ) ) . '">';
		}
		$output .= '<h3><a href="' . esc_url( $permalink ) . '">' . esc_html( get_the_title( $post_id ) ) . '</a></h3>';
		$output .= '<p>' . esc_html( wp_trim_words( (string) get_the_excerpt( $post_id ), 30, '...' ) ) . '</p>';
		$output .= '<div class="sevendtd-nexus-meta-inline">';
		$output .= '<span class="sevendtd-nexus-pill">コメント: ' . esc_html( (string) get_comments_number( $post_id ) ) . '</span>';
		$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">人気スコア: ' . esc_html( (string) $pop ) . '</span>';
		if ( '' !== $author ) {
			$output .= '<span class="sevendtd-nexus-pill">作者: ' . esc_html( $author ) . '</span>';
		}
		if ( '' !== $category ) {
			$output .= '<span class="sevendtd-nexus-pill">カテゴリ: ' . esc_html( $category ) . '</span>';
		}
		if ( '' !== $updated ) {
			// 経過日数バッジを更新日の横に追加
			$updated_pill = $updated . ( '' !== $elapsed ? '（' . $elapsed . '）' : '' );
			$output .= '<span class="sevendtd-nexus-pill">更新日: ' . esc_html( $updated_pill ) . '</span>';
		}
		$output .= '</div>';

		if ( ! empty( $tags ) ) {
			$output .= '<div class="sevendtd-nexus-discussion-tags">';
			foreach ( $tags as $tag ) {
				$output .= '<span class="sevendtd-nexus-pill">#' . esc_html( $tag ) . '</span>';
			}
			$output .= '</div>';
		}

		$options = sevendtd_nb_get_discussion_reaction_options();
		$output .= '<div class="sevendtd-nexus-meta-inline">';
		foreach ( $options as $key => $label ) {
			$count = isset( $counts[ $key ] ) ? (int) $counts[ $key ] : 0;
			if ( $count <= 0 ) {
				continue;
			}
			$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-reaction-' . esc_attr( $key ) . '">' . esc_html( $label ) . ': ' . esc_html( (string) $count ) . '</span>';
		}
		$output .= '</div>';

		$output .= '<div class="sevendtd-nexus-actions"><a href="' . esc_url( $permalink ) . '">議論ページへ</a>';
		if ( '' !== $mod_url ) {
			$output .= ' / <a href="' . esc_url( $mod_url ) . '" target="_blank" rel="noopener noreferrer">Nexus 原ページ</a>';
		}
		$output .= '</div>';
		$output .= '</article>';
	}

	$output .= '</div></section>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_mod_discussions', 'sevendtd_nb_render_mod_discussions_shortcode' );

/**
 * MOD 議論一覧ページかどうかを判定する。
 *
 * @return bool
 */
function sevendtd_nb_is_discussion_index_page() {
	if ( is_admin() || ! is_main_query() || ! is_singular() ) {
		return false;
	}

	$paths = array(
		'community/nexus-mods',
		'community/mod-discussions',
		'nexus-mods',
	);

	foreach ( $paths as $path ) {
		$page = get_page_by_path( $path );
		if ( ( $page instanceof WP_Post ) && is_page( $page->ID ) ) {
			return true;
		}
	}

	return false;
}

/**
 * 議論一覧ページへショートコードを自動追加する。
 *
 * @param string $content 本文.
 *
 * @return string
 */
function sevendtd_nb_append_discussion_index_content( $content ) {
	if ( ! sevendtd_nb_is_discussion_index_page() ) {
		return $content;
	}

	if ( false !== strpos( $content, 'sevendtd_nexus_mod_discussions' ) ) {
		return $content;
	}

	$extra = sevendtd_nb_render_mod_discussions_shortcode(
		array(
			'order' => 'popular',
			'limit' => 20,
			'title' => 'MOD 議論一覧',
		)
	);

	return $content . $extra;
}
add_filter( 'the_content', 'sevendtd_nb_append_discussion_index_content', 10025 );

/**
 * Discord 通知向け REST 権限チェック。
 *
 * @param WP_REST_Request $request REST リクエスト.
 *
 * @return bool
 */
function sevendtd_nb_rest_watch_permission( WP_REST_Request $request ) {
	if ( current_user_can( 'manage_options' ) ) {
		return true;
	}

	$settings = sevendtd_nb_get_settings();
	$token    = isset( $settings['discord_notify_token'] ) ? trim( (string) $settings['discord_notify_token'] ) : '';

	if ( '' === $token ) {
		return false;
	}

	$auth = (string) $request->get_header( 'authorization' );
	if ( 0 === stripos( $auth, 'Bearer ' ) ) {
		$provided = trim( substr( $auth, 7 ) );
		if ( hash_equals( $token, $provided ) ) {
			return true;
		}
	}

	$fallback = trim( (string) $request->get_header( 'x-sevendtd-bearer' ) );
	return '' !== $fallback && hash_equals( $token, $fallback );
}

/**
 * Discord 通知向けデータを返す REST コールバック。
 *
 * @param WP_REST_Request $request REST リクエスト.
 *
 * @return WP_REST_Response
 */
function sevendtd_nb_rest_watch_updates( WP_REST_Request $request ) {
	$result = sevendtd_nb_get_discord_watch_items(
		array(
			'limit'  => $request->get_param( 'limit' ),
			'source' => $request->get_param( 'source' ),
		)
	);

	return new WP_REST_Response( $result, 200 );
}

/**
 * MOD カテゴリ一覧を返す REST コールバック。
 *
 * @param WP_REST_Request $request REST リクエスト.
 *
 * @return WP_REST_Response
 */
function sevendtd_nb_rest_categories( WP_REST_Request $request ) {
	$category_result = sevendtd_nb_get_categories();
	$rows            = ! empty( $category_result['data'] ) && is_array( $category_result['data'] ) ? $category_result['data'] : array();
	$items           = array();
	$fallback_used   = ! empty( $category_result['fallback'] );

	if ( empty( $rows ) ) {
		$watch_result = sevendtd_nb_get_discord_watch_items(
			array(
				'limit' => 50,
			)
		);
		$watch_items  = ! empty( $watch_result['items'] ) && is_array( $watch_result['items'] ) ? $watch_result['items'] : array();
		$derived_rows = array();

		foreach ( $watch_items as $watch_item ) {
			if ( ! is_array( $watch_item ) ) {
				continue;
			}

			$name = trim( (string) ( isset( $watch_item['category'] ) ? $watch_item['category'] : '' ) );
			if ( '' !== $name ) {
				$derived_rows[] = array(
					'category_id'   => 0,
					'name'          => $name,
					'category_name' => $name,
				);
			}

			$tag_rows = isset( $watch_item['tags_ja'] ) && is_array( $watch_item['tags_ja'] ) ? $watch_item['tags_ja'] : array();
			foreach ( $tag_rows as $tag_name ) {
				$tag_name = trim( (string) $tag_name );
				if ( '' === $tag_name ) {
					continue;
				}

				$derived_rows[] = array(
					'category_id'   => 0,
					'name'          => $tag_name,
					'category_name' => $tag_name,
				);
			}
		}

		if ( ! empty( $derived_rows ) ) {
			$rows          = sevendtd_nb_merge_category_rows( $derived_rows );
			$fallback_used = true;
		}
	}

	$dictionary_rows = array();
	foreach ( array_values( array_unique( array_values( sevendtd_nb_get_japanese_tag_dictionary() ) ) ) as $tag_name ) {
		$tag_name = trim( (string) $tag_name );
		if ( '' === $tag_name ) {
			continue;
		}

		$dictionary_rows[] = array(
			'category_id'   => 0,
			'name'          => $tag_name,
			'category_name' => $tag_name,
		);
	}

	if ( ! empty( $dictionary_rows ) ) {
		$merged_rows = sevendtd_nb_merge_category_rows( $rows, $dictionary_rows );
		if ( count( $merged_rows ) > count( $rows ) ) {
			$fallback_used = true;
		}
		$rows = $merged_rows;
	}

	foreach ( $rows as $row ) {
		if ( ! is_array( $row ) ) {
			continue;
		}

		$name = trim( (string) ( isset( $row['name'] ) ? $row['name'] : ( isset( $row['category_name'] ) ? $row['category_name'] : '' ) ) );
		if ( '' === $name ) {
			continue;
		}

		$items[] = array(
			'category_id' => absint( isset( $row['category_id'] ) ? $row['category_id'] : 0 ),
			'name'        => $name,
		);
	}

	return new WP_REST_Response(
		array(
			'ok'         => ! empty( $category_result['ok'] ) || ! empty( $items ),
			'count'      => count( $items ),
			'fallback'   => $fallback_used,
			'message'    => isset( $category_result['message'] ) ? (string) $category_result['message'] : '',
			'categories' => $items,
		),
		200
	);
}

/**
 * REST ルートを登録する。
 */
function sevendtd_nb_register_rest_routes() {
	register_rest_route(
		'sevendtd-nexus/v1',
		'/watch-updates',
		array(
			'methods'             => WP_REST_Server::READABLE,
			'callback'            => 'sevendtd_nb_rest_watch_updates',
			'permission_callback' => 'sevendtd_nb_rest_watch_permission',
		)
	);
	register_rest_route(
		'sevendtd-nexus/v1',
		'/categories',
		array(
			'methods'             => WP_REST_Server::READABLE,
			'callback'            => 'sevendtd_nb_rest_categories',
			'permission_callback' => 'sevendtd_nb_rest_watch_permission',
		)
	);
	register_rest_route(
		'sevendtd-nexus/v1',
		'/account-link',
		array(
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => 'sevendtd_nb_rest_account_link_save',
				'permission_callback' => 'sevendtd_nb_rest_account_link_permission',
				'args'                => array(
					'nexus_username' => array(
						'required'          => true,
						'type'              => 'string',
						'sanitize_callback' => 'sanitize_text_field',
					),
					'nexus_api_key'  => array(
						'required'          => true,
						'type'              => 'string',
						'sanitize_callback' => 'sanitize_text_field',
					),
				),
			),
			array(
				'methods'             => WP_REST_Server::DELETABLE,
				'callback'            => 'sevendtd_nb_rest_account_link_delete',
				'permission_callback' => 'sevendtd_nb_rest_account_link_permission',
			),
		)
	);
}
add_action( 'rest_api_init', 'sevendtd_nb_register_rest_routes' );
/**
 * ==================== Nexus アカウント連携 (Phase 1-3) ====================
 */

/**
 * WordPress ユーザーの Nexus 連携情報を取得する。
 *
 * @param int $user_id WordPress ユーザー ID.
 *
 * @return array{username:string,nexus_uid:string,linked_at:int}
 */
function sevendtd_nb_get_user_nexus_account( $user_id ) {
	$user_id = absint( $user_id );
	return array(
		'username'  => (string) get_user_meta( $user_id, 'sevendtd_nexus_username', true ),
		'nexus_uid' => (string) get_user_meta( $user_id, 'sevendtd_nexus_user_id', true ),
		'linked_at' => absint( get_user_meta( $user_id, 'sevendtd_nexus_linked_at', true ) ),
	);
}

/**
 * Nexus ユーザー名のソフト検証。
 *
 * フィードデータで uploaded_by が一致する MOD を探し、見つかれば確認済みとする。
 * フィードに存在しない場合は検索 API をフォールバックとして試みる。
 *
 * @param string $username Nexus ユーザー名.
 *
 * @return array{ok:bool,nexus_uid:string,mod_count:int,message:string}
 */
function sevendtd_nb_verify_nexus_username( $username ) {
	$username = trim( sanitize_text_field( (string) $username ) );

	if ( '' === $username ) {
		return array(
			'ok'        => false,
			'nexus_uid' => '',
			'mod_count' => 0,
			'message'   => 'ユーザー名が空です。',
		);
	}

	if ( ! preg_match( '/^[A-Za-z0-9._-]{2,64}$/', $username ) ) {
		return array(
			'ok'        => false,
			'nexus_uid' => '',
			'mod_count' => 0,
			'message'   => 'ユーザー名の形式が正しくありません。英数字と . _ - のみ使用できます。',
		);
	}

	$lower = sevendtd_safe_strtolower( $username );
	$mods  = sevendtd_nb_get_merged_feed_mods();
	$uid   = '';
	$count = 0;

	foreach ( $mods as $mod ) {
		$author = sevendtd_safe_strtolower(
			sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) )
		);

		if ( $author === $lower ) {
			++$count;
			if ( '' === $uid ) {
				$raw_uid = sevendtd_nb_get_mod_value( $mod, array( 'user_id', 'uploaded_users_profile_url' ) );
				if ( ctype_digit( $raw_uid ) ) {
					$uid = $raw_uid;
				} elseif ( '' !== $raw_uid && preg_match( '/\/users\/(\d+)/', $raw_uid, $mtch ) ) {
					$uid = $mtch[1];
				}
			}
		}
	}

	if ( $count > 0 ) {
		return array(
			'ok'        => true,
			'nexus_uid' => $uid,
			'mod_count' => $count,
			'message'   => sprintf( 'フィード内で %d 件の MOD が見つかりました。', $count ),
		);
	}

	$search_result = sevendtd_nb_search_mods( $username, 0, 6 );
	if ( ! empty( $search_result['ok'] ) && ! empty( $search_result['data'] ) && is_array( $search_result['data'] ) ) {
		foreach ( $search_result['data'] as $mod ) {
			$author = sevendtd_safe_strtolower(
				sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) )
			);

			if ( $author === $lower ) {
					++$count;
				if ( '' === $uid ) {
					$raw_uid = sevendtd_nb_get_mod_value( $mod, array( 'user_id', 'uploaded_users_profile_url' ) );
					if ( ctype_digit( $raw_uid ) ) {
						$uid = $raw_uid;
					} elseif ( '' !== $raw_uid && preg_match( '/\/users\/(\d+)/', $raw_uid, $mtch ) ) {
						$uid = $mtch[1];
					}
				}
			}
		}
	}

	if ( $count > 0 ) {
		return array(
			'ok'        => true,
			'nexus_uid' => $uid,
			'mod_count' => $count,
			'message'   => sprintf( 'API 検索経由で %d 件の MOD が確認されました。', $count ),
		);
	}

	return array(
		'ok'        => true,
		'nexus_uid' => '',
		'mod_count' => 0,
		'message'   => '一致する MOD は未検出でしたが、Nexus ユーザー名として連携登録しました。',
	);
}

/**
 * Nexus API キーで本人確認を行う。
 *
 * @param string $username 希望ユーザー名.
 * @param string $api_key  Nexus API キー.
 *
 * @return array{ok:bool,username:string,nexus_uid:string,message:string}
 */
function sevendtd_nb_validate_nexus_identity_with_api_key( $username, $api_key ) {
	$username = trim( sanitize_text_field( (string) $username ) );
	$api_key  = trim( sanitize_text_field( (string) $api_key ) );

	if ( '' === $api_key ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => 'Nexus API キーを入力してください。',
		);
	}

	$settings = sevendtd_nb_get_settings();
	// 本人確認は「ユーザー自身のキーで、ユーザー操作起点」＝AUP 準拠。
	// 公開 discovery 用の GraphQL とは別に、レガシー v1 の validate.json を使う。
	$url = 'https://api.nexusmods.com/v1/users/validate.json';

	$response = wp_remote_get(
		$url,
		array(
			'timeout' => max( 5, absint( $settings['timeout'] ) ),
			'headers' => array(
				'apikey'              => $api_key,
				'Accept'              => 'application/json',
				'User-Agent'          => (string) $settings['user_agent'],
				'Application-Name'    => (string) $settings['application_name'],
				'Application-Version' => (string) $settings['application_version'],
			),
		)
	);

	if ( is_wp_error( $response ) ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => 'Nexus API 本人確認に失敗しました。API キーが有効か確認してください。',
		);
	}

	$status = (int) wp_remote_retrieve_response_code( $response );
	if ( 200 !== $status ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => 'Nexus API 本人確認に失敗しました。API キーが有効か確認してください。',
		);
	}

	$body = (string) wp_remote_retrieve_body( $response );
	$data = json_decode( $body, true );

	if ( ! is_array( $data ) ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => 'Nexus API 本人確認レスポンスを解釈できませんでした。',
		);
	}

	$validated_username = '';
	foreach ( array( 'name', 'username', 'user_name', 'member_name' ) as $key ) {
		if ( isset( $data[ $key ] ) && ! is_array( $data[ $key ] ) ) {
			$value = trim( (string) $data[ $key ] );
			if ( '' !== $value ) {
				$validated_username = $value;
				break;
			}
		}
	}

	$validated_uid = '';
	foreach ( array( 'user_id', 'member_id', 'id' ) as $key ) {
		if ( isset( $data[ $key ] ) && ! is_array( $data[ $key ] ) ) {
			$value = trim( (string) $data[ $key ] );
			if ( '' !== $value && ctype_digit( $value ) ) {
				$validated_uid = $value;
				break;
			}
		}
	}

	if ( '' === $validated_username ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => 'Nexus API からユーザー名を取得できませんでした。',
		);
	}

	if ( sevendtd_safe_strtolower( $validated_username ) !== sevendtd_safe_strtolower( $username ) ) {
		return array(
			'ok'        => false,
			'username'  => '',
			'nexus_uid' => '',
			'message'   => '入力したユーザー名と API キーの所有者が一致しません。',
		);
	}

	return array(
		'ok'        => true,
		'username'  => $validated_username,
		'nexus_uid' => $validated_uid,
		'message'   => 'Nexus API キーによる本人確認が完了しました。',
	);
}

/**
 * アカウント連携エンドポイントの権限チェック。
 *
 * @param WP_REST_Request $request リクエスト.
 *
 * @return bool|WP_Error
 */
function sevendtd_nb_rest_account_link_permission( WP_REST_Request $request ) { // phpcs:ignore Generic.CodeAnalysis.UnusedFunctionParameter.Found
	if ( ! is_user_logged_in() ) {
		return new WP_Error( 'not_logged_in', 'ログインが必要です。', array( 'status' => 401 ) );
	}

	return true;
}

/**
 * アカウント連携保存（POST）コールバック。
 *
 * @param WP_REST_Request $request リクエスト.
 *
 * @return WP_REST_Response|WP_Error
 */
function sevendtd_nb_rest_account_link_save( WP_REST_Request $request ) {
	$user_id  = get_current_user_id();
	$username = sanitize_text_field( (string) $request->get_param( 'nexus_username' ) );
	$api_key  = sanitize_text_field( (string) $request->get_param( 'nexus_api_key' ) );

	if ( '' === $username ) {
		return new WP_Error( 'missing_username', 'nexus_username が必要です。', array( 'status' => 400 ) );
	}

	if ( '' === $api_key ) {
		return new WP_Error( 'missing_api_key', 'nexus_api_key が必要です。', array( 'status' => 400 ) );
	}

	$identity = sevendtd_nb_validate_nexus_identity_with_api_key( $username, $api_key );
	if ( ! $identity['ok'] ) {
		return new WP_REST_Response(
			array(
				'ok'      => false,
				'message' => $identity['message'],
			),
			422
		);
	}

	$username = $identity['username'];

	$verify = sevendtd_nb_verify_nexus_username( $username );

	if ( ! $verify['ok'] ) {
		return new WP_REST_Response(
			array(
				'ok'      => false,
				'message' => $verify['message'],
			),
			422
		);
	}

	$resolved_uid = '' !== $identity['nexus_uid'] ? $identity['nexus_uid'] : $verify['nexus_uid'];

	update_user_meta( $user_id, 'sevendtd_nexus_username', $username );
	update_user_meta( $user_id, 'sevendtd_nexus_user_id', $resolved_uid );
	update_user_meta( $user_id, 'sevendtd_nexus_linked_at', time() );

	return new WP_REST_Response(
		array(
			'ok'        => true,
			'username'  => $username,
			'nexus_uid' => $resolved_uid,
			'mod_count' => $verify['mod_count'],
			'message'   => $identity['message'] . ' ' . $verify['message'],
		),
		200
	);
}

/**
 * アカウント連携解除（DELETE）コールバック。
 *
 * @param WP_REST_Request $request リクエスト.
 *
 * @return WP_REST_Response
 */
function sevendtd_nb_rest_account_link_delete( WP_REST_Request $request ) { // phpcs:ignore Generic.CodeAnalysis.UnusedFunctionParameter.Found
	$user_id = get_current_user_id();
	delete_user_meta( $user_id, 'sevendtd_nexus_username' );
	delete_user_meta( $user_id, 'sevendtd_nexus_user_id' );
	delete_user_meta( $user_id, 'sevendtd_nexus_linked_at' );

	return new WP_REST_Response(
		array(
			'ok'      => true,
			'message' => '連携を解除しました。',
		),
		200
	);
}

/**
 * Modder バッジの HTML を返す。
 *
 * @param int $user_id WordPress ユーザー ID.
 *
 * @return string
 */
function sevendtd_nb_get_user_nexus_badge_html( $user_id ) {
	$account = sevendtd_nb_get_user_nexus_account( absint( $user_id ) );

	if ( '' === $account['username'] ) {
		return '';
	}

	$uid = (string) $account['nexus_uid'];
	if ( '' !== $uid ) {
		$url  = 'https://www.nexusmods.com/7daystodie/users/' . rawurlencode( $uid );
		$link = '<a href="' . esc_url( $url ) . '" target="_blank" rel="noopener noreferrer">' . esc_html( $account['username'] ) . '</a>';
	} else {
		$link = esc_html( $account['username'] );
	}

	return '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-strong sevendtd-nb-modder-badge" title="Nexus Mods: ' . esc_attr( $account['username'] ) . '">&#x1F517; Modder: ' . $link . '</span>';
}

/**
 * 特定作者の MOD 一覧をフィードおよび検索 API から収集する。
 *
 * @param string $username Nexus ユーザー名.
 * @param int    $limit    最大件数.
 *
 * @return array<int,array<string,mixed>>
 */
function sevendtd_nb_get_mods_by_author( $username, $limit = 20 ) {
	$username = trim( (string) $username );
	$limit    = max( 1, min( 50, absint( $limit ) ) );

	if ( '' === $username ) {
		return array();
	}

	$settings = sevendtd_nb_get_settings();
	$lower    = sevendtd_safe_strtolower( $username );
	$results  = array();
	$seen     = array();

	// 著者名で直接 GraphQL 取得（フィードに無い旧作も拾える）。
	$direct = sevendtd_nb_gql_fetch_mods(
		array(
			'author' => array(
				'value' => $username,
				'op'    => 'EQUALS',
			),
		),
		array( array( 'updatedAt' => array( 'direction' => 'DESC' ) ) ),
		$limit,
		'sevendtd_nb_gql_author_' . md5( $lower ),
		(int) $settings['cache_ttl']
	);
	if ( ! empty( $direct['ok'] ) && ! empty( $direct['data'] ) && is_array( $direct['data'] ) ) {
		foreach ( $direct['data'] as $mod ) {
			$key = sevendtd_nb_get_mod_key( $mod );
			if ( ! isset( $seen[ $key ] ) ) {
				$seen[ $key ] = true;
				$results[]    = $mod;
			}
		}
	}

	foreach ( sevendtd_nb_get_merged_feed_mods() as $mod ) {
		$author = sevendtd_safe_strtolower(
			sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) )
		);

		if ( $author === $lower ) {
			$key = sevendtd_nb_get_mod_key( $mod );
			if ( ! isset( $seen[ $key ] ) ) {
				$seen[ $key ] = true;
				$results[]    = $mod;
			}
		}
	}

	if ( count( $results ) < $limit ) {
		$search_result = sevendtd_nb_search_mods( $username, 0, $limit );
		if ( ! empty( $search_result['ok'] ) && ! empty( $search_result['data'] ) && is_array( $search_result['data'] ) ) {
			foreach ( $search_result['data'] as $mod ) {
				$author = sevendtd_safe_strtolower(
					sevendtd_nb_get_mod_value( $mod, array( 'uploaded_by', 'author', 'user' ) )
				);

				if ( $author === $lower ) {
						$key = sevendtd_nb_get_mod_key( $mod );
					if ( ! isset( $seen[ $key ] ) ) {
						$seen[ $key ] = true;
						$results[]    = $mod;
					}
				}
			}
		}
	}

	return array_slice( $results, 0, $limit );
}

/**
 * アカウント連携ショートコードを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_account_link_shortcode( $atts ) {
	$atts = shortcode_atts(
		array( 'title' => 'Nexus Mods アカウント連携' ),
		$atts,
		'sevendtd_nexus_account_link'
	);

	if ( ! is_user_logged_in() ) {
		return '<div class="sevendtd-nexus-notice">この機能を利用するには <a href="' . esc_url( wp_login_url( get_permalink() ) ) . '">ログイン</a> が必要です。</div>';
	}

	$user_id = get_current_user_id();
	$account = sevendtd_nb_get_user_nexus_account( $user_id );
	$linked  = '' !== $account['username'];
	$nonce   = wp_create_nonce( 'wp_rest' );
	$api_url = rest_url( 'sevendtd-nexus/v1/account-link' );

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box" id="sevendtd-account-link">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';

	if ( $linked ) {
		$linked_date = $account['linked_at'] > 0 ? (string) wp_date( 'Y-m-d', $account['linked_at'] ) : '';
		$output     .= '<div class="sevendtd-nexus-notice">';
		$output     .= '<strong>&#x1F517; 連携済み</strong>&nbsp;&nbsp;';
		$output     .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">' . esc_html( $account['username'] ) . '</span>';

		if ( '' !== $account['nexus_uid'] ) {
			$profile_url = 'https://www.nexusmods.com/7daystodie/users/' . rawurlencode( $account['nexus_uid'] );
			$output     .= '&nbsp;&nbsp;<a href="' . esc_url( $profile_url ) . '" target="_blank" rel="noopener noreferrer">Nexus プロフィールを見る &rarr;</a>';
		}

		if ( '' !== $linked_date ) {
			$output .= '<br><small>連携日: ' . esc_html( $linked_date ) . '</small>';
		}

		$output .= '</div>';
		$output .= '<button class="sevendtd-nb-account-unlink-btn" style="border:1px solid #c0392b;background:#fff;color:#c0392b;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:13px;margin-top:8px">連携解除する</button>';
	} else {
		$output .= '<p class="sevendtd-nexus-muted">本人確認のため、Nexus ユーザー名と Nexus API キーで連携します。API キーは保存しません。</p>';
		$output .= '<form class="sevendtd-nexus-form" id="sevendtd-nb-link-form" onsubmit="return false;" style="grid-template-columns:1fr auto">';
		$output .= '<div><label for="sevendtd-nb-nexus-username">Nexus Mods ユーザー名</label>';
		$output .= '<input id="sevendtd-nb-nexus-username" type="text" name="nexus_username" placeholder="例: JohnModder" autocomplete="off" style="width:100%;border:1px solid #c9d7cf;border-radius:10px;padding:10px 12px;box-sizing:border-box"></div>';
		$output .= '<div style="grid-column:1/-1"><label for="sevendtd-nb-nexus-api-key">Nexus API キー（本人確認用・保存しません）</label>';
		$output .= '<input id="sevendtd-nb-nexus-api-key" type="password" name="nexus_api_key" placeholder="Nexus の Settings > API Keys で発行" autocomplete="off" style="width:100%;border:1px solid #c9d7cf;border-radius:10px;padding:10px 12px;box-sizing:border-box"></div>';
		$output .= '<div style="display:flex;align-items:flex-end"><button type="submit" class="sevendtd-nb-link-submit" style="border:0;border-radius:999px;padding:11px 18px;background:#1e4c3c;color:#fff;font-weight:700;cursor:pointer">連携する</button></div>';
		$output .= '</form>';
		$output .= '<p id="sevendtd-nb-link-msg" class="sevendtd-nexus-muted" style="min-height:1.5em;margin-top:8px"></p>';
	}

	$output .= '</section>';
	$output .= '<script>(function(){';
	$output .= 'var apiUrl=' . wp_json_encode( esc_url_raw( $api_url ) ) . ';';
	$output .= 'var nonce=' . wp_json_encode( $nonce ) . ';';
	$output .= 'var form=document.getElementById("sevendtd-nb-link-form");';
	$output .= 'var unlinkBtn=document.querySelector(".sevendtd-nb-account-unlink-btn");';
	$output .= 'var msgEl=document.getElementById("sevendtd-nb-link-msg");';
	$output .= 'function msg(t,ok){if(msgEl){msgEl.textContent=t;msgEl.style.color=ok?"#1e6b2b":"#b02020";}}';
	$output .= 'if(form){form.addEventListener("submit",function(){';
	$output .= 'var inp=document.getElementById("sevendtd-nb-nexus-username");';
	$output .= 'var keyInp=document.getElementById("sevendtd-nb-nexus-api-key");';
	$output .= 'var u=inp?inp.value.trim():"";';
	$output .= 'var k=keyInp?keyInp.value.trim():"";';
	$output .= 'if(!u){msg("\u30e6\u30fc\u30b6\u30fc\u540d\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002",false);return;}';
	$output .= 'if(!k){msg("Nexus API \u30ad\u30fc\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002",false);return;}';
	$output .= 'var btn=form.querySelector(".sevendtd-nb-link-submit");';
	$output .= 'if(btn)btn.disabled=true;';
	$output .= 'msg("\u78ba\u8a8d\u4e2d\u2026",true);';
	$output .= 'fetch(apiUrl,{method:"POST",headers:{"Content-Type":"application/json","X-WP-Nonce":nonce},body:JSON.stringify({nexus_username:u,nexus_api_key:k})})';
	$output .= '.then(function(r){return r.json();})';
	$output .= '.then(function(d){if(d.ok){msg("\u2705 "+d.message,true);setTimeout(function(){location.reload();},1500);}else{msg("\u274c "+(d.message||"\u9023\u643a\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002"),false);if(btn)btn.disabled=false;}})';
	$output .= '.catch(function(){msg("\u901a\u4fe1\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f\u3002",false);if(btn)btn.disabled=false;});';
	$output .= '});}';
	$output .= 'if(unlinkBtn){unlinkBtn.addEventListener("click",function(){';
	$output .= 'if(!confirm("Nexus Mods \u30a2\u30ab\u30a6\u30f3\u30c8\u306e\u9023\u643a\u3092\u89e3\u9664\u3057\u307e\u3059\u304b\uff1f"))return;';
	$output .= 'fetch(apiUrl,{method:"DELETE",headers:{"X-WP-Nonce":nonce}})';
	$output .= '.then(function(r){return r.json();})';
	$output .= '.then(function(d){if(d.ok)location.reload();});';
	$output .= '});}';
	$output .= '})();</script>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_account_link', 'sevendtd_nb_render_account_link_shortcode' );

/**
 * Account-link ページかどうかを判定する。
 *
 * @return bool
 */
function sevendtd_nb_is_account_link_page() {
	if ( is_admin() || ! is_main_query() || ! is_singular() ) {
		return false;
	}

	$page = get_page_by_path( 'community/account-link' );

	return ( $page instanceof WP_Post ) && is_page( $page->ID );
}

/**
 * Account-link ページへ Nexus 連携 UI を自動追加する。
 *
 * @param string $content 本文.
 *
 * @return string
 */
function sevendtd_nb_append_account_link_content( $content ) {
	if ( ! sevendtd_nb_is_account_link_page() ) {
		return $content;
	}

	if (
		false !== strpos( $content, 'sevendtd_nexus_account_link' ) ||
		false !== strpos( $content, 'sevendtd-account-link' ) ||
		false !== strpos( $content, 'sdtd-link-guide' ) ||
		false !== strpos( $content, 'sevendtd_nexus_modder_dashboard' )
	) {
		return $content;
	}

	$extra = sevendtd_nb_render_account_link_shortcode(
		array(
			'title' => 'Nexus Mods 連携',
		)
	);

	if ( is_user_logged_in() ) {
		$account = sevendtd_nb_get_user_nexus_account( get_current_user_id() );
		if ( '' !== $account['username'] ) {
			$extra .= sevendtd_nb_render_modder_dashboard_shortcode(
				array(
					'title' => 'Nexus Mods 投稿ダッシュボード',
					'limit' => 12,
				)
			);
		}
	}

	return $content . $extra;
}
add_filter( 'the_content', 'sevendtd_nb_append_account_link_content', 10020 );

/**
 * Modder ダッシュボードショートコードを描画する。
 *
 * @param array<string,mixed> $atts 属性.
 *
 * @return string
 */
function sevendtd_nb_render_modder_dashboard_shortcode( $atts ) {
	$atts = shortcode_atts(
		array(
			'title' => '自分の投稿 MOD ダッシュボード',
			'limit' => 12,
		),
		$atts,
		'sevendtd_nexus_modder_dashboard'
	);

	if ( ! sevendtd_nb_current_user_can_use_tools() ) {
		return sevendtd_nb_render_tool_access_notice( '自分の投稿 MOD ダッシュボード' );
	}

	$user_id = get_current_user_id();
	$account = sevendtd_nb_get_user_nexus_account( $user_id );

	if ( '' === $account['username'] ) {
		return '<div class="sevendtd-nexus-notice">Nexus Mods アカウントが未連携です。<a href="/community/account-link/">アカウント連携ページで登録してください。</a></div>';
	}

	$limit    = max( 3, min( 30, absint( $atts['limit'] ) ) );
	$username = $account['username'];
	$mods     = sevendtd_nb_get_mods_by_author( $username, $limit );

	$total_dl      = 0;
	$total_endorse = 0;

	foreach ( $mods as $mod ) {
		$total_dl      += sevendtd_nb_get_mod_downloads( $mod );
		$total_endorse += sevendtd_nb_get_mod_endorsements( $mod );
	}

	$output  = sevendtd_nb_get_shared_styles();
	$output .= '<section class="sevendtd-nexus-box">';
	$output .= '<h2>' . esc_html( (string) $atts['title'] ) . '</h2>';
	$output .= '<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px">';
	$output .= sevendtd_nb_get_user_nexus_badge_html( $user_id );

	if ( '' !== $account['nexus_uid'] ) {
		$profile_url = 'https://www.nexusmods.com/7daystodie/users/' . rawurlencode( $account['nexus_uid'] );
		$output     .= '<a href="' . esc_url( $profile_url ) . '" target="_blank" rel="noopener noreferrer" class="sevendtd-nexus-actions">Nexus プロフィールを見る &rarr;</a>';
	}

	$output .= '</div>';
	$output .= '<div class="sevendtd-nexus-result-summary" style="margin:0 0 16px">';
	$output .= '<span class="sevendtd-nexus-pill">MOD 数: ' . esc_html( (string) count( $mods ) ) . '</span>';
	$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-score">総 DL 数: ' . esc_html( (string) number_format_i18n( $total_dl ) ) . '</span>';
	$output .= '<span class="sevendtd-nexus-pill sevendtd-nexus-pill-diff">総 Endorse 数: ' . esc_html( (string) number_format_i18n( $total_endorse ) ) . '</span>';
	$output .= '</div>';

	if ( empty( $mods ) ) {
		$output .= '<p class="sevendtd-nexus-muted">フィード内に投稿 MOD が見つかりませんでした。フィードが更新されると表示されます。</p>';
	} else {
		$output .= sevendtd_nb_render_mod_cards(
			$mods,
			array(
				'show_image'   => true,
				'compact_meta' => false,
			)
		);
	}

	$output .= '</section>';

	return $output;
}
add_shortcode( 'sevendtd_nexus_modder_dashboard', 'sevendtd_nb_render_modder_dashboard_shortcode' );
