"""
Playwright test script to analyze Twitter/X retweet button HTML structure
and test the retweet interaction flow.

Run this script with:
    python test_retweet_interaction.py
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


async def test_retweet_button():
    """Test and analyze the retweet button interaction."""
    
    # Load cookies from data/cookies/local.json
    cookies_path = "data/cookies/local.json"
    if not os.path.exists(cookies_path):
        print(f"❌ Cookies file not found: {cookies_path}")
        return
    
    with open(cookies_path, 'r') as f:
        cookies = json.load(f)
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )
        
        # Add cookies
        await context.add_cookies(cookies)
        
        # Create page
        page = await context.new_page()
        
        try:
            # Navigate to Twitter home
            print("🔄 Navigating to Twitter/X...")
            await page.goto('https://x.com/home', wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # Wait for timeline to load
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            print("✅ Timeline loaded")
            
            # Find the first tweet
            first_tweet = await page.query_selector('article[data-testid="tweet"]')
            
            if not first_tweet:
                print("❌ No tweets found")
                return
            
            # Locate retweet button using data-testid
            retweet_button = await first_tweet.query_selector('button[data-testid="retweet"]')
            
            if not retweet_button:
                print("❌ Retweet button not found")
                return
            
            print("\n📋 RETWEET BUTTON HTML STRUCTURE:")
            print("=" * 60)
            button_html = await retweet_button.evaluate('el => el.outerHTML')
            print(button_html)
            print("=" * 60)
            
            # Get button attributes
            aria_label = await retweet_button.get_attribute('aria-label')
            aria_expanded = await retweet_button.get_attribute('aria-expanded')
            print(f"\n🔍 Button Attributes:")
            print(f"   aria-label: {aria_label}")
            print(f"   aria-expanded: {aria_expanded}")
            
            # Scroll button into view
            await retweet_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # Click the retweet button
            print("\n🖱️  Clicking retweet button...")
            await retweet_button.click()
            await asyncio.sleep(1)
            
            # Wait for dropdown menu to appear
            try:
                menu = await page.wait_for_selector('div[role="menu"]', timeout=3000)
                print("✅ Dropdown menu appeared")
                
                # Get menu HTML
                menu_html = await menu.evaluate('el => el.outerHTML')
                print("\n📋 DROPDOWN MENU HTML STRUCTURE:")
                print("=" * 60)
                print(menu_html[:2000])  # Print first 2000 chars
                if len(menu_html) > 2000:
                    print(f"... (truncated, total length: {len(menu_html)} chars)")
                print("=" * 60)
                
                # Find all menu items
                menu_items = await menu.query_selector_all('div[role="menuitem"]')
                print(f"\n📝 Found {len(menu_items)} menu items:")
                
                for i, item in enumerate(menu_items, 1):
                    item_text = await item.inner_text()
                    item_testid = await item.get_attribute('data-testid')
                    print(f"   {i}. Text: '{item_text.strip()}' | data-testid: {item_testid}")
                
                # Look for retweetConfirm button
                confirm_button = await page.query_selector('[data-testid="retweetConfirm"]')
                if confirm_button:
                    print("\n✅ Found retweetConfirm button")
                    confirm_html = await confirm_button.evaluate('el => el.outerHTML')
                    print("\n📋 RETWEET CONFIRM BUTTON:")
                    print("=" * 60)
                    print(confirm_html)
                    print("=" * 60)
                else:
                    print("\n⚠️  retweetConfirm button not found, checking alternatives...")
                    
                    # Try finding by text
                    repost_option = await page.query_selector('div[role="menuitem"]:has-text("Repost")')
                    if repost_option:
                        print("✅ Found 'Repost' menu item by text")
                        repost_html = await repost_option.evaluate('el => el.outerHTML')
                        print("\n📋 REPOST MENU ITEM:")
                        print("=" * 60)
                        print(repost_html)
                        print("=" * 60)
                
                # Close menu by clicking outside or pressing Escape
                await page.keyboard.press('Escape')
                print("\n✅ Test completed successfully")
                
            except PlaywrightTimeoutError:
                print("❌ Dropdown menu did not appear")
                
                # Check if button state changed (might already be retweeted)
                updated_button = await first_tweet.query_selector('button[data-testid="unretweet"]')
                if updated_button:
                    print("ℹ️  Tweet might already be retweeted (unretweet button found)")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Keep browser open for manual inspection
            print("\n⏸️  Browser will remain open for 30 seconds for manual inspection...")
            await asyncio.sleep(30)
            await browser.close()


if __name__ == "__main__":
    print("🚀 Starting Twitter/X Retweet Button Analysis")
    print("=" * 60)
    asyncio.run(test_retweet_button())
