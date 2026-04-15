import json
import requests

# Import the components we want to demonstrate
from scraper import scrape_google_maps_data
from pipeline_processor import process_scraped_data
from wp_importer import ingest_to_wordpress
# IMPORTANT: We import from a special 'demo' version of the image generator
from image_generator_demo import generate_restaurant_image

def run_demonstration():
    """
    This script demonstrates the full pipeline's resilience for a stakeholder,
    mirroring the logic of `run_pipeline.py`.

    - Fallback 1 (Enhancement): If AI upscaling of the scraped image fails,
      it uses the original image.
    - Fallback 2 (Generation): If AI generation of new gallery images fails,
      this demo version falls back to using copies of the original scraped image.

    The final JSON output is identical in format to the main pipeline's output.
    """
    print("🚀 Starting Full Pipeline Resilience Demonstration...")
    print("="*60)
    print("NOTE: This requires the mock_wp.py server to be running in another terminal.")
    print("`uvicorn mock_wp:app --reload`")
    print("="*60)

    # --- Step 1: Configuration & Scraping (Identical to run_pipeline.py) ---
    target_business = "Allegory"
    target_location = "Naperville, IL"
    target_category = "Premium Farm-to-Table Restaurant"
    print(f"\n[PHASE 1: INITIAL POST CREATION]")
    scraped_info = scrape_google_maps_data(target_business, target_location)

    if not scraped_info:
        print("❌ Demonstration failed: Could not scrape initial data.")
        return
    
    # --- NEW: Download the original image to use for fallbacks ---
    original_image_bytes = None
    try:
        response = requests.get(scraped_info['image_url'])
        response.raise_for_status()
        original_image_bytes = response.content
        print("✅ Original scraped image downloaded for fallback use in this demo.")
    except requests.RequestException as e:
        print(f"⚠️ Could not download original image for fallback demo: {e}")

    # --- Step 2: Process Data & Generate Story (Identical to run_pipeline.py) ---
    final_payload = process_scraped_data(scraped_info)

    # --- Step 3: Ingest Initial Post & Trigger ENHANCEMENT FALLBACK ---
    print("\nDEMO POINT 1: Calling ingest_to_wordpress.")
    print("This will trigger the image processing gates. We expect the AI enhancement to fail and fall back to using the original scraped image.")
    ingest_to_wordpress(final_payload, source_image_url=scraped_info['image_url'])

    # --- Step 4: Generate Gallery Images & Trigger GENERATION FALLBACK ---
    print("\n[PHASE 2: POST ENRICHMENT]")
    print("\nDEMO POINT 2: Generating gallery images.")
    print("We expect the AI image generation to fail and fall back to creating copies of the original scraped image.")
    
    # Pass the downloaded bytes to the demo function
    exterior_img = generate_restaurant_image(
        scraped_info['name'], 
        f"Exterior of {target_category}", 
        scraped_info['city'],
        fallback_image_bytes=original_image_bytes
    )
    interior_img = generate_restaurant_image(
        scraped_info['name'], 
        f"Interior dining room of {target_category}", 
        scraped_info['city'],
        fallback_image_bytes=original_image_bytes
    )

    # --- Step 5: Update Payload with Fallback Assets (Identical to run_pipeline.py) ---
    generated_images = [img for img in [exterior_img, interior_img] if img is not None]
    final_payload['acf_fields']['gallery_images'] = generated_images

    # --- Step 6: Save Final JSON to Demonstrate Format ---
    output_filename = "pipeline_demonstration_output.json"
    with open(output_filename, "w") as f:
        json.dump(final_payload, f, indent=4)
    print(f"\n✅ Final payload constructed. Saved to '{output_filename}'")

    print(f"\n--- Contents of {output_filename} (matches naperville_sample.json format) ---")
    print(json.dumps(final_payload, indent=4))
    print("--------------------------------------------------------------------------")

    # --- Step 7: Update the Post with the Gallery ---
    print("\nDEMO POINT 3: Updating the post with the gallery of fallback images.")
    ingest_to_wordpress(final_payload)

    print("\n🏁 Demonstration Complete.")

if __name__ == "__main__":
    run_demonstration()