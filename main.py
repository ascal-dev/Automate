import asyncio
import re
import json
import nodriver as uc
from curl_cffi import requests

# 1. Configuration
WP_API_URL = "https://serialmaza.xyz/wp-json/wp/v2/posts"
OUTPUT_FILE = "result.json"

def get_extract_id():
    """Fetches the 32-character ID from the WordPress API."""
    print(f"[*] Fetching target ID from: {WP_API_URL}")
    try:
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

async def main():
    target_id = get_extract_id()
    if not target_id:
        print("[-] Error: No ID found. Exiting.")
        return

    print("[*] Launching browser with explicit uc.Config (Root Bypass)...")

    # --- THE CRITICAL FIX ---
    config = uc.Config()
    config.no_sandbox = True  # Solves the "Failed to connect/root" error
    config.headless = False   # False is better for Turnstile (xvfb handles the display)
    
    # Standard stability arguments
    config.add_argument("--disable-setuid-sandbox")
    config.add_argument("--disable-dev-shm-usage")
    config.add_argument("--disable-gpu")
    config.add_argument("--no-first-run")
    config.add_argument("--window-size=1920,1080")

    browser = await uc.start(config)

    try:
        url = f"https://multiup.io/en/mirror/{target_id}"
        print(f"[*] Navigating to: {url}")
        page = await browser.get(url)
        
        # Wait for the page and Turnstile widget to initialize
        await asyncio.sleep(10)

        # Handle the Turnstile checkbox
        try:
            # Look for the Cloudflare challenge iframe
            iframe = await page.select('iframe[src*="challenges.cloudflare.com"]', timeout=10)
            if iframe:
                print("[!] Turnstile detected. Clicking the checkbox area...")
                # Coordinate-based click often works better in headless-virtual environments
                rect = await iframe.get_position()
                await page.mouse.move(rect.x + 35, rect.y + 35)
                await page.mouse.click()
                await asyncio.sleep(5)
        except Exception:
            print("[*] No interactive challenge detected; checking for cookies.")

        print("[*] Monitoring for cf_clearance cookie...")
        cf_clearance = None
        user_agent = None

        for _ in range(20): # Check for 40 seconds total
            cookies = await browser.cookies.get_all()
            for c in cookies:
                if c.name == "cf_clearance":
                    cf_clearance = c.value
                    break
            if cf_clearance:
                user_agent = await page.evaluate("navigator.userAgent")
                break
            await asyncio.sleep(2)

        if cf_clearance:
            result = {
                "cf_clearance": cf_clearance,
                "user_agent": user_agent,
                "target_id": target_id
            }
            with open(OUTPUT_FILE, "w") as f:
                json.dump(result, f, indent=4)
            print(f"[SUCCESS] Key Captured: {cf_clearance[:20]}...")
        else:
            print("[-] FAILED: Cookie not found. Saving debug page.")
            html = await page.get_content()
            with open("debug_page.html", "w") as f:
                f.write(html)

    except Exception as e:
        print(f"[-] Browser Execution Error: {e}")
    finally:
        if browser:
            await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
