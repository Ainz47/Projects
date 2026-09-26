<?php
/**
 * Plugin Name: RR WP Abilities
 * Description: Gutenberg page abilities for Rank & Rent v2 template building via MCP
 * Version: 1.0.0
 */

add_action( 'wp_abilities_api_categories_init', function () {
	wp_register_ability_category(
		'rr-deployer',
		array(
			'label'       => 'Rank & Rent Deployer',
			'description' => 'Abilities for building and reading Gutenberg page templates for the Rank & Rent v2 deployer.',
		)
	);
} );

add_action( 'wp_abilities_api_init', function () {

	wp_register_ability(
		'rr/create-page',
		array(
			'label'            => 'Create Page',
			'description'      => 'Creates a WordPress page with Gutenberg block content. Returns the new page ID and URL.',
			'category'         => 'rr-deployer',
			'input_schema'     => array(
				'type'       => 'object',
				'properties' => array(
					'title'   => array( 'type' => 'string', 'description' => 'Page title' ),
					'content' => array( 'type' => 'string', 'description' => 'Gutenberg block markup (raw block HTML with wp: comments)' ),
					'status'  => array( 'type' => 'string', 'description' => 'publish or draft', 'default' => 'draft' ),
					'slug'    => array( 'type' => 'string', 'description' => 'URL slug (optional)' ),
				),
				'required'   => array( 'title', 'content' ),
			),
			'output_schema'    => array(),
			'execute_callback' => static function ( array $input ) {
				$args = array(
					'post_title'   => sanitize_text_field( $input['title'] ),
					'post_content' => $input['content'],
					'post_status'  => isset( $input['status'] ) ? sanitize_key( $input['status'] ) : 'draft',
					'post_type'    => 'page',
					// Astra: hide the page-header title banner by default — every
					// page built by this tool ships its own in-content hero instead.
					'meta_input'   => array(
						'site-post-title'            => 'disabled',
						'_astra-site-sidebar-layout' => 'no-sidebar',
					),
				);
				if ( ! empty( $input['slug'] ) ) {
					$args['post_name'] = sanitize_title( $input['slug'] );
				}
				$id = wp_insert_post( $args, true );
				if ( is_wp_error( $id ) ) {
					return array( 'error' => $id->get_error_message() );
				}
				return array(
					'id'   => $id,
					'url'  => get_permalink( $id ),
					'edit' => admin_url( 'post.php?post=' . $id . '&action=edit' ),
				);
			},
			'permission_callback' => static function () {
				return current_user_can( 'publish_pages' );
			},
			'meta'             => array( 'mcp' => array( 'public' => true ) ),
		)
	);

	wp_register_ability(
		'rr/get-page',
		array(
			'label'            => 'Get Page Content',
			'description'      => 'Retrieves the raw Gutenberg block markup (content.raw) and metadata for a page by ID.',
			'category'         => 'rr-deployer',
			'input_schema'     => array(
				'type'       => 'object',
				'properties' => array(
					'id' => array( 'type' => 'integer', 'description' => 'Page ID' ),
				),
				'required'   => array( 'id' ),
			),
			'output_schema'    => array(),
			'execute_callback' => static function ( array $input ) {
				$post = get_post( (int) $input['id'] );
				if ( ! $post ) {
					return array( 'error' => 'Page not found' );
				}
				return array(
					'id'           => $post->ID,
					'title'        => $post->post_title,
					'content_raw'  => $post->post_content,
					'status'       => $post->post_status,
					'url'          => get_permalink( $post->ID ),
					'edit'         => admin_url( 'post.php?post=' . $post->ID . '&action=edit' ),
				);
			},
			'permission_callback' => static function () {
				return current_user_can( 'edit_pages' );
			},
			'meta'             => array( 'mcp' => array( 'public' => true ) ),
		)
	);

	wp_register_ability(
		'rr/update-page',
		array(
			'label'            => 'Update Page Content',
			'description'      => 'Updates an existing page\'s Gutenberg block content by ID.',
			'category'         => 'rr-deployer',
			'input_schema'     => array(
				'type'       => 'object',
				'properties' => array(
					'id'      => array( 'type' => 'integer', 'description' => 'Page ID' ),
					'content' => array( 'type' => 'string', 'description' => 'New Gutenberg block markup' ),
					'title'   => array( 'type' => 'string', 'description' => 'New page title (optional)' ),
				),
				'required'   => array( 'id', 'content' ),
			),
			'output_schema'    => array(),
			'execute_callback' => static function ( array $input ) {
				$args = array(
					'ID'           => (int) $input['id'],
					'post_content' => $input['content'],
				);
				if ( ! empty( $input['title'] ) ) {
					$args['post_title'] = sanitize_text_field( $input['title'] );
				}
				$id = wp_update_post( $args, true );
				if ( is_wp_error( $id ) ) {
					return array( 'error' => $id->get_error_message() );
				}
				return array( 'id' => $id, 'url' => get_permalink( $id ) );
			},
			'permission_callback' => static function () {
				return current_user_can( 'edit_pages' );
			},
			'meta'             => array( 'mcp' => array( 'public' => true ) ),
		)
	);

	wp_register_ability(
		'rr/list-pages',
		array(
			'label'            => 'List Pages',
			'description'      => 'Lists all WordPress pages with their IDs, titles, slugs, and URLs.',
			'category'         => 'rr-deployer',
			'input_schema'     => array( 'type' => 'object', 'properties' => array() ),
			'output_schema'    => array(),
			'execute_callback' => static function ( array $input ) {
				$pages = get_posts( array(
					'post_type'      => 'page',
					'post_status'    => array( 'publish', 'draft' ),
					'posts_per_page' => 100,
					'orderby'        => 'title',
					'order'          => 'ASC',
				) );
				return array_map( static function ( $p ) {
					return array(
						'id'     => $p->ID,
						'title'  => $p->post_title,
						'slug'   => $p->post_name,
						'status' => $p->post_status,
						'url'    => get_permalink( $p->ID ),
					);
				}, $pages );
			},
			'permission_callback' => static function () {
				return current_user_can( 'edit_pages' );
			},
			'meta'             => array( 'mcp' => array( 'public' => true ) ),
		)
	);

} );
