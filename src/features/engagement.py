import os
import logging
import sys
import time
from typing import Optional
from selenium.webdriver.remote.webelement import WebElement # Import WebElement

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Adjust import paths
try:
    from ..core.browser_manager import BrowserManager
    from ..core.config_loader import ConfigLoader
    from ..utils.logger import setup_logger
    from ..data_models import ScrapedTweet, AccountConfig
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..')) # Add root src to path
    from src.core.browser_manager import BrowserManager
    from src.core.config_loader import ConfigLoader
    from src.utils.logger import setup_logger
    from src.data_models import ScrapedTweet, AccountConfig

config_loader_instance = ConfigLoader()
setup_logger(config_loader_instance)
logger = logging.getLogger(__name__)

class TweetEngagement:
    def __init__(self, browser_manager: BrowserManager, account_config: AccountConfig):
        self.browser_manager = browser_manager
        self.driver = self.browser_manager.get_driver()
        self.account_config = account_config
        self.config_loader = browser_manager.config_loader

    def _find_tweet_on_page(self, tweet_id: str) -> Optional[WebElement]:
        """
        Attempts to find a tweet article element by its ID within its URL.
        This is a helper and might need to be more robust if tweets are not directly addressable
        or if the current page doesn't show the tweet directly.
        """
        try:
            # Construct an XPath to find an article that contains a link with the tweet ID.
            # This assumes the tweet is visible on the current page.
            xpath_selector = f"//article[.//a[contains(@href, '/status/{tweet_id}')]]"
            tweet_element = self.driver.find_element(By.XPATH, xpath_selector)
            logger.info(f"Found tweet element for ID {tweet_id} on page.")
            return tweet_element
        except NoSuchElementException:
            logger.warning(f"Tweet element with ID {tweet_id} not found on the current page.")
            return None

    async def like_tweet(self, tweet_id: str, tweet_url: Optional[str] = None) -> bool:
        """
        Likes a tweet given its ID. Navigates to the tweet URL if provided and necessary.
        Updated Jan 6, 2026: Improved selectors and fallback strategies.
        """
        logger.info(f"Attempting to like tweet ID: {tweet_id}")
        
        original_url = None
        tweet_card_element = None

        try:
            # If a tweet URL is provided, navigate to it first.
            if tweet_url:
                original_url = self.driver.current_url
                # Convert HttpUrl to string if necessary
                url_str = str(tweet_url) if hasattr(tweet_url, '__str__') else tweet_url
                if tweet_id not in original_url:
                    logger.info(f"Navigating to tweet URL: {url_str}")
                    self.browser_manager.navigate_to(url_str)
                    time.sleep(3)
            
            # Check if page exists
            page_source = self.driver.page_source.lower()
            if "this page doesn't exist" in page_source or "this account doesn't exist" in page_source:
                logger.error(f"Tweet {tweet_id} doesn't exist!")
                return False
            
            # Try multiple strategies to find the tweet article
            strategies = [
                f"//article[@data-testid='tweet'][.//a[contains(@href, '/status/{tweet_id}')]]",
                f"//article[.//a[contains(@href, '/status/{tweet_id}')]]",
                "//article[@data-testid='tweet']",
            ]
            
            for xpath in strategies:
                try:
                    tweet_card_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    logger.info(f"Found tweet article using: {xpath}")
                    break
                except:
                    continue
            
            if not tweet_card_element:
                logger.error(f"Cannot like tweet {tweet_id}: Tweet article not found on page.")
                return False

            # Find the like button - try multiple selectors
            like_button = None
            like_selectors = [
                './/button[@data-testid="like"]',
                './/div[@data-testid="like"]//button',
                './/button[contains(@aria-label, "Like")]',
            ]
            
            for selector in like_selectors:
                try:
                    like_button = tweet_card_element.find_element(By.XPATH, selector)
                    logger.info(f"Found like button using: {selector}")
                    break
                except:
                    continue
            
            if not like_button:
                # Try page-wide search as fallback
                try:
                    like_button = self.driver.find_element(By.XPATH, '//button[@data-testid="like"]')
                    logger.info("Found like button using page-wide search")
                except:
                    logger.error(f"Cannot like tweet {tweet_id}: Like button not found.")
                    return False

            # Check if already liked
            aria_label = like_button.get_attribute("aria-label") or ""
            data_testid = like_button.get_attribute("data-testid") or ""
            
            if "unlike" in aria_label.lower() or data_testid == "unlike":
                logger.info(f"Tweet {tweet_id} is already liked.")
                return True

            # Scroll button into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_button)
            time.sleep(0.5)

            # Click the like button
            try:
                like_button.click()
                logger.info(f"Clicked like button for tweet {tweet_id}.")
            except ElementClickInterceptedException:
                logger.warning("Click intercepted, trying JavaScript click")
                self.driver.execute_script("arguments[0].click();", like_button)
                logger.info("Clicked like button via JavaScript.")
            
            time.sleep(1.5)

            # Verify if liked - check for unlike button
            try:
                unlike_button = tweet_card_element.find_element(By.XPATH, './/button[@data-testid="unlike"]')
                logger.info(f"Successfully liked tweet {tweet_id} (found unlike button).")
                return True
            except:
                pass
            
            # Alternative verification via aria-label
            try:
                updated_button = tweet_card_element.find_element(
                    By.XPATH, './/button[@data-testid="like" or @data-testid="unlike"]'
                )
                new_label = updated_button.get_attribute("aria-label") or ""
                new_testid = updated_button.get_attribute("data-testid") or ""
                if "unlike" in new_label.lower() or new_testid == "unlike":
                    logger.info(f"Successfully liked tweet {tweet_id}.")
                    return True
            except:
                pass
            
            logger.warning(f"Could not verify like for tweet {tweet_id}, but click was attempted.")
            return False

        except TimeoutException:
            logger.error(f"Timeout while trying to like tweet {tweet_id}.")
            return False
        except ElementClickInterceptedException:
            logger.error(f"Like button click intercepted for tweet {tweet_id}. Possible overlay or popup.")
            return False
        except Exception as e:
            logger.error(f"Failed to like tweet {tweet_id}: {e}", exc_info=True)
            return False

