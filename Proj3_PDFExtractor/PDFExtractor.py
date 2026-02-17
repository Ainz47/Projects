import requests
import io
import pdfplumber
from playwright.sync_api import sync_playwright

def robust_discovery(target_url):
    print(f"🔍 Investigating: {target_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            response = page.goto(target_url, wait_until="networkidle", timeout=30000)
            
            # Check for 404 or other errors
            if response.status != 200:
                print(f"❌ ERROR: Server returned status {response.status}")
                return []

            # Capture a screenshot to see what the script "sees"
            page.screenshot(path="debug_view.png")
            print("📸 Screenshot saved as debug_view.png")

            # Deep link discovery
            links = page.eval_on_selector_all('a', 
                "elements => elements.map(e => e.href).filter(href => href.toLowerCase().includes('.pdf'))"
            )
            
            print(f"📊 Found {len(links)} PDF links.")
            return links

        except Exception as e:
            print(f"❌ CRITICAL FAILURE: {e}")
            return []
        finally:
            browser.close()

if __name__ == "__main__":
    # Test with any link you want, for example:
    test_url = "https://www.lausd.org/Page/13501" 
    found_pdfs = robust_discovery(test_url)