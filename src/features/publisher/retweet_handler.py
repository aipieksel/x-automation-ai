import logging
import time
import random
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from core.browser_manager import BrowserManager
from data_models import ScrapedTweet

logger = logging.getLogger(__name__)


def retweet_or_quote(
    browser_manager: BrowserManager,
    original_tweet: ScrapedTweet,
    final_quote_text: Optional[str],
) -> bool:
    driver = browser_manager.get_driver()
    if not original_tweet.tweet_url:
        logger.error(f"Cannot retweet tweet {original_tweet.tweet_id}: Missing tweet URL.")
        return False

    is_quote_tweet = bool(final_quote_text)
    action_type_log = "Quote Tweet" if is_quote_tweet else "Retweet"
    logger.info(f"Attempting {action_type_log} for tweet ID: {original_tweet.tweet_id}")
    if final_quote_text:
        logger.info(f"Quote text: '{final_quote_text[:50]}...'")

    try:
        browser_manager.navigate_to(str(original_tweet.tweet_url))
        time.sleep(random.uniform(2.5, 4.0))

        # Verify URL still contains the tweet ID (not redirected to error page)
        current_url = driver.current_url
        if original_tweet.tweet_id not in current_url:
            logger.error(f"URL mismatch: expected tweet {original_tweet.tweet_id} but current URL is {current_url}")
            return False

        # Find the main tweet element using multiple strategies
        main_tweet_element = None
        
        # Strategy 1: Article with status link containing tweet ID
        main_tweet_article_xpath = (
            f"//article[.//a[contains(@href, '/status/{original_tweet.tweet_id}')]]"
        )
        try:
            main_tweet_element = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, main_tweet_article_xpath))
            )
            logger.debug(f"Found tweet article with status link for {original_tweet.tweet_id}")
        except TimeoutException:
            logger.debug(f"Strategy 1 failed: Could not find article with status link")
        
        # Strategy 2: Article with data-testid='tweet'
        if not main_tweet_element:
            try:
                main_tweet_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
                )
                logger.debug("Found tweet article using data-testid='tweet'")
            except TimeoutException:
                logger.debug("Strategy 2 failed: Could not find article with data-testid='tweet'")
        
        # Strategy 3: Look for first article element on the page
        if not main_tweet_element:
            try:
                main_tweet_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//article"))
                )
                logger.debug("Found tweet using generic article selector")
            except TimeoutException:
                logger.debug("Strategy 3 failed: Could not find any article element")

        # Strategy 4: If no article found, try to find the retweet button directly on page
        # This handles cases where Twitter's structure has changed
        retweet_icon_button = None
        if not main_tweet_element:
            try:
                # Look for the retweet button directly
                retweet_icon_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='retweet']"))
                )
                logger.debug("Found retweet button directly without article container")
            except TimeoutException:
                pass
        
        # If we can't find either the article OR the retweet button, check for errors
        if not main_tweet_element and not retweet_icon_button:
            # Check for common error indicators
            error_indicators = [
                "//span[contains(text(), \"page doesn't exist\")]",
                "//span[contains(text(), 'Something went wrong')]", 
                "//span[contains(text(), \"doesn't exist\")]",
                "//div[contains(text(), \"Hmm...this page doesn't exist\")]",
            ]
            
            page_has_error = False
            for error_xpath in error_indicators:
                try:
                    error_elem = driver.find_element(By.XPATH, error_xpath)
                    if error_elem and error_elem.is_displayed():
                        logger.error(f"Tweet page shows error for {original_tweet.tweet_id}: Page doesn't exist.")
                        page_has_error = True
                        break
                except Exception:
                    pass
            
            if not page_has_error:
                logger.error(f"Could not find tweet article or retweet button for {original_tweet.tweet_id}. Tweet may not exist or page structure changed.")
            return False

        # If already reposted, the action button is 'unretweet'. Treat as success.
        search_context = main_tweet_element if main_tweet_element else driver
        try:
            already_reposted_btn = WebDriverWait(search_context, 3).until(
                EC.presence_of_element_located((By.XPATH, ".//button[@data-testid='unretweet']" if main_tweet_element else "//button[@data-testid='unretweet']"))
            )
            if already_reposted_btn:
                logger.info(f"Tweet {original_tweet.tweet_id} already reposted. Skipping confirm.")
                return True
        except TimeoutException:
            pass

        # Find the retweet button if not already found
        if not retweet_icon_button:
            try:
                retweet_icon_button = WebDriverWait(search_context, 8).until(
                    EC.element_to_be_clickable((By.XPATH, ".//button[@data-testid='retweet']" if main_tweet_element else "//button[@data-testid='retweet']"))
                )
            except TimeoutException:
                # As a fallback, the button might be present but not immediately clickable; try presence then JS click
                retweet_icon_button = WebDriverWait(search_context, 8).until(
                    EC.presence_of_element_located((By.XPATH, ".//button[@data-testid='retweet']" if main_tweet_element else "//button[@data-testid='retweet']"))
                )
        
        try:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", retweet_icon_button)
            except Exception:
                pass
            retweet_icon_button.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", retweet_icon_button)
            except Exception:
                pass
        logger.info(f"Clicked retweet icon for tweet {original_tweet.tweet_id}.")
        time.sleep(0.8)

        if is_quote_tweet:
            # Wait for the dropdown menu to appear
            try:
                menu = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='menu']"))
                )
                logger.info("Found dropdown menu for quote selection")
            except TimeoutException:
                logger.error("Dropdown menu did not appear after clicking retweet button")
                raise
            
            # Try multiple selectors for the Quote option based on Twitter's HTML structure
            quote_option = None
            quote_selectors = [
                # Strategy 1: Link element with href containing /compose/post (from user's HTML)
                ".//a[contains(@href, '/compose/post')]",
                # Strategy 2: Menu item containing "Quote" text
                ".//a[@role='menuitem'][contains(., 'Quote')]",
                # Strategy 3: Div menuitem with Quote text
                ".//div[@role='menuitem'][contains(., 'Quote')]",
                # Strategy 4: Any link in dropdown going to compose
                ".//a[contains(@href, '/compose')]",
                # Strategy 5: Second menu item (Quote is usually second after Repost)
                ".//a[@role='menuitem']",
            ]
            
            for xpath in quote_selectors:
                try:
                    quote_option = WebDriverWait(menu, 2).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    if quote_option:
                        logger.info(f"Found Quote option using: {xpath}")
                        break
                except TimeoutException:
                    logger.debug(f"Quote selector failed: {xpath}")
                    continue
            
            if not quote_option:
                # Debug: Print dropdown HTML
                try:
                    menu_html = menu.get_attribute('outerHTML')[:500]
                    logger.error(f"Dropdown HTML (first 500 chars): {menu_html}")
                except:
                    pass
                raise TimeoutException("Could not find Quote option in dropdown menu")
            
            quote_option.click()
            logger.info("Clicked 'Quote' option.")
            time.sleep(2.5)

            quote_text_area_xpath = "//div[@data-testid='tweetTextarea_0' and @role='textbox']"
            quote_text_area = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, quote_text_area_xpath))
            )
            
            # Click the text area to focus it
            try:
                quote_text_area.click()
                time.sleep(0.3)
            except Exception:
                pass
            
            # Enforce platform cap for quote text as safety and remove non-BMP characters (emojis)
            safe_quote = (final_quote_text or "")[:270]
            # Remove characters outside BMP (emojis like 🔥) that ChromeDriver can't handle
            safe_quote = ''.join(c for c in safe_quote if ord(c) < 0x10000)
            
            # Use JavaScript to set the text content (more reliable than send_keys)
            try:
                driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].textContent = arguments[1];
                    arguments[0].dispatchEvent(new InputEvent('input', { bubbles: true }));
                """, quote_text_area, safe_quote)
                logger.info("Typed quote text via JavaScript.")
            except Exception as js_err:
                logger.warning(f"JS input failed, trying send_keys: {js_err}")
                # Fallback to send_keys (may fail with emojis)
                try:
                    quote_text_area.send_keys(safe_quote)
                    logger.info("Typed quote text via send_keys.")
                except Exception as sk_err:
                    logger.error(f"Failed to type quote text: {sk_err}")
                    raise
            
            time.sleep(0.5)

            post_button = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='tweetButton']"))
            )
            post_button.click()
            logger.info("Clicked 'Post' for quote tweet.")
        else:
            # Wait for the dropdown menu to appear after clicking retweet button
            confirm_retweet_button = None
            last_error = None
            
            # Give the dropdown time to render
            time.sleep(0.8)
            
            for attempt in range(3):
                try:
                    # First, wait for the menu container to appear
                    menu = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@role='menu']"))
                    )
                    logger.debug(f"Found dropdown menu (attempt {attempt + 1})")
                    
                    # Try multiple selector strategies for the repost/retweet confirm button
                    selectors = [
                        # Strategy 1: Direct data-testid
                        (By.XPATH, ".//div[@data-testid='retweetConfirm']"),
                        # Strategy 2: Menu item with "Repost" text
                        (By.XPATH, ".//div[@role='menuitem'][contains(., 'Repost')]"),
                        # Strategy 3: Menu item with "Retweet" text  
                        (By.XPATH, ".//div[@role='menuitem'][contains(., 'Retweet')]"),
                        # Strategy 4: Any menu item (first one is usually repost)
                        (By.XPATH, ".//div[@role='menuitem'][1]"),
                    ]
                    
                    for by, xpath in selectors:
                        try:
                            confirm_retweet_button = WebDriverWait(menu, 2).until(
                                EC.element_to_be_clickable((by, xpath))
                            )
                            if confirm_retweet_button:
                                logger.debug(f"Found confirm button using: {xpath}")
                                break
                        except TimeoutException:
                            continue
                    
                    if confirm_retweet_button:
                        break
                        
                except TimeoutException as e:
                    last_error = e
                    logger.warning(f"Menu not found on attempt {attempt + 1}, retrying...")
                    
                    # Retry clicking the retweet button
                    if attempt < 2:
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", retweet_icon_button)
                            time.sleep(0.3)
                            driver.execute_script("arguments[0].click();", retweet_icon_button)
                            time.sleep(0.8)
                        except Exception as retry_error:
                            logger.warning(f"Failed to retry click: {retry_error}")

            if not confirm_retweet_button:
                # Before failing, check if the tweet now shows unretweet (might have auto-confirmed)
                try:
                    WebDriverWait(main_tweet_element, 3).until(
                        EC.presence_of_element_located((By.XPATH, ".//button[@data-testid='unretweet']"))
                    )
                    logger.info(f"Repost appears active for tweet {original_tweet.tweet_id} (unretweet visible).")
                    return True
                except TimeoutException:
                    raise TimeoutException(f"Retweet confirm button not found after 3 attempts. Last error: {last_error}")

            # Click the confirm button
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_retweet_button)
            except Exception:
                pass
            
            try:
                confirm_retweet_button.click()
                logger.info("Clicked 'Repost' (confirm retweet) option via regular click.")
            except Exception as click_error:
                logger.warning(f"Regular click failed, trying JS click: {click_error}")
                driver.execute_script("arguments[0].click();", confirm_retweet_button)
                logger.info("Clicked 'Repost' (confirm retweet) option via JS click.")

        # Light backoff after action to avoid rapid-fire sequences
        time.sleep(random.uniform(2.0, 4.5))
        logger.info(f"{action_type_log} for tweet {original_tweet.tweet_id} successful.")
        return True
    except TimeoutException as e:
        logger.error(f"Timeout during {action_type_log.lower()} for tweet {original_tweet.tweet_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to {action_type_log.lower()} tweet {original_tweet.tweet_id}: {e}", exc_info=True)
        return False
