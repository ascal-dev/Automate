import asyncio
import re
import json
import nodriver as uc
from curl_cffi import requests

def get_extract_id():
    print("Fetching ID from WordPress API...")
    url = "https://serialmaza.xyz/wp-json/wp/v2/posts"
    try:
        response = requests.get(url, impersonate="chrome124")
        posts = response.json()
        for post in posts:
            content = post['content']['rendered']
            match = re.search(r'id=([a-f0-9]{32})', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error fetching API: {e}")
    return None

async def extract_cf_clearance(target_id):
    target_url = f"https://multiup.io/en/mirror/{target_id}"
    print(f"Targeting: {target_url}")

    # Launch browser
    browser = await uc.start(headless=True) # Change to False if debugging locally
    page = await browser.get(target_url)

    print("Waiting for Cloudflare Challenge (15s)...")
    await asyncio.sleep(15) 

    cookies = await browser.cookies.get_all()
    ua = await page.evaluate("navigator.userAgent")
    
    cf_clearance = next((c.value for c in cookies if c.name == 'cf_clearance'), None)
    
    if cf_clearance:
        result = {"cf_clearance": cf_clearance, "user_agent": ua, "id": target_id}
        print(f"Successfully extracted: {cf_clearance[:15]}...")
        with open("result.json", "w") as f:
            json.dump(result, f)
    else:
        print("Failed to capture cf_clearance.")

    await browser.stop()

if __name__ == "__main__":
    ext_id = get_extract_id()
    if ext_id:
        asyncio.run(extract_cf_clearance(ext_id))
    else:
        print("No ID found in WordPress feed.")
