import asyncio
import re
import json
import nodriver as uc
from curl_cffi import requests

# Configuration
WP_API_URL = "https://serialmaza.xyz/wp-json/wp/v2/posts"
OUTPUT_FILE = "result.json"

def get_extract_id():
    """Fetches the 32-character ID from the WordPress API."""
    print(f"[*] Fetching target ID from: {WP_API_URL}")
    try:
        # Using curl_cffi for the API call to avoid early blocks
        response = requests.get(WP_API_URL, impersonate="chrome124", timeout=15)
        response.raise_for_status()
        posts = response.json()
        for post in posts:
            content = post.get('content', {}).get('rendered', '')
            match = re.search(r'id=([a-f0-9]{32})', content)
            if match:
                print(f"[+] Found Target ID: {match.group(1)}")
                return match.group(1)
    except Exception as e:
        print(f"[-] API Error: {e}")
    return None

async def solve_turnstile(page):
    """Attempts to find and click the 'Verify you are human' checkbox."""
    print("[*] Searching for Turnstile widget...")
    try:
        # 1. Wait for the iframe that hosts the challenge
        # Cloudflare usually uses an iframe with 'challenges' in the source
        iframe = await page.select('iframe[src*="challenges.cloudflare.com"]', timeout=10)
        
        if iframe:
            print("[+] Found Turnstile iframe. Calculating click coordinates...")
            # We click the top-left area of the widget where the checkbox sits
            # Offset (30, 30) is typically where the box is located inside the frame
            rect = await iframe.get_position()
            click_x = rect.x + 30
            click_y = rect.y + 30
            
            # Simulate human-like mouse movement
            await page.mouse.move(click_x, click_y)
            await asyncio.sleep(0.5)
            await page.mouse.click()
            print("[!] Clicked checkbox. Waiting for verification...")
            return True
    except Exception as e:
        print(f"[*] Widget not found or already solved: {e}")
    return False

async def main():
    # 1. Get the ID
    target_id = get_extract_id()
    if not target_id:
        print("[-] Error: Could not find target ID from API.")
        return

    # 2. Launch Browser with Root-fix arguments
    print("[*] Launching browser...")
    browser = await uc.start(
        headless=True,
        browser_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1920,1080"
        ]
    )

    try:
        page = await browser.get(f"https://multiup.io/en/mirror/{target_id}")
        
        # Give the page a moment to load the Cloudflare challenge
        await asyncio.sleep(5)
        
        # 3. Interactive Challenge Solving
        await solve_turnstile(page)

        # 4. Extract Cookie and User-Agent
        print("[*] Waiting for cf_clearance cookie (max 30s)...")
        cf_clearance = None
        user_agent = None

        for _ in range(15):  # Loop 15 times (30 seconds total)
            cookies = await browser.cookies.get_all()
            for cookie in cookies:
                if cookie.name == "cf_clearance":
                    cf_clearance = cookie.value
                    break
            
            if cf_clearance:
                user_agent = await page.evaluate("navigator.userAgent")
                break
            await asyncio.sleep(2)

        # 5. Save Results
        if cf_clearance:
            data = {
                "cf_clearance": cf_clearance,
                "user_agent": user_agent,
                "target_id": target_id
            }
            with open(OUTPUT_FILE, "w") as f:
                json.dump(data, f, indent=4)
            print(f"[SUCCESS] Cookie captured: {cf_clearance[:15]}...")
        else:
            print("[-] FAILED: Cookie not generated. Check debug_page.html")
            content = await page.get_content()
            with open("debug_page.html", "w") as f:
                f.write(content)

    finally:
        await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
