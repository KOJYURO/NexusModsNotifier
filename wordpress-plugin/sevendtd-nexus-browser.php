<?php
/**
 * Plugin Name: 7DTD Nexus Browser
 * Description: Nexus Mods API を使った MOD 検索とカテゴリ別一覧のショートコードを提供します。
 * Version: 0.1.0
 * Author: 7daystodie.jp
 *
 * @package sevendtd-nexus-browser
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'SEVENDTD_NB_VERSION', '0.1.0' );
define( 'SEVENDTD_NB_PLUGIN_FILE', __FILE__ );
define( 'SEVENDTD_NB_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );

require_once SEVENDTD_NB_PLUGIN_DIR . 'includes/plugin.php';

register_activation_hook( SEVENDTD_NB_PLUGIN_FILE, 'sevendtd_nb_activate_plugin' );
