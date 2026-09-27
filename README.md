# X Automation AI

Maintained by [aipieksel](https://github.com/aipieksel). Based on the upstream Twitter Automation AI project; its [MIT license](LICENSE) and author notice are retained.

X Automation AI is a configurable Python/Selenium project for operating X accounts you control. It combines browser actions with optional AI-generated content for posts, replies, likes, reposts, and community activity, then records per-account activity metrics. The examples are inactive until you supply your own account settings and session cookies.

Each enabled account has its own topics, action settings, and provider configuration. The browser uses that account's signed-in session; model calls use the credentials you configure. Running the main module performs real account actions, so review the account and action settings before starting it. Browser selectors and provider availability can change with the external platforms.

## How it works

1. Create private settings from the examples and configure an account you own.
2. Set its intended actions, content topics, model provider, and browser session.
3. Start the scheduler only after reviewing the enabled actions and their effects.

## Start with your own configuration

Use Python 3.10+ and Chrome for browser execution. From this folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup.py
```

The setup helper creates private `config/settings.json`, `config/accounts.json`, and `.env` from the shipped examples. Existing files are preserved. Configure your own API keys in `.env`; nonblank environment values override `settings.json` keys. Review every account field in [accounts.example.json](config/accounts.example.json) and global option in [settings.example.json](config/settings.example.json).

The example account is inactive. Supply your own cookie file path, account handle, topics, provider/model settings, and any optional proxy/community settings before enabling it. Cookie files authenticate your account and must stay private. Presets under `config/presets/` are examples; they do not contain a usable signed-in session.

After reviewing the configured account and intended actions, launch from the project root:

```sh
.venv/bin/python -m src.main
```

This starts real automation for enabled accounts; it is not a dry-run command.

## Development and layout

- `src/core/`: configuration, browser/account management and scheduling.
- `src/`: action, content and provider implementation.
- `config/`: trackable starter files; private live settings are ignored.
- `scripts/setup.py`: non-overwriting local configuration setup.
- `tests/`: configuration checks and older manual browser diagnostics.

Run the local configuration checks without a signed-in browser:

```sh
.venv/bin/python -m unittest discover -s tests -p test_config_templates.py -v
```

Inspect other test scripts before running them: some operate on a live X session. Logs, cookie files, metrics, screenshots, generated media, and real account configuration belong outside the shared source tree. Provider usage may incur charges; the supplied examples do not enable an account.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributions. Product features are under development; no reliability or platform-approval claim is made by the starter templates.
