import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Union, Optional

# Define project root relative to this file's location (src/core/config_loader.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / 'config'
DEFAULT_SETTINGS_FILE = CONFIG_DIR / 'settings.json'
DEFAULT_ACCOUNTS_FILE = CONFIG_DIR / 'accounts.json'

logger = logging.getLogger(__name__)

API_ENVIRONMENT = {
    'openai_api_key': 'OPENAI_API_KEY',
    'gemini_api_key': 'GEMINI_API_KEY',
    'deepseek_api_key': 'DEEPSEEK_API_KEY',
    'azure_openai_api_key': 'AZURE_OPENAI_API_KEY',
    'azure_openai_endpoint': 'AZURE_OPENAI_ENDPOINT',
    'azure_openai_deployment': 'AZURE_OPENAI_DEPLOYMENT',
    'azure_api_version': 'AZURE_OPENAI_API_VERSION',
}

class ConfigLoader:
    def __init__(self, settings_file: Union[str, Path] = DEFAULT_SETTINGS_FILE, 
                 accounts_file: Union[str, Path] = DEFAULT_ACCOUNTS_FILE):
        """
        Initializes the ConfigLoader.

        Args:
            settings_file (Union[str, Path], optional): Path to the settings JSON file. 
                                                        Defaults to 'config/settings.json'.
            accounts_file (Union[str, Path], optional): Path to the accounts JSON file. 
                                                        Defaults to 'config/accounts.json'.
        """
        self.settings_file: Path = Path(settings_file)
        self.accounts_file: Path = Path(accounts_file)
        # Existing shell/service values take precedence over a private .env.
        try:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_ROOT / '.env', override=False)
        except ImportError:
            pass  # Environment variables still work without python-dotenv.
        
        self.settings: Dict[str, Any] = self._load_json(self.settings_file, default_value={})
        self.accounts: List[Dict[str, Any]] = self._load_json(self.accounts_file, default_value=[])
        if isinstance(self.settings, dict):
            keys = dict(self.settings.get('api_keys') or {})
            for key, variable in API_ENVIRONMENT.items():
                value = os.environ.get(variable)
                if value and value.strip():
                    keys[key] = value.strip()
            self.settings['api_keys'] = keys
        
        if not self.settings:
            logger.warning(f"Settings file '{self.settings_file}' was not found or is empty/invalid. Using empty settings.")
        if not self.accounts:
            logger.warning(f"Accounts file '{self.accounts_file}' was not found or is empty/invalid. Using empty accounts list.")

    def _load_json(self, file_path: Path, default_value: Union[Dict, List]) -> Any:
        """
        Loads a JSON file.

        Args:
            file_path (Path): The path to the JSON file.
            default_value (Union[Dict, List]): The default value to return if loading fails.

        Returns:
            Any: The loaded JSON data or the default value.
        """
        if not file_path.exists():
            logger.error(f"Configuration file not found: {file_path}")
            return default_value
        if not file_path.is_file():
            logger.error(f"Configuration path is not a file: {file_path}")
            return default_value
            
        try:
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Successfully loaded JSON from {file_path}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Could not decode JSON from {file_path}: {e}")
            return default_value
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading {file_path}: {e}")
            return default_value

    def get_settings(self) -> Dict[str, Any]:
        """Returns all loaded settings."""
        return self.settings

    def get_accounts_config(self) -> List[Dict[str, Any]]:
        """Returns all loaded account configurations."""
        return self.accounts

    def get_setting(self, path_str: str, default: Any = None) -> Any:
        """
        Retrieves a setting value using a dot-separated path.

        Args:
            path_str (str): Dot-separated path to the setting (e.g., "logging.level").
            default (Any, optional): Default value if the setting is not found. Defaults to None.

        Returns:
            Any: The setting value or the default.
        """
        keys = path_str.split('.')
        current_level = self.settings
        try:
            for key in keys:
                if isinstance(current_level, dict):
                    current_level = current_level[key]
                else: # Path leads to a non-dict item before all keys are consumed
                    logger.warning(f"Invalid path '{path_str}' at key '{key}'. Expected a dictionary, found {type(current_level)}.")
                    return default
            return current_level
        except KeyError:
            logger.debug(f"Setting '{path_str}' not found. Returning default: {default}")
            return default
        except Exception as e:
            logger.warning(f"Error accessing setting '{path_str}': {e}. Returning default: {default}")
            return default

    def get_api_key(self, service_name: str) -> Optional[str]:
        """Retrieves an API key for a specific service."""
        return self.get_setting(f'api_keys.{service_name}')

    def get_twitter_automation_setting(self, setting_name: str, default: Any = None) -> Any:
        """Retrieves a specific setting from the 'twitter_automation' block."""
        return self.get_setting(f'twitter_automation.{setting_name}', default)

    def get_logging_setting(self, setting_name: str, default: Any = None) -> Any:
        """Retrieves a specific setting from the 'logging' block."""
        return self.get_setting(f'logging.{setting_name}', default)

if __name__ == '__main__':
    # Inspect readiness without logging credentials or creating personal files.
    logging.basicConfig(level=logging.INFO)
    loader = ConfigLoader()
    print(f"Loaded {len(loader.get_accounts_config())} account configuration(s).")
    print("Configured providers:", ", ".join(
        key.removesuffix('_api_key') for key in API_ENVIRONMENT
        if key.endswith('_api_key') and loader.get_api_key(key)
    ) or "none")
