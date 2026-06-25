<?php
/**
 * Plugin Name: 7DTD Nexus Browser
 * Description: Nexus Mods 公開 GraphQL V2 API（APIキー不要・公開データのみ）を使った 7 Days to Die MOD の発見・日本語検索・カテゴリ別一覧ショートコードを提供します。原ページへの誘導を前提とした discovery インターフェースです。
 * Version: 0.2.0
 * Author: 7daystodie.jp
 *
 * @package sevendtd-nexus-browser
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'SEVENDTD_NB_VERSION', '0.2.0' );
define( 'SEVENDTD_NB_PLUGIN_FILE', __FILE__ );
define( 'SEVENDTD_NB_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );

require_once SEVENDTD_NB_PLUGIN_DIR . 'includes/plugin.php';

register_activation_hook( SEVENDTD_NB_PLUGIN_FILE, 'sevendtd_nb_activate_plugin' );
