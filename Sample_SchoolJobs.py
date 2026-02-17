from playwright.sync_api import sync_playwright
import requests
import pandas as pd

def harvest_cookies():
    print("🤖 Playwright: Opening browser to solve the firewall...")
    with sync_playwright() as p:
        # We can even run it "headless" (invisible) now!
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Go to the site just to get past the Incapsula firewall
        page.goto("https://tcisd.tedk12.com/hire/index.aspx")
        page.wait_for_timeout(5000) # Give it 5 seconds to pass the security check

        # 🍪 STEAL THE COOKIES!
        raw_cookies = context.cookies()
        browser.close()
        print("✅ Playwright: Cookies stolen! Closing browser.")

        # Reformat the cookies into a dictionary that 'requests' can understand
        cookie_dict = {}
        for cookie in raw_cookies:
            cookie_dict[cookie['name']] = cookie['value']
            
        return cookie_dict

def fast_api_scrape(cookies):
    print("⚡ Requests: Using stolen cookies to download all data instantly...")
    
    # Notice we can use our size=1000 cheat code again!
    api_url = "https://api.schoolspring.com/api/Jobs/GetPagedJobsWithSearch?domainName=&keyword=&location=&category=&gradelevel=&jobtype=&organization=&swLat=&swLon=&neLat=&neLon=&page=1&size=1000&sortDateAscending=false"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "origin": "https://tcisd.schoolspring.com",
        "referer": "https://tcisd.schoolspring.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }

    # Pass the cookies we stole from Playwright directly into the fast requests library!
    response = requests.get(api_url, headers=headers, cookies=cookies)
    data = response.json()

    # Extract the jobs
    actual_jobs_list = data.get('value', {}).get('jobsList', [])
    
    if actual_jobs_list:
        df = pd.DataFrame(actual_jobs_list)
        df.to_csv('ultimate_hybrid_jobs.csv', index=False)
        print(f"\n🏆 SUCCESS! Instant downloaded {len(df)} jobs using the Hybrid Method.")
    else:
        print("Failed to get data. The firewall might need more time to load.")

if __name__ == "__main__":
    # Step 1: Let the heavy robot steal the keys
    stolen_keys = harvest_cookies()
    
    # Step 2: Let the fast robot grab the data
    fast_api_scrape(stolen_keys)