# Example usage and test function remains largely the same but will now use the implemented like_tweet.
# The placeholder warning in the test function about replacing tweet_id/url is still relevant for actual testing.

if __name__ == '__main__':
    import asyncio
    
    async def test_engagement():
        cfg_loader = ConfigLoader()
        accounts_data = cfg_loader.get_accounts_config()
        
        if not accounts_data:
            logger.error("No accounts configured in config/accounts.json. Cannot run engagement test.")
            return

        active_account_dict = next((acc for acc in accounts_data if acc.get("is_active", True)), None)
        if not active_account_dict:
            logger.error("No active accounts found in config/accounts.json.")
            return
            
        try:
            # Use Pydantic's model_validate for robust parsing
            account = AccountConfig.model_validate(active_account_dict)
        except Exception as e:
            logger.error(f"Error creating AccountConfig model from dict for {active_account_dict.get('account_id')}: {e}")
            return

        bm = BrowserManager(account_config=active_account_dict) 
        engagement = TweetEngagement(browser_manager=bm, account_config=account)

        # --- IMPORTANT: Replace with a REAL, ACCESSIBLE tweet_id and tweet_url for testing ---
        # This tweet should ideally NOT be liked by the test account initially.
        test_tweet_id = "1795000000000000000"  # Replace with a real tweet ID from X.com
        test_tweet_user = "x" # Replace with the user handle of the tweet poster
        test_tweet_url = f"https://x.com/{test_tweet_user}/status/{test_tweet_id}" 
        # --- End of placeholder section ---

        if "1795000000000000000" == test_tweet_id or "someuser" == test_tweet_user or "x" == test_tweet_user :
            logger.warning("Placeholder tweet_id/URL/user detected in engagement test. Test will likely fail or target a non-existent tweet.")
            logger.warning("Please update test_tweet_id, test_tweet_user, and test_tweet_url in src/features/engagement.py with real, accessible values.")
            bm.close_driver()
            return

        try:
            logger.info(f"Testing engagement for account: {account.account_id}")
            logger.info(f"Attempting to like tweet: {test_tweet_url}")

            success = await engagement.like_tweet(tweet_id=test_tweet_id, tweet_url=test_tweet_url)
            logger.info(f"Like tweet operation result: {success}")

            if success:
                logger.info("Waiting a few seconds to observe the 'liked' state if checking manually...")
                time.sleep(5)
                # Optionally, you could try to unlike it here if an unlike method existed.
                # For now, just confirms the like action was attempted.
            
        except Exception as e:
            logger.error(f"Error during engagement test: {e}", exc_info=True)
        finally:
            logger.info("Closing browser manager after engagement test...")
            engagement.browser_manager.close_driver()
            logger.info("Engagement test finished.")

    # To run this test:
    # 1. Ensure config/accounts.json has at least one active account with valid cookies.
    # 2. Replace the placeholder test_tweet_id, test_tweet_user, and test_tweet_url above with actual values.
    # 3. Uncomment the line below:
    # asyncio.run(test_engagement())
    if __name__ == '__main__':
         logger.info("To run the engagement test, uncomment 'asyncio.run(test_engagement())' at the end of the script and ensure placeholder tweet IDs/URLs are replaced with actual, accessible ones.")
