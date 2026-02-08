import asyncio
import re
import json
import os
import nodriver as uc
from curl_cffi import requests

# 1. Configuration
WP_API_URL = "https://serialmaza.xyz/wp-json/wp/v2/posts"
OUTPUT_FILE = "result.json"

def get_extract_id():
    """
    Fetches the latest posts from the WordPress API and extracts the MultiUp ID.
    """
    print(f"[*] Fetching ID from: {WP_API_URL}")
    try:
        # Use curl_cffi to mimic a real browser for the API request
        response = requests.get(WP_API_URL, impersonate="chrome124", timeout=10)
        response.raise_for_status()
        
        posts = response.json()
        for post in posts:
            content = post.get('content', {}).get('rendered', '')
            # Regex to find the ID pattern: id=2ea1ff...
            match = re.search(r'id=([a-f0-9]{32})', content)
            if match:
                found_id = match.group(1)
                print(f"[+] Found Target ID: {found_id}")
                return found_id
                
    except Exception as e:
        print(f"[-] Error fetching API: {e}")
    
    print("[-] No valid ID found in the latest posts.")
    return None

async def extract_cf_clearance(target_id):
    """
    Uses nodriver to solve the Cloudflare challenge and extract cookies.
    """
    target_url = f"https://multiup.io/en/mirror/{target_id}"
    print(f"[*] Navigating to: {target_url}")

    browser = None
    try:
        # --- CRITICAL FIX FOR GITHUB ACTIONS ---
        # We must disable the sandbox and GPU to run in the CI environment
        browser = await uc.start(
            headless=True,
            sandbox=False, # Essential for root/CI execution
            browser_args=[
                "--no-sandbox",
                "--disable-dev-shm-usage", # Fixes shared memory issues
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--window-size=1920,1080"
            ]
        )
        print("[+] Browser started successfully.")

        # Visit the page
        page = await browser.get(target_url)

        # Wait for Cloudflare challenge to resolve
        # We check periodically instead of just sleeping
        print("[*] Waiting for Cloudflare challenge to clear...")
        
        cf_clearance = None
        user_agent = None

        # Retry loop: check for cookies every 2 seconds, up to 30 seconds
        for i in range(15):
            await asyncio.sleep(2)
            cookies = await browser.cookies.get_all()
            
            # Look for the specific cookie
            for cookie in cookies:
                if cookie.name == "cf_clearance":
                    cf_clearance = cookie.value
                    break
            
            if cf_clearance:
                print(f"[+] Cookie found after {i*2} seconds!")
                break
        
        if not cf_clearance:
            print("[-] Timeout: cf_clearance cookie not found.")
            # Optional: Print page source or title for debugging
            title = await page.evaluate("document.title")
            print(f"[-] Current Page Title: {title}")
        else:
            # Grab the User-Agent (Must match the cookie)
            user_agent = await page.evaluate("navigator.userAgent")
            
            # Save results
            result = {
                "id": target_id,
                "cf_clearance": cf_clearance,
                "user_agent": user_agent
            }
            
            with open(OUTPUT_FILE, "w") as f:
                json.dump(result, f, indent=4)
            
            print(f"[+] SUCCESS. Data saved to {OUTPUT_FILE}")
            print(f"    Key: {cf_clearance[:15]}...")

    except Exception as e:
        print(f"[-] Browser Error: {e}")
    
    finally:
        if browser:
            try:
                await browser.stop()
            except:
                pass

if __name__ == "__main__":
    # Main execution flow
    target_id = get_extract_id()
    
    if target_id:
        asyncio.run(extract_cf_clearance(target_id))
    else:
        # Create an empty or error JSON so the workflow doesn't fail on upload
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"error": "No ID found"}, f)
        exit(1) # Exit with error code to notify GitHub Actions
