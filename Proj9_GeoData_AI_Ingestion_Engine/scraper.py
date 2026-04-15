from playwright.sync_api import sync_playwright
import urllib.parse
import json

def scrape_google_maps_data(business_name: str, location: str) -> dict:
    """
    Searches Google Maps for a business and extracts the high-res cover image 
    and basic details to feed into the WordPress/Gemini pipeline.
    """
    print(f"🕵️‍♂️ Searching Google Maps for: {business_name} in {location}")
    
    # Format the search query for the URL
    query = urllib.parse.quote(f"{business_name} {location}")
    search_url = f"https://www.google.com/maps/search/{query}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            
            # 1. Wait for the left-hand panel to load the cover photo
            # Google Maps usually puts the cover photo in a button with an aria-label starting with "Photo"
            photo_selector = 'button[aria-label*="Photo"] img'
            page.wait_for_selector(photo_selector, timeout=10000)
            
            raw_img_url = page.locator(photo_selector).first.get_attribute("src")
            
            # 2. THE PRO-MOVE: Image Upscaling
            # Google Maps thumbnail URLs look like: .../p/AF1QipM...?w=256&h=256&k=no
            # We want to replace the width/height parameters to get a high-res image for WP
            high_res_img_url = raw_img_url.split("=")[0] + "=w1080-h720-k-no"
            print("✅ Extracted High-Resolution Image URL!")

            # 3. Extract Basic Data (Name & Address)
            # We grab the exact name and address Google uses to ensure accuracy
            try:
                extracted_name = page.locator('h1').first.inner_text()
            except:
                extracted_name = business_name

            # Address is usually in a button with a specific data-item-id
            try:
                address_selector = 'button[data-item-id="address"]'
                page.wait_for_selector(address_selector, timeout=5000)
                extracted_address = page.locator(address_selector).first.inner_text()
            except:
                extracted_address = location # Fallback
                
            # --- Map to our standard dictionary ---
            scraped_payload = {
                "name": extracted_name.strip(),
                "category": "Restaurant", # You can pass this in as a parameter later
                "address": extracted_address.strip(),
                "city": location,
                "image_url": high_res_img_url
            }
            
            print(f"✅ Successfully scraped Google Maps data for: {scraped_payload['name']}")
            return scraped_payload
            
        except Exception as e:
            print(f"❌ Google Maps scraping failed (Bot detection or timeout): {e}")
            return None
        finally:
            browser.close()

# Quick Local Test
if __name__ == "__main__":
    # Test it with a new restaurant to prove the pipeline works!
    test_business = "Gordon Ramsay Hell's Kitchen"
    test_location = "Chicago, IL"
    
    data = scrape_google_maps_data(test_business, test_location)
    print(json.dumps(data, indent=4))