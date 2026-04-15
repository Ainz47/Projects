import json
from image_generator import generate_restaurant_image
from pipeline_processor import process_scraped_data
from wp_importer import ingest_to_wordpress
from scraper import scrape_google_maps_data

# 1. Configuration
target_business = "Allegory"
target_location = "Naperville, IL"
target_category = "Premium Farm-to-Table Restaurant"

# 2. Step One: Scrape the "Ground Truth"
scraped_info = scrape_google_maps_data(target_business, target_location)

if scraped_info:
    # 3. Step Two: Process scraped data and generate the story ONCE.
    final_payload = process_scraped_data(scraped_info)
    
    # 4. Step Three: Create the initial post with the scraped image.
    # This establishes the "ground truth" and creates the post ID.
    ingest_to_wordpress(final_payload, source_image_url=scraped_info['image_url'])
    
    # 5. Step Four: Generate new AI visuals for the gallery.
    print(f"📸 Generating Gallery Images for {scraped_info['name']}...")
    exterior_img = generate_restaurant_image(scraped_info['name'], f"Exterior of {target_category}", scraped_info['city'])
    interior_img = generate_restaurant_image(scraped_info['name'], f"Interior dining room of {target_category}", scraped_info['city'])
    
    # 6. Step Five: Update the payload with the new AI-generated images.
    # We are MODIFYING the existing payload, not re-creating it. This is more efficient.
    # We also filter out any 'None' values if image generation failed.
    generated_images = [img for img in [exterior_img, interior_img] if img is not None]
    final_payload['acf_fields']['gallery_images'] = generated_images
    
    # Save a local JSON copy for verification
    with open("naperville_sample.json", "w") as f:
        json.dump(final_payload, f, indent=4)
    print("💾 Saved Ivy-Level JSON sample to disk.")

    # 7. Step Six: Update the WordPress post with the full gallery.
    # This second call will find the existing post (by place_id) and add the gallery.
    # NOTE: This requires the functions.php change in WordPress to work correctly.
    ingest_to_wordpress(final_payload)
    
    print("\n🚀 Pipeline Execution Complete!")
else:
    print("❌ Pipeline aborted: Could not find business data on Google Maps.")