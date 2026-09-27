<?php
/**
 * Plugin Name: Proj9 Directory Listing
 * Description: The directory_listing post type, the meta the Proj9 pipeline writes, and a ?place_id= REST lookup so re-runs update instead of duplicating.
 * Version: 1.1.0
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('init', 'proj9_register_listing');

// Register once on activation too, then flush, so /listings/ works on a fresh site without re-saving permalinks.
register_activation_hook(__FILE__, function () {
    proj9_register_listing();
    flush_rewrite_rules();
});

function proj9_register_listing() {
    register_post_type('directory_listing', [
        'label'        => 'Directory Listings',
        'public'       => true,
        'has_archive'  => true,
        'rewrite'      => ['slug' => 'listings'],
        'show_in_rest' => true,
        'rest_base'    => 'directory_listing',
        'supports'     => ['title', 'editor', 'thumbnail', 'custom-fields'],
    ]);

    $can_edit = function () {
        return current_user_can('edit_posts');
    };
    foreach (['place_id', 'business_address', 'business_category', 'business_city'] as $key) {
        register_post_meta('directory_listing', $key, [
            'type' => 'string', 'single' => true, 'show_in_rest' => true, 'auth_callback' => $can_edit,
        ]);
    }
    register_post_meta('directory_listing', 'gallery_images', [
        'type'          => 'array',
        'single'        => true,
        'auth_callback' => $can_edit,
        'show_in_rest'  => ['schema' => ['type' => 'array', 'items' => ['type' => 'integer']]],
    ]);
}

// GET /wp/v2/directory_listing?place_id=<md5> : exact match on that one meta key only.
add_filter('rest_directory_listing_query', function ($args, $request) {
    $place_id = $request->get_param('place_id');
    if (is_string($place_id) && preg_match('/^[a-f0-9]{32}$/', $place_id)) {
        $args['meta_query'] = [['key' => 'place_id', 'value' => $place_id]];
    }
    return $args;
}, 10, 2);

// Show the scraped photo above the story, and the address and gallery under it, on the public listing page.
// Block themes already render the featured image from their single template, so the plugin adds its own copy
// only on classic themes. Sites can override that with the proj9_show_listing_photo filter.
add_filter('the_content', function ($content) {
    if (!is_singular('directory_listing') || !in_the_loop()) {
        return $content;
    }
    $id = get_the_ID();
    if (has_post_thumbnail($id) && apply_filters('proj9_show_listing_photo', !wp_is_block_theme())) {
        $content = get_the_post_thumbnail($id, 'large', ['class' => 'listing-photo']) . $content;
    }
    $html = '';
    $address = get_post_meta($id, 'business_address', true);
    if ($address) {
        $html .= '<p class="listing-address"><strong>Address:</strong> ' . esc_html($address) . '</p>';
    }
    $gallery = array_filter(array_map('intval', (array) get_post_meta($id, 'gallery_images', true)));
    if ($gallery) {
        $html .= '<h3>Gallery</h3><p class="listing-gallery-note"><em>AI-generated illustrations, not photos of the venue.</em></p>';
        $html .= '<div class="listing-gallery" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">';
        foreach ($gallery as $media_id) {
            $html .= wp_get_attachment_image($media_id, 'large', false, ['style' => 'width:100%;height:auto']);
        }
        $html .= '</div>';
    }
    return $content . $html;
});
