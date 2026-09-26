"""
Test script to verify like functionality works correctly.

Usage:
    python test_like_fix.py [tweet_url]
    python test_like_fix.py --search "keyword"

Example:
    python test_like_fix.py https://x.com/username/status/1234567890
    python test_like_fix.py --search "React templates"
"""
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.browser_manager import BrowserManager
from core.config_loader import ConfigLoader
from data_models import ScrapedTweet

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def search_and_get_tweet(browser_manager: BrowserManager, keyword: str) -> ScrapedTweet:
    """Search for a keyword and return the first tweet found."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    driver = browser_manager.get_driver()
    
    # Navigate to Twitter search
    search_url = f"https://x.com/search?q={keyword.replace(' ', '%20')}&src=typed_query&f=live"
    logger.info(f"Searching for: {keyword}")
    browser_manager.navigate_to(search_url)
    time.sleep(3)
    
    # Wait for tweets to load and find the first one
    try:
        # Find first article with a status link
        article = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
        )
        
        # Get the tweet link from the article
        status_link = article.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
        tweet_url = status_link.get_attribute("href")
        
        # Extract tweet ID
        tweet_id = tweet_url.split("/status/")[-1].split("?")[0].split("/")[0]
        
        # Get user handle
        try:
            handle_elem = article.find_element(By.XPATH, ".//span[contains(text(), '@')]")
            user_handle = handle_elem.text
        except:
            user_handle = "unknown"
        
        # Get tweet text
        try:
            text_elem = article.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
            text_content = text_elem.text[:100]
        except:
            text_content = ""
        
        logger.info(f"Found tweet: {tweet_url}")
        logger.info(f"  User: {user_handle}")
        logger.info(f"  Text: {text_content}...")
        
        return ScrapedTweet(
            tweet_id=tweet_id,
            tweet_url=tweet_url,
            user_handle=user_handle,
            text_content=text_content
        )
        
    except Exception as e:
        logger.error(f"Failed to find tweet: {e}")
        raise


def like_tweet(browser_manager: BrowserManager, tweet: ScrapedTweet) -> bool:
    """
    Like a tweet. Improved version with better selectors.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
    
    driver = browser_manager.get_driver()
    tweet_id = tweet.tweet_id
    tweet_url = tweet.tweet_url
    
    logger.info(f"Attempting to like tweet ID: {tweet_id}")
    
    try:
        # Navigate to the tweet
        logger.info(f"Navigating to tweet URL: {tweet_url}")
        browser_manager.navigate_to(tweet_url)
        time.sleep(3)
        
        # Check if page exists
        page_source = driver.page_source.lower()
        if "this page doesn't exist" in page_source or "this account doesn't exist" in page_source:
            logger.error(f"Tweet {tweet_id} doesn't exist!")
            return False
        
        # Strategy 1: Find tweet article by data-testid
        tweet_article = None
        strategies = [
            f"//article[@data-testid='tweet'][.//a[contains(@href, '/status/{tweet_id}')]]",
            f"//article[.//a[contains(@href, '/status/{tweet_id}')]]",
            "//article[@data-testid='tweet']",
        ]
        
        for xpath in strategies:
            try:
                tweet_article = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                logger.info(f"Found tweet article using: {xpath}")
                break
            except:
                continue
        
        if not tweet_article:
            logger.error(f"Could not find tweet article for {tweet_id}")
            return False
        
        # Find the like button within the article
        # Twitter uses data-testid="like" for the like button
        like_button = None
        like_selectors = [
            './/button[@data-testid="like"]',
            './/div[@data-testid="like"]//button',
            './/button[contains(@aria-label, "Like")]',
        ]
        
        for selector in like_selectors:
            try:
                like_button = tweet_article.find_element(By.XPATH, selector)
                logger.info(f"Found like button using: {selector}")
                break
            except:
                continue
        
        if not like_button:
            # Try page-wide search
            try:
                like_button = driver.find_element(By.XPATH, '//button[@data-testid="like"]')
                logger.info("Found like button using page-wide search")
            except:
                logger.error("Could not find like button")
                return False
        
        # Check if already liked
        aria_label = like_button.get_attribute("aria-label") or ""
        data_testid = like_button.get_attribute("data-testid") or ""
        
        if "unlike" in aria_label.lower() or data_testid == "unlike":
            logger.info(f"Tweet {tweet_id} is already liked!")
            return True
        
        logger.info(f"Like button state - aria-label: '{aria_label}', data-testid: '{data_testid}'")
        
        # Scroll button into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_button)
        time.sleep(0.5)
        
        # Click the like button
        try:
            like_button.click()
            logger.info(f"Clicked like button for tweet {tweet_id}")
        except ElementClickInterceptedException:
            logger.warning("Click intercepted, trying JavaScript click")
            driver.execute_script("arguments[0].click();", like_button)
            logger.info("Clicked via JavaScript")
        
        time.sleep(1.5)
        
        # Verify the like was successful
        try:
            # Re-find the button - it may have changed
            unlike_button = tweet_article.find_element(By.XPATH, './/button[@data-testid="unlike"]')
            logger.info(f"Successfully liked tweet {tweet_id} (found unlike button)")
            return True
        except:
            pass
        
        # Alternative verification via aria-label
        try:
            updated_button = tweet_article.find_element(By.XPATH, './/button[@data-testid="like" or @data-testid="unlike"]')
            new_label = updated_button.get_attribute("aria-label") or ""
            new_testid = updated_button.get_attribute("data-testid") or ""
            if "unlike" in new_label.lower() or new_testid == "unlike":
                logger.info(f"Successfully liked tweet {tweet_id} (aria-label/testid changed)")
                return True
        except:
            pass
        
        logger.warning(f"Could not verify like for tweet {tweet_id}")
        return False
        
    except TimeoutException:
        logger.error(f"Timeout while trying to like tweet {tweet_id}")
        return False
    except Exception as e:
        logger.error(f"Failed to like tweet {tweet_id}: {e}", exc_info=True)
        return False


def test_like():
    """Test the like functionality."""
    # Load config
    config_loader = ConfigLoader()
    accounts = config_loader.get_accounts_config()
    
    if not accounts:
        logger.error("No accounts configured!")
        return
    
    account_config = accounts[0]
    logger.info(f"Using account: {account_config.get('account_id', 'unknown')}")
    
    # Initialize browser
    browser_manager = BrowserManager(account_config, config_loader)
    
    try:
        # Check if searching or using URL
        if len(sys.argv) > 1 and sys.argv[1] == "--search":
            keyword = sys.argv[2] if len(sys.argv) > 2 else "React templates"
            test_tweet = search_and_get_tweet(browser_manager, keyword)
        elif len(sys.argv) > 1:
            tweet_url = sys.argv[1]
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0].split("/")[0]
            test_tweet = ScrapedTweet(
                tweet_id=tweet_id,
                tweet_url=tweet_url,
                user_handle="test_user",
                text_content="Test tweet"
            )
        else:
            # Default: search for a tweet
            test_tweet = search_and_get_tweet(browser_manager, "React templates")
        
        logger.info(f"Testing like for: {test_tweet.tweet_url}")
        logger.info("=" * 60)
        logger.info("Testing LIKE feature")
        logger.info("=" * 60)
        
        result = like_tweet(browser_manager, test_tweet)
        
        if result:
            logger.info("✅ Like test PASSED")
        else:
            logger.error("❌ Like test FAILED")
        
        # Keep browser open for inspection
        input("\nPress Enter to close browser and exit...")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        input("\nPress Enter to close browser and exit...")
    finally:
        browser_manager.close_driver()


if __name__ == "__main__":
    test_like()
