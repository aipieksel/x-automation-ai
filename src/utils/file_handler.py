import os
import logging
import sys
import csv
import json
from pathlib import Path
from typing import Set, List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Adjust import path for ConfigLoader and setup_logger
try:
    from ..core.config_loader import ConfigLoader
    from .logger import setup_logger # Assuming logger.py is in the same utils directory
except ImportError:
    # This block allows the script to be run directly for testing,
    # assuming the script is in src/utils and the root is two levels up.
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from src.core.config_loader import ConfigLoader
    from src.utils.logger import setup_logger

config_loader_instance = ConfigLoader() # Initialize once
# Initialize logging configuration and get a module-specific logger
setup_logger(config_loader_instance)
logger = logging.getLogger(__name__)

# Define project root relative to this file's location (src/utils/file_handler.py)
# Path(__file__) -> current file
# .resolve() -> absolute path
# .parent -> src/utils
# .parent -> src
# .parent -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class FileHandler:
    def __init__(self, config_loader: Optional[ConfigLoader] = None, account_id: Optional[str] = None):
        if config_loader is None:
            self.config_loader = config_loader_instance
        else:
            self.config_loader = config_loader
        
        self.twitter_auto_settings: Dict[str, Any] = self.config_loader.get_twitter_automation_setting("", {})
        self.account_id = account_id
        
        # JSONL log file path (replaces CSV for tracking processed tweets)
        self.logs_dir = PROJECT_ROOT / 'logs' / 'accounts'
        self.ensure_directory_exists(self.logs_dir)

    def ensure_directory_exists(self, dir_path: Path) -> None:
        """Ensures that the specified directory exists, creating it if necessary."""
        try:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {dir_path}")
            elif not dir_path.is_dir():
                logger.error(f"Path exists but is not a directory: {dir_path}")
                raise NotADirectoryError(f"{dir_path} exists but is not a directory.")
        except OSError as e:
            logger.error(f"Error creating directory {dir_path}: {e}")
            raise

    def load_processed_action_keys(self, account_id: Optional[str] = None) -> Set[str]:
        """
        Loads processed action_keys from the JSONL log file.
        Each action_key is constructed from action type, account ID, and tweet ID.
        """
        processed_keys: Set[str] = set()
        
        # Use provided account_id or fall back to instance account_id
        acct_id = account_id or self.account_id
        if not acct_id:
            logger.warning("No account_id provided for loading processed action keys.")
            return processed_keys
        
        jsonl_path = self.logs_dir / f'{acct_id}.jsonl'
        
        if not jsonl_path.exists():
            logger.info(f"JSONL log file not found at {jsonl_path}. Starting with an empty set.")
            return processed_keys

        try:
            with jsonl_path.open(mode='r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        action = event.get('action', '')
                        event_account_id = event.get('account_id', acct_id)
                        tweet_id = event.get('meta', {}).get('tweet_id', '')
                        
                        if action and tweet_id:
                            # Construct action_key in same format: {action}_{account_id}_{tweet_id}
                            action_key = f"{action}_{event_account_id}_{tweet_id}"
                            processed_keys.add(action_key)
                    except json.JSONDecodeError:
                        continue
            
            logger.info(f"Loaded {len(processed_keys)} processed action keys from {jsonl_path}")
        except Exception as e:
            logger.error(f"Error loading processed action keys from {jsonl_path}: {e}")
        return processed_keys

    def load_user_interaction_history(self, account_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Loads interaction history per target user from the JSONL log file.
        Returns a dict mapping target_user_handle -> list of interaction records.
        Each record contains: timestamp, action, tweet_id.
        """
        user_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        acct_id = account_id or self.account_id
        if not acct_id:
            logger.warning("No account_id provided for loading user interaction history.")
            return dict(user_history)
        
        jsonl_path = self.logs_dir / f'{acct_id}.jsonl'
        
        if not jsonl_path.exists():
            logger.info(f"JSONL log file not found at {jsonl_path}. Starting with empty user history.")
            return dict(user_history)

        try:
            with jsonl_path.open(mode='r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        action = event.get('action', '')
                        result = event.get('result', '')
                        meta = event.get('meta', {})
                        target_user = meta.get('target_user_handle', '').strip().lstrip('@').lower()
                        tweet_id = meta.get('tweet_id', '')
                        ts_str = event.get('ts', '')
                        
                        # Only track successful engagements with valid target users
                        if target_user and result == 'success' and action in ('reply', 'like', 'retweet', 'quote_tweet', 'post', 'community_reply', 'community_like', 'community_retweet'):
                            try:
                                ts = datetime.fromisoformat(ts_str) if ts_str else None
                            except ValueError:
                                ts = None
                            
                            user_history[target_user].append({
                                'timestamp': ts,
                                'action': action,
                                'tweet_id': tweet_id,
                            })
                    except json.JSONDecodeError:
                        continue
            
            logger.info(f"Loaded interaction history for {len(user_history)} users from {jsonl_path}")
        except Exception as e:
            logger.error(f"Error loading user interaction history from {jsonl_path}: {e}")
        return dict(user_history)

    def can_interact_with_user(
        self, 
        target_user_handle: str, 
        user_history: Dict[str, List[Dict[str, Any]]],
        max_per_day: int = 2,
        min_hours_between: int = 4
    ) -> Tuple[bool, str]:
        """
        Check if we can interact with a target user based on rate limits.
        
        Args:
            target_user_handle: The @handle of the user to interact with
            user_history: Dict from load_user_interaction_history()
            max_per_day: Maximum interactions allowed per user per day (default: 2)
            min_hours_between: Minimum hours between interactions with same user (default: 4)
        
        Returns:
            Tuple of (can_interact: bool, reason: str)
        """
        handle = (target_user_handle or "").strip().lstrip('@').lower()
        if not handle:
            return True, "No target user specified"
        
        interactions = user_history.get(handle, [])
        if not interactions:
            return True, "No previous interactions"
        
        now_utc = datetime.now(timezone.utc)
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count interactions today
        interactions_today = 0
        most_recent_interaction = None
        
        for record in interactions:
            ts = record.get('timestamp')
            if not ts:
                continue
            
            # Make sure ts is timezone-aware for comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            
            # Track most recent
            if most_recent_interaction is None or ts > most_recent_interaction:
                most_recent_interaction = ts
            
            # Count if today
            if ts >= today_start:
                interactions_today += 1
        
        # Check daily limit
        if interactions_today >= max_per_day:
            return False, f"Daily limit reached ({interactions_today}/{max_per_day} interactions with @{handle} today)"
        
        # Check time since last interaction
        if most_recent_interaction:
            hours_since = (now_utc - most_recent_interaction).total_seconds() / 3600
            if hours_since < min_hours_between:
                remaining = min_hours_between - hours_since
                return False, f"Too soon since last interaction with @{handle} ({hours_since:.1f}h ago, need {min_hours_between}h gap, {remaining:.1f}h remaining)"
        
        return True, f"OK ({interactions_today}/{max_per_day} today)"

    def save_processed_action_key(self, action_key: str, timestamp: Optional[str] = None, **extra_data: Any) -> bool:
        """
        This method is now a no-op since logging is handled by MetricsRecorder.log_event().
        Kept for backward compatibility but does nothing.
        """
        # No longer needed - MetricsRecorder.log_event() handles this
        logger.debug(f"save_processed_action_key called for {action_key} - now handled by MetricsRecorder")
        return True

    # --- Generic File Utilities ---

    def read_text(self, file_path: Path) -> Optional[str]:
        """Reads entire content from a text file."""
        try:
            if not file_path.is_file():
                logger.warning(f"Text file not found: {file_path}")
                return None
            content = file_path.read_text(encoding='utf-8')
            logger.debug(f"Successfully read text file: {file_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            return None

    def write_text(self, file_path: Path, content: str, append: bool = False) -> bool:
        """Writes or appends content to a text file. Ensures directory exists."""
        try:
            self.ensure_directory_exists(file_path.parent)
            mode = 'a' if append else 'w'
            with file_path.open(mode=mode, encoding='utf-8') as file:
                file.write(content)
            logger.debug(f"Successfully {'appended to' if append else 'wrote to'} text file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing to text file {file_path}: {e}")
            return False

    def read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Reads data from a JSON file."""
        try:
            if not file_path.is_file():
                logger.warning(f"JSON file not found: {file_path}")
                return None
            with file_path.open('r', encoding='utf-8') as file:
                data = json.load(file)
            logger.debug(f"Successfully read JSON file: {file_path}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading JSON file {file_path}: {e}")
            return None

    def write_json(self, file_path: Path, data: Dict[str, Any], indent: int = 4) -> bool:
        """Writes data to a JSON file. Ensures directory exists."""
        try:
            self.ensure_directory_exists(file_path.parent)
            with file_path.open('w', encoding='utf-8') as file:
                json.dump(data, file, indent=indent, ensure_ascii=False)
            logger.debug(f"Successfully wrote JSON to file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing JSON to file {file_path}: {e}")
            return False

    def list_files(self, directory_path: Path, pattern: str = "*") -> List[Path]:
        """Lists files in a directory, optionally matching a glob pattern."""
        try:
            if not directory_path.is_dir():
                logger.warning(f"Directory not found for listing files: {directory_path}")
                return []
            files = list(directory_path.glob(pattern))
            logger.debug(f"Found {len(files)} files in {directory_path} matching '{pattern}'.")
            return files
        except Exception as e:
            logger.error(f"Error listing files in directory {directory_path}: {e}")
            return []
            
    def delete_file(self, file_path: Path) -> bool:
        """Deletes a file."""
        try:
            if not file_path.is_file():
                logger.warning(f"File not found for deletion: {file_path}")
                return False
            file_path.unlink()
            logger.info(f"Successfully deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False


if __name__ == '__main__':
    # Example Usage
    # Ensure config is loaded for logger, or provide a mock/simple config for testing
    # For simplicity, we assume config_loader_instance and logger are set up globally
    
    # Create a temporary directory for testing relative to this script file
    test_dir = Path(__file__).parent / "test_file_handler_output"
    if not test_dir.exists():
        test_dir.mkdir(parents=True, exist_ok=True)

    # Override processed_tweets_file_path for testing to be inside test_dir
    # This requires a bit of a workaround if we want to test FileHandler's own config reading
    # For a direct test, we can instantiate FileHandler and then change its path attribute
    
    # A more direct way to test is to mock ConfigLoader or provide a test config file.
    # For this example, let's assume the default 'processed_tweets_log.csv' will be created in PROJECT_ROOT
    # or we can manually set the path for the test instance.
    
    # To avoid polluting the project root, let's create a custom config for testing
    # or simply use the new methods with explicit paths within our test_dir.

    print(f"--- FileHandler Tests (output in: {test_dir.resolve()}) ---")
    
    # Instantiate FileHandler - it will use global config_loader_instance
    # Its processed_tweets_file_path will be based on your actual project config or default.
    # For isolated testing of CSV methods, let's make a specific test file path.
    
    file_handler = FileHandler() # Uses global config
    
    # For processed_actions_keys, let's use a dedicated test file
    original_processed_path = file_handler.processed_tweets_file_path
    test_csv_path = test_dir / "test_processed_actions.csv"
    file_handler.processed_tweets_file_path = test_csv_path # Override for test
    
    # Clean up previous test CSV if it exists
    if test_csv_path.exists():
        test_csv_path.unlink()

    print(f"\n--- Testing Processed Action Keys (CSV at {test_csv_path}) ---")
    # Test loading (file might not exist initially)
    print("--- Testing Load (Initial) ---")
    initial_keys = file_handler.load_processed_action_keys()
    print(f"Initial processed action_keys: {initial_keys}")

    # Test saving
    print("\n--- Testing Save ---")
    from datetime import datetime
    ts = datetime.now().isoformat()
    file_handler.save_processed_action_key("reply_user1_tweet123", timestamp=ts, source="test_script")
    file_handler.save_processed_action_key("like_user1_tweet456", timestamp=ts, source="test_script", attempts=1)
    file_handler.save_processed_action_key("repost_user2_tweet789", source="another_test") # No timestamp, different extra data

    # Test loading again
    print("\n--- Testing Load (After Save) ---")
    updated_keys = file_handler.load_processed_action_keys()
    print(f"Updated processed action_keys: {updated_keys}")
    print(f"Check the file: {test_csv_path}")

    # --- Test Generic Utilities ---
    print("\n--- Testing Generic File Utilities ---")

    # Test Text Files
    test_text_file = test_dir / "sample.txt"
    print(f"\n--- Testing Text File: {test_text_file} ---")
    file_handler.write_text(test_text_file, "Hello, World!\n")
    file_handler.write_text(test_text_file, "This is a new line.", append=True)
    content = file_handler.read_text(test_text_file)
    print(f"Content of {test_text_file}:\n{content}")

    # Test JSON Files
    test_json_file = test_dir / "sample.json"
    print(f"\n--- Testing JSON File: {test_json_file} ---")
    json_data = {"name": "Test User", "id": 123, "active": True, "tags": ["test", "example"]}
    file_handler.write_json(test_json_file, json_data)
    read_data = file_handler.read_json(test_json_file)
    print(f"Content of {test_json_file}: {read_data}")
    
    # Test Listing Files
    print(f"\n--- Testing List Files in {test_dir} ---")
    # Create some dummy files for listing
    (test_dir / "file1.txt").touch()
    (test_dir / "file2.log").touch()
    (test_dir / "another.json").touch()
    
    all_files = file_handler.list_files(test_dir)
    print(f"All files in {test_dir}: {[f.name for f in all_files]}")
    
    txt_files = file_handler.list_files(test_dir, pattern="*.txt")
    print(f"Text files in {test_dir}: {[f.name for f in txt_files]}")

    json_files = file_handler.list_files(test_dir, pattern="*.json")
    print(f"JSON files in {test_dir}: {[f.name for f in json_files]}")

    # Test Deleting Files
    file_to_delete = test_dir / "file_to_delete.tmp"
    file_handler.write_text(file_to_delete, "This file will be deleted.")
    print(f"\n--- Testing Delete File: {file_to_delete} ---")
    if file_to_delete.exists():
        print(f"File {file_to_delete.name} exists before deletion.")
    else:
        print(f"File {file_to_delete.name} does NOT exist before deletion (ERROR IN TEST SETUP).")
        
    delete_success = file_handler.delete_file(file_to_delete)
    print(f"Deletion successful: {delete_success}")
    
    if file_to_delete.exists():
        print(f"File {file_to_delete.name} STILL exists after deletion (DELETION FAILED).")
    else:
        print(f"File {file_to_delete.name} no longer exists after deletion.")

    # Restore original path if it was changed for testing (though instance is local to main)
    file_handler.processed_tweets_file_path = original_processed_path

    print(f"\n--- End of FileHandler Tests ---")
    print(f"NOTE: You might want to manually delete the '{test_dir.resolve()}' directory after inspection.")
    # Example: To clean up test_dir (optional, be careful with rmtree)
    # import shutil
    # print(f"\nCleaning up test directory: {test_dir}")
    # shutil.rmtree(test_dir)
