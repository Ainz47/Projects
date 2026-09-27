from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "wp-plugin/proj9-directory-listing/proj9-directory-listing.php"


def test_plugin_registers_everything_the_client_writes():
    """PHP can't run in CI here, so this keeps the plugin and the Python client in agreement."""
    php = PLUGIN.read_text(encoding="utf-8")
    assert "register_post_type('directory_listing'" in php
    assert "'show_in_rest' => true" in php
    for key in ("place_id", "business_address", "business_category", "business_city", "gallery_images"):
        assert f"'{key}'" in php, key
    assert "rest_directory_listing_query" in php
