from playwright.sync_api import sync_playwright
import pandas as pd

# We added a 'max_pages' variable! Set it to 3, 5, or whatever you want.
def hijack_shopee_pages(keyword, max_pages=3):
    print(f"🕵️‍♂️ Phase 2: Hijacking Target... {max_pages} Pages of '{keyword}'")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ Successfully hijacked the open browser!")
            
            context = browser.contexts[0]
            page = context.pages[0]
            product_list = []

            # 1. Our Network Detective
            def capture_api(response):
                if "search_items" in response.url or "/api/v4/search/search" in response.url:
                    try:
                        data = response.json()
                        items = data.get('items', [])
                        
                        if items:
                            print(f"🎯 Intercepted API data for {len(items)} items!")
                            
                        for item in items:
                            info = item.get('item_basic', item) 
                            title = info.get('name', 'No Title')
                            
                            raw_price = info.get('price', 0)
                            price = raw_price / 100000 if raw_price else 0
                            
                            # THE DATA SECRET: Stealing the exact, unrounded integers!
                            exact_lifetime_sold = info.get('historical_sold', 0)
                            exact_monthly_sold = info.get('sold', 0)
                            
                            product_list.append({
                                'Title': title,
                                'Price (PHP)': price,
                                'Exact Lifetime Sold': exact_lifetime_sold,
                                'Monthly Sold': exact_monthly_sold
                            })
                    except Exception as e:
                        pass

            page.on("response", capture_api)

            # 2. THE PAGINATION LOOP
            for current_page in range(max_pages):
                # Shopee counts starting at 0! Page 1 is &page=0. Page 2 is &page=1.
                search_url = f"https://shopee.ph/search?keyword={keyword.replace(' ', '%20')}&page={current_page}"
                
                try:
                    with page.expect_response(lambda r: "api/v4/search/search" in r.url, timeout=15000) as response_info:
                        page.goto(search_url)
            
                    # The moment that specific API call finishes, the script continues immediately
                    print(f"✅ Data received for page {current_page + 1}")
        
                    # Optional: A small scroll to trigger any lazy-loaded secondary APIs
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(1000) 

                except Exception as e:
                    print(f"⚠️ Page {current_page + 1} timed out or failed to load data.")

            # 3. Clean and Save Data
            if product_list:
                df = pd.DataFrame(product_list).drop_duplicates(subset=['Title']) 
                filename = f"shopee_{keyword.replace(' ', '_')}_{max_pages}_pages.csv"
                df.to_csv(filename, index=False)
                
                print(f"\n🏆 VICTORY! Scraped {len(df)} unique products across {max_pages} pages!")
                # Print a preview of our exact data!
                print(df[['Title', 'Price (PHP)', 'Exact Lifetime Sold']].head())
            else:
                print("\n❌ No products intercepted.")
                
        except Exception as e:
            print(f"❌ Failed to connect! Make sure your secret Chrome window is open.")
            print(f"Error: {e}")

if __name__ == "__main__":
    # You can change the '3' to '5' if you want 5 pages of data!
    search_item=input("Enter the product keyword to hijack (e.g., 'mechanical keyboard'): ")
    max_page=int(input("Enter the number of pages to hijack (e.g., 3): "))
    hijack_shopee_pages(search_item, max_pages=max_page)
    
