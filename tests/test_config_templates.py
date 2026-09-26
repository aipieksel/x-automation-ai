"""Starter config tests: no Selenium, cookies, network or model calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from core.config_loader import ConfigLoader

class StarterConfigurationTests(unittest.TestCase):
    def test_real_loader_accepts_templates_and_environment_precedence(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-value"}, clear=True):
            loader = ConfigLoader(ROOT / "config/settings.example.json", ROOT / "config/accounts.example.json")
            self.assertEqual(loader.get_api_key("openai_api_key"), "synthetic-test-value")
            self.assertEqual(loader.get_accounts_config()[0]["is_active"], False)
            self.assertEqual(loader.get_setting("browser_settings.type"), "firefox")
            self.assertEqual(json.loads((ROOT / "config/settings.example.json").read_text())["api_keys"]["openai_api_key"], "")

    def test_setup_preserves_user_configuration_on_second_run(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / "config").mkdir()
            (target / "scripts").mkdir()
            for relative in ["config/settings.example.json", "config/accounts.example.json", ".env.example", "scripts/setup.py"]:
                shutil.copyfile(ROOT / relative, target / relative)
            with contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(target / "scripts/setup.py"), run_name="__main__")
                private = target / "config/accounts.json"
                private.write_text('[{"account_id":"user-owned","is_active":false}]')
                runpy.run_path(str(target / "scripts/setup.py"), run_name="__main__")
            self.assertEqual(json.loads(private.read_text())[0]["account_id"], "user-owned")
            self.assertEqual((target / ".env").stat().st_mode & 0o777, 0o600)

if __name__ == "__main__":
    unittest.main()
