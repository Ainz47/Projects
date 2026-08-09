<?php
/**
 * Plugin Name: RR Contact Handler
 * Description: Captures contact form submissions, stores leads in WP, and emails the site owner.
 * Version: 1.2
 * Author: Rank & Rent Deployer
 */

defined('ABSPATH') || exit;

// ── Register rr_contact_email so WP REST /settings can write it ─────────────
add_action('init', function () {
    register_setting('general', 'rr_contact_email', [
        'type'         => 'string',
        'description'  => 'Email address that receives lead notifications',
        'show_in_rest' => true,
        'default'      => '',
    ]);
});

// ── Custom post type: rr_lead ────────────────────────────────────────────────
add_action('init', function () {
    register_post_type('rr_lead', [
        'labels'      => ['name' => 'Leads', 'singular_name' => 'Lead',
                          'add_new' => 'Add Lead', 'all_items' => 'All Leads'],
        'public'      => false,
        'show_ui'     => true,
        'show_in_menu'=> true,
        'supports'    => ['title'],
        'menu_icon'   => 'dashicons-email-alt',
        'menu_position'=> 25,
    ]);
});

// ── AJAX handler (works for logged-in and anonymous users) ───────────────────
add_action('wp_ajax_nopriv_rr_contact', 'rr_handle_contact');
add_action('wp_ajax_rr_contact',        'rr_handle_contact');

function rr_handle_contact() {
    $name    = sanitize_text_field($_POST['rr_name']    ?? '');
    $email   = sanitize_email($_POST['rr_email']        ?? '');
    $phone   = sanitize_text_field($_POST['rr_phone']   ?? '');
    $message = sanitize_textarea_field($_POST['rr_message'] ?? '');
    $source  = sanitize_text_field($_POST['source']     ?? '');

    if (!$name || !is_email($email)) {
        wp_send_json_error('Please provide your name and a valid email address.');
    }

    // Store lead as CPT
    $post_id = wp_insert_post([
        'post_type'   => 'rr_lead',
        'post_title'  => esc_html("$name — $email"),
        'post_status' => 'publish',
    ]);

    if ($post_id && !is_wp_error($post_id)) {
        update_post_meta($post_id, 'rr_name',      $name);
        update_post_meta($post_id, 'rr_email',     $email);
        update_post_meta($post_id, 'rr_phone',     $phone);
        update_post_meta($post_id, 'rr_message',   $message);
        update_post_meta($post_id, 'rr_source',    $source);
        update_post_meta($post_id, 'rr_submitted', current_time('mysql'));
    }

    // Send email notification
    $to      = get_option('rr_contact_email') ?: get_option('admin_email');
    $subject = get_bloginfo('name') . " — New lead from $name";
    $body    = "You have a new lead from your website.\n\n"
             . "Name:    $name\n"
             . "Email:   $email\n"
             . "Phone:   $phone\n"
             . "Message: $message\n"
             . "Page:    $source\n"
             . "Time:    " . current_time('mysql');

    wp_mail($to, $subject, $body);

    wp_send_json_success('Thank you! We\'ll be in touch soon.');
}

// ── Option writer (used by deployer to configure WP Mail SMTP etc.) ─────────
add_action('wp_ajax_rr_set_option', function () {
    // Without the nonce and the allowlist this is an arbitrary-option write
    // reachable by CSRF, which escalates to admin via users_can_register +
    // default_role. Only options this plugin owns may be set here.
    $allowed = ['rr_footer_config', 'rr_contact_email'];

    check_ajax_referer('wp_rest', '_wpnonce');

    if (!current_user_can('manage_options')) {
        wp_send_json_error('Unauthorized', 403);
    }
    $key   = sanitize_key($_POST['option_key']   ?? '');
    $raw   = stripslashes($_POST['option_value'] ?? '');
    if (!in_array($key, $allowed, true)) {
        wp_send_json_error('Option not permitted', 403);
    }
    if ($raw === '') {
        wp_send_json_error('Missing params');
    }
    $value = json_decode($raw, true);
    update_option($key, $value !== null ? $value : $raw, false);
    wp_send_json_success('saved');
});

// ── Admin list columns ───────────────────────────────────────────────────────
add_filter('manage_rr_lead_posts_columns', function ($cols) {
    return [
        'cb'        => $cols['cb'],
        'title'     => 'Name / Email',
        'rr_phone'  => 'Phone',
        'rr_source' => 'Source Page',
        'rr_date'   => 'Submitted',
    ];
});

add_action('manage_rr_lead_posts_custom_column', function ($col, $post_id) {
    switch ($col) {
        case 'rr_phone':  echo esc_html(get_post_meta($post_id, 'rr_phone',     true)); break;
        case 'rr_source': echo esc_html(get_post_meta($post_id, 'rr_source',    true)); break;
        case 'rr_date':   echo esc_html(get_post_meta($post_id, 'rr_submitted', true)); break;
    }
}, 10, 2);

add_filter('manage_edit-rr_lead_sortable_columns', function ($cols) {
    $cols['rr_date'] = 'rr_date';
    return $cols;
});

