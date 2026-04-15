import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from transformations import process_and_filter_image

load_dotenv()

WP_BASE = os.getenv("WP_BASE_URL")
print(f"DEBUG: Connecting to WP at -> {WP_BASE}") # Add this!

AUTH = HTTPBasicAuth(os.getenv("WP_USERNAME"), os.getenv("WP_APP_PASSWORD"))

def upload_processed_image(image_url: str, category: str, business_name: str) -> int:
    """The Gate Logic: Scraped -> Filter -> Resolution -> (Optional) Upscale"""
    
    # 1. Get the Scraped Image
    response = requests.get(image_url)
    if not response.ok:
        print(f"❌ Failed to download image from {image_url}. Status: {response.status_code}")
        return None
    img_bytes = response.content

    # Refactored: Use the centralized processing function from transformations.py
    final_bytes = process_and_filter_image(
        image_bytes=img_bytes, category=category, business_name=business_name
    )

    # Proceed to upload the final binary (Original or Enhanced)
    return upload_binary_to_wp(final_bytes, f"{business_name.replace(' ', '_')}.jpg")

def upload_binary_to_wp(image_bytes: bytes, filename: str) -> int:
    """Uploads image bytes to WP Media Library and returns the ID."""
    if not image_bytes:
        return None

    url = f"{WP_BASE}/wp/v2/media"
    
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "image/jpeg"
    }

    response = requests.post(url, headers=headers, data=image_bytes, auth=AUTH)

    if response.status_code == 201:
        print(f"✅ Uploaded {filename} to WordPress Media Library.")
        return response.json().get("id")
    else:
        print(f"❌ Failed to upload {filename}. Status: {response.status_code}, Response: {response.text}")
    return None

def upload_local_media(file_path: str) -> int:
    """Uploads a local file to WP Media Library and returns the ID."""
    if not file_path or not os.path.exists(file_path):
        return None

    url = f"{WP_BASE}/wp/v2/media"
    filename = os.path.basename(file_path)
    
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "image/jpeg"
    }

    with open(file_path, "rb") as img:
        response = requests.post(url, headers=headers, data=img, auth=AUTH)

    if response.status_code == 201:
        return response.json().get("id")
    return None

def ingest_to_wordpress(payload: dict, source_image_url: str = None):
    """Pushes data, handles the gallery loop, and maps IDs."""
    cpt_endpoint = f"{WP_BASE}/wp/v2/directory_listing"
    
    featured_media_id = None
    # GATEKEEPER LOGIC for the scraped "Ground Truth" image
    if source_image_url:
        print("🔎 Processing scraped image URL as potential featured image...")
        featured_media_id = upload_processed_image(
            image_url=source_image_url,
            category=payload['acf_fields']['business_category'],
            business_name=payload['title']
        )

    # 1. Process Gallery Images (Convert Filenames -> Media IDs)
    gallery_ids = []
    for img_path in payload["acf_fields"].get("gallery_images", []):
        media_id = upload_local_media(img_path)
        if media_id:
            gallery_ids.append(media_id)

    # Update ACF to use IDs instead of strings
    payload["acf_fields"]["gallery_images"] = gallery_ids

    # Determine the final featured image. Prioritize the first gallery image if it exists.
    final_featured_media_id = gallery_ids[0] if gallery_ids else featured_media_id

    # 2. Check for existing post (Idempotency)
    search_params = {"meta_key": "place_id", "meta_value": payload['place_id']}
    search_res = requests.get(cpt_endpoint, params=search_params, auth=AUTH)
    existing_posts = search_res.json()

    wp_data = {
        "title": payload["title"],
        "content": payload["content"],
        "status": "publish",
        "acf": payload["acf_fields"],
        "meta": {"place_id": payload["place_id"]}
    }
    # Only add featured_media if we have one, to avoid sending 'None'
    if final_featured_media_id:
        wp_data["featured_media"] = final_featured_media_id

    if existing_posts:
        post_id = existing_posts[0]['id']
        response = requests.post(f"{cpt_endpoint}/{post_id}", json=wp_data, auth=AUTH)
        if response.status_code == 200:
            print(f"🔄 Updated {payload['title']} (ID: {post_id})")
        else:
            print(f"❌ Failed to update {payload['title']}. Status: {response.status_code}, Response: {response.text}")
    else:
        response = requests.post(cpt_endpoint, json=wp_data, auth=AUTH)
        if response.status_code == 201:
            print(f"✅ Created {payload['title']} (ID: {response.json()['id']})")
        else:
            print(f"❌ Failed to create {payload['title']}. Status: {response.status_code}, Response: {response.text}")