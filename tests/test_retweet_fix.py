"""
Simple test script to verify retweet functionality works correctly.
Tests the updated retweet_handler with the new dropdown selectors.

Usage:
    python test_retweet_fix.py [tweet_url]
    python test_retweet_fix.py --search "keyword"

Example:
    python test_retweet_fix.py https://x.com/username/status/1234567890
    python test_retweet_fix.py --search "React templates"
"""
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.browser_manager import BrowserManager
from core.config_loader import ConfigLoader
from core.llm_service import LLMService
from data_models import ScrapedTweet, LLMSettings
from features.publisher.retweet_handler import retweet_or_quote

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
        return None


def test_retweet(tweet_url: str = None, search_keyword: str = None):
    """Test retweet functionality with a specific tweet URL or by searching."""
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        accounts_data = config_loader.get_accounts_config()
        
        if not accounts_data:
            logger.error("No accounts found in configuration")
            return False
        
        # Import AccountConfig to parse account data
        from data_models import AccountConfig
        
        # Find first active account
        account = None
        for acc_data in accounts_data:
            if acc_data.get("is_active", False):
                account = AccountConfig(**acc_data)
                break
        
        if not account:
            logger.error("No active accounts found")
            return False
        
        logger.info(f"Using account: {account.account_id}")
        
        # Prepare account_config dict for BrowserManager
        account_config = {
            "account_id": account.account_id,
            "cookies": account.cookie_file_path,
            "proxy": account.proxy,
        }
        
        # Initialize browser with visible mode for debugging
        browser_manager = BrowserManager(
            account_config=account_config,
            config_loader=config_loader
        )
        
        # Override headless setting to False for testing
        browser_manager.browser_settings['headless'] = False
        
        # Get the tweet to test
        if search_keyword:
            test_tweet = search_and_get_tweet(browser_manager, search_keyword)
            if not test_tweet:
                logger.error("Could not find a tweet to test")
                return False
        else:
            # Use provided URL
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0]
            test_tweet = ScrapedTweet(
                tweet_id=tweet_id,
                tweet_url=tweet_url,
                user_handle="test_user",
                text_content="Test tweet"
            )
        
        logger.info(f"Testing retweet for: {test_tweet.tweet_url}")
        
        # Check for command line argument to select test type
        test_type = "1"  # Default to simple repost
        if len(sys.argv) > 3:
            test_type = sys.argv[3]
        else:
            # Ask interactively
            print("\nWhich test would you like to run?")
            print("1. Simple Repost (no comment)")
            print("2. Quote Tweet (repost with AI-generated comment)")
            try:
                choice = input("Enter 1 or 2 (default: 1): ").strip() or "1"
                test_type = choice
            except EOFError:
                test_type = "1"
        
        if test_type == "2":
            # Test quote tweet with AI-generated comment
            logger.info("=" * 60)
            logger.info("Testing QUOTE TWEET (repost with AI comment)")
            logger.info("=" * 60)
            
            # Generate quote text using LLM service (same as production)
            import asyncio
            settings = config_loader.get_settings()
            llm_service = LLMService(config_loader)  # Pass config_loader, not settings
            llm_settings = LLMSettings(
                service_preference=settings.get('llm_service_preference', 'openai'),
                model_name_override=settings.get('llm_model_name_override', 'gpt-4o'),
                max_tokens=settings.get('llm_max_tokens', 800),
                temperature=settings.get('llm_temperature', 0.78)
            )
            
            # Build a prompt based on the tweet content
            tweet_text = test_tweet.text_content or "web development templates"
            quote_prompt = (
                f"Generate a short, engaging quote comment (under 200 characters) for retweeting this tweet: "
                f"'{tweet_text[:200]}'. "
                f"Be conversational, relevant, and avoid excessive hashtags. "
                f"Use only the supplied tweet as context; do not invent an account identity or promotion."
            )
            
            logger.info(f"Generating quote with LLM...")
            quote_text = asyncio.run(llm_service.generate_text(
                prompt=quote_prompt,
                service_preference=llm_settings.service_preference,
                model_name=llm_settings.model_name_override,
                max_tokens=200,
                temperature=0.8
            ))
            
            if not quote_text:
                quote_text = "Check this out! 🔥"
                logger.warning("LLM failed, using fallback quote text")
            else:
                # Clean up the quote text
                quote_text = quote_text.strip().strip('"').strip("'")[:270]
            
            logger.info(f"Quote text: {quote_text}")
            
            result = retweet_or_quote(
                browser_manager=browser_manager,
                original_tweet=test_tweet,
                final_quote_text=quote_text
            )
            
            if result:
                logger.info("✅ Quote Tweet test PASSED")
            else:
                logger.error("❌ Quote Tweet test FAILED")
        else:
            # Test simple retweet (no quote)
            logger.info("=" * 60)
            logger.info("Testing SIMPLE REPOST (no comment)")
            logger.info("=" * 60)
            
            result = retweet_or_quote(
                browser_manager=browser_manager,
                original_tweet=test_tweet,
                final_quote_text=None
            )
            
            if result:
                logger.info("✅ Repost test PASSED")
            else:
                logger.error("❌ Repost test FAILED")
        
        # Keep browser open for inspection
        input("\nPress Enter to close browser and exit...")
        
        browser_manager.close_driver()
        return result
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_retweet_fix.py <tweet_url>")
        print("  python test_retweet_fix.py --search \"keyword\"")
        print("\nExamples:")
        print("  python test_retweet_fix.py https://x.com/username/status/1234567890")
        print("  python test_retweet_fix.py --search \"React templates\"")
        sys.exit(1)
    
    if sys.argv[1] == "--search":
        if len(sys.argv) < 3:
            print("❌ Please provide a search keyword")
            sys.exit(1)
        keyword = sys.argv[2]
        success = test_retweet(search_keyword=keyword)
    else:
        tweet_url = sys.argv[1]
        
        if not tweet_url.startswith("http"):
            print("❌ Invalid tweet URL. Must start with http:// or https://")
            sys.exit(1)
        
        if "/status/" not in tweet_url:
            print("❌ Invalid tweet URL. Must contain /status/")
            sys.exit(1)
        
        success = test_retweet(tweet_url=tweet_url)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