// ── Mobile CSS fixes ─────────────────────────────────────────────────────────
// 1) Colored/dark background sections: stretch to full viewport width (removes
//    the floating-card look from Gutenberg's constrained max-width).
// 2) Stacked columns + constrained text groups: restore 16px side padding.
// 3) Media-text content when stacked: 16px side padding.
// Priority 999 ensures this runs after all content CSS in the document.
add_action('wp_footer', function () {
    echo '<style>'
       . '@media(max-width:767px){'
       .   '.wp-block-group.has-background:not(.alignfull):not(.has-border-color){width:100vw!important;max-width:100vw!important;margin-left:calc(50% - 50vw)!important;margin-right:0!important;box-sizing:border-box!important;padding-top:32px!important;padding-bottom:32px!important;margin-top:0!important;margin-bottom:0!important}'
       .   '.wp-block-columns>.wp-block-column{padding-left:16px!important;padding-right:16px!important}'
       .   '.is-layout-constrained:not(.alignfull):not(.has-background){padding-left:16px!important;padding-right:16px!important}'
       .   '.is-stacked-on-mobile .wp-block-media-text__content{padding-left:16px!important;padding-right:16px!important}'
       .   '.wp-block-media-text.is-stacked-on-mobile{margin-top:0!important;margin-bottom:0!important}'
       .   '.wp-block-media-text.is-stacked-on-mobile:not(.wp-block-group *){background-color:#f5f5f5!important;padding-bottom:32px!important}'
       . '}</style>';
}, 999);

// ── Rich footer ───────────────────────────────────────────────────────────────
add_action('wp_footer', function () {
    $cfg = get_option('rr_footer_config');
    if (empty($cfg['enabled'])) return;

    $name    = esc_html($cfg['business_name'] ?? '');
    $city    = esc_html($cfg['city']          ?? '');
    $state   = esc_html($cfg['state']         ?? '');
    $phone   = esc_html($cfg['phone']         ?? '');
    $pc      = esc_attr($cfg['primary_color'] ?? '#ff5e14');
    $dc      = esc_attr($cfg['dark_color']    ?? '#1a1a1a');
    $year    = date('Y');
    $services = $cfg['services'] ?? [];

    $svc_links = '';
    foreach ($services as $svc) {
        $svc_name = esc_html($svc['name'] ?? '');
        $svc_slug = esc_attr($svc['slug'] ?? '');
        $svc_links .= "<li><a href=\"/services/{$svc_slug}/\">{$svc_name}</a></li>";
    }

    echo <<<HTML
<style>
.site-footer{display:none!important}
.rr-footer{background:{$dc};color:#ccc;font-family:inherit;border-top:3px solid {$pc}}
.rr-footer-main{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:48px;padding:52px 24px 48px}
.rr-footer-logo{font-size:20px;font-weight:800;color:#fff;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;line-height:1.2}
.rr-footer-brand p{font-size:13px;color:#888;margin:4px 0 0}
.rr-footer h4{color:{$pc};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 16px}
.rr-footer ul{list-style:none;margin:0;padding:0}
.rr-footer ul li{margin-bottom:10px}
.rr-footer ul li a{color:#aaa;text-decoration:none;font-size:14px;transition:color .2s}
.rr-footer ul li a:hover{color:{$pc}}
.rr-footer-contact p{font-size:14px;color:#aaa;margin:0 0 12px;display:flex;align-items:flex-start;gap:10px}
.rr-footer-contact a{color:#aaa;text-decoration:none}
.rr-footer-contact a:hover{color:{$pc}}
.rr-footer-bar{border-top:2px solid {$pc};padding:16px 24px;font-size:12px;color:#666}
.rr-footer-bar-inner{max-width:1100px;margin:0 auto}
@media(max-width:900px){
  .rr-footer-main{grid-template-columns:1fr 1fr;gap:36px}
  .rr-footer-brand{grid-column:1/-1}
}
@media(max-width:560px){
  .rr-footer-main{grid-template-columns:1fr;gap:28px;padding:40px 24px 36px}
  .rr-footer-brand{text-align:center}
  .rr-footer h4{text-align:center}
  .rr-footer ul{text-align:center}
  .rr-footer-contact p{justify-content:center}
  .rr-footer-bar{text-align:center}
}
</style>
<footer class="rr-footer">
  <div class="rr-footer-main">
    <div class="rr-footer-brand">
      <div class="rr-footer-logo">{$name}</div>
      <p>{$city}, {$state}</p>
    </div>
    <div class="rr-footer-services">
      <h4>Services</h4>
      <ul>{$svc_links}</ul>
    </div>
    <div class="rr-footer-contact">
      <h4>Contact</h4>
      <p>📍 {$city}, {$state}</p>
      <p>📞 <a href="tel:{$phone}">{$phone}</a></p>
    </div>
  </div>
  <div class="rr-footer-bar">
    <div class="rr-footer-bar-inner">Copyright {$year} | {$name}</div>
  </div>
</footer>
HTML;
});
