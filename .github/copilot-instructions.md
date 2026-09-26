# X Automation AI - Copilot Instructions

## Architecture Overview

This is a **Selenium-based Twitter/X automation bot** with LLM integration for content generation. Core flow:

```
main.py (TwitterOrchestrator) 
  → ConfigLoader (config/*.json)
  → BrowserManager (Selenium/undetected-chromedriver)
  → Features: TweetScraper, TweetPublisher, TweetAnalyzer, TweetEngagement
  → LLMService (OpenAI/Gemini/DeepSeek/Azure)
```

**Key architectural decisions:**
- Per-account everything: configs, cookies, proxies, logs, metrics
- Action deduplication via JSONL logs (`logs/accounts/{account_id}.jsonl`)
- Pydantic models enforce config/data validation ([data_models.py](../src/data_models.py))

## Configuration Hierarchy

Settings cascade: **global defaults → per-account overrides**

1. [config/settings.json](../config/settings.example.json) - API keys, global action_config, browser_settings
2. [config/accounts.json](../config/accounts.example.json) - Per-account: `action_config_override`, `llm_settings_override`

**Naming convention for overrides:** Fields in accounts.json ending in `_override` map to base field names (e.g., `target_keywords_override` → `target_keywords`). See `_normalize_account_config()` in [main.py](../src/main.py#L152).

## Critical Patterns

### LLM Service Usage
```python
# Structured JSON generation with retries
data, err = await llm_service.generate_structured(
    task_instruction="...",
    schema={"field": "description"},
    service_preference="deepseek",  # or "openai", "gemini", "azure"
)
```
Supported providers initialized in [llm_service/clients.py](../src/core/llm_service/clients.py). DeepSeek uses OpenAI-compatible API.

### Browser Automation
- Cookies loaded from `data/cookies/{account}_cookies.json` (JSON array format)
- `BrowserManager.navigate_to()` handles all page navigation
- Tweet interactions use XPath selectors in [scraper/selectors.py](../src/features/scraper/selectors.py)

### Action Deduplication
Action keys format: `{action}_{account_id}_{tweet_id}` (e.g., `reply_example-account_123456`)
- Loaded at startup from JSONL via `file_handler.load_processed_action_keys()`
- Written automatically by `MetricsRecorder.log_event()`

## Development Commands

```bash
# Run continuously (standard operation)
python -m src.main --continuous

# Single run (one cycle, then exit)
python -m src.main

# Test specific components
python -c "from src.core.llm_service import LLMService; ..."
```

## File Locations

| Purpose | Location |
|---------|----------|
| Account configs | `config/accounts.json` |
| Global settings | `config/settings.json` |
| Cookie files | `data/cookies/*.json` |
| Action logs | `logs/accounts/{account_id}.jsonl` |
| Metrics | `data/metrics/{account_id}.json` |
| Presets (templates) | `config/presets/accounts/*.json`, `config/presets/settings/*.json` |

## Common Modifications

**Adjust action timing:** Edit `action_config_override` in accounts.json:
- `min_delay_between_actions_seconds` / `max_delay_between_actions_seconds`

**Change LLM provider:** Set `llm_settings_override.service_preference` to `"openai"`, `"gemini"`, `"deepseek"`, or `"azure"`

**Enable/disable features:** Toggle flags like `enable_keyword_replies`, `enable_competitor_reposts`, `enable_liking_tweets` in `action_config_override`

## Testing Notes

- Never hardcode tweet IDs; they change constantly
- Browser must be non-headless for debugging interactions
- Use `start_minimized: true` in browser_settings for background operation
