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
                
                print(f"\n🌐 Forcing browser to Page {current_page + 1}: {search_url}")
                page.goto(search_url)

                print("⏳ Waiting 8 seconds for API data...")
                page.wait_for_timeout(8000)
                
                # Scroll down in stages to make sure the page loads everything
                for _ in range(3):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(2000)

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
    hijack_shopee_pages("mechanical keyboard", max_pages=3)