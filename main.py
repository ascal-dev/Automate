import asyncio
import re
import json
import os
import nodriver as uc
from curl_cffi import requests

# Configuration
WP_API_URL = "https://serialmaza.xyz/wp-json/wp/v2/posts"
OUTPUT_FILE = "result.json"

def get_extract_id():
    """Extracts the 32-char ID from the WordPress API."""
    print(f"[*] Fetching target ID from: {WP_API_URL}")
    try:
        # Use impersonate to bypass potential WAF on the API itself
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
    """Detects and clicks the Turnstile checkbox."""
    print("[*] Looking for Turnstile challenge...")
    try:
        # Wait for the Cloudflare iframe
        iframe = await page.select('iframe[src*="challenges.cloudflare.com"]', timeout=15)
        if iframe:
            print("[!] Turnstile detected. Performing human-like click...")
            # Get coordinates of the iframe to click the checkbox area
            rect = await iframe.get_position()
            # The checkbox is usually in the top-left quadrant of the widget
            await page.mouse.move(rect.x + 45, rect.y + 45)
            await asyncio.sleep(0.5)
            await page.mouse.click()
            print("[+] Clicked. Waiting for verification...")
            return True
    except Exception:
        print("[*] No interactive challenge found; might have auto-solved.")
    return False

async def main():
    target_id = get_extract_id()
    if not target_id:
        return

    print("[*] Launching browser with Root-Bypass settings...")
    
    # THE 100% WORKING CONFIG:
    # We use headless=False + no_sandbox=True to satisfy the root user requirement.
    # xvfb-run (in the YAML) will handle the display.
    browser = await uc.start(
        headless=False, 
        no_sandbox=True,
        browser_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--remote-debugging-port=9222",
            "--disable-gpu",
            "--no-first-run"
        ]
    )

    try:
        url = f"https://multiup.io/en/mirror/{target_id}"
        page = await browser.get(url)
        
        # 1. Wait for Turnstile to appear and solve it
        await asyncio.sleep(7) 
        await solve_turnstile(page)

        # 2. Extract Cookie
        print("[*] Monitoring cookies for cf_clearance...")
        cf_clearance = None
        user_agent = None

        for _ in range(20): # Try for 40 seconds
            cookies = await browser.cookies.get_all()
            for c in cookies:
                if c.name == "cf_clearance":
                    cf_clearance = c.value
                    break
            if cf_clearance:
                user_agent = await page.evaluate("navigator.userAgent")
                break
            await asyncio.sleep(2)

        # 3. Save Result
        if cf_clearance:
            res = {"cf_clearance": cf_clearance, "user_agent": user_agent, "id": target_id}
            with open(OUTPUT_FILE, "w") as f:
                json.dump(res, f, indent=4)
            print(f"[SUCCESS] Key Captured: {cf_clearance[:20]}...")
        else:
            print("[-] Failed to capture cookie. Saving debug HTML.")
            html = await page.get_content()
            with open("debug.html", "w") as f:
                f.write(html)

    finally:
        await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
