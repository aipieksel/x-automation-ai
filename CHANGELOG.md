# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed - 2026-01-06

#### Retweet/Repost Functionality Restored
- **Fixed broken retweet dropdown detection** after Twitter/X UI changes
- Implemented multi-strategy selector approach for menu items:
  - Primary: `data-testid='retweetConfirm'`
  - Fallback 1: Menu item with "Repost" text
  - Fallback 2: Menu item with "Retweet" text
  - Fallback 3: First menu item in dropdown
- Added 3-attempt retry mechanism with re-clicking
- Enhanced error handling and logging
- Added detection for already-retweeted tweets
- Improved click reliability with JavaScript fallback

**Files changed:**
- `src/features/publisher/retweet_handler.py` - Core retweet logic
- Account-specific operational notes are omitted from this reusable source package.
- `test_retweet_fix.py` - New standalone test script
- `RETWEET_FIX_SUMMARY.md` - Technical documentation
- `ENABLE_RETWEETS_GUIDE.md` - User guide for enabling feature

**Testing:**
```bash
python test_retweet_fix.py https://x.com/username/status/1234567890
```

**To enable:**
Set `"enable_keyword_retweets": true` in `config/accounts.json`

---

## [Previous] - Before 2026-01-06

### Disabled Features
- Keyword retweets disabled due to dropdown selector issues
- Competitor reposts disabled due to UI selector changes
- Like functionality disabled due to unreliable button detection

### Active Features
- ✅ Keyword-based replies (main engagement strategy)
- ✅ AI-powered content generation via GPT-4o
- ✅ Sentiment analysis for context-aware responses
- ✅ Engagement decision making
- ✅ Proxy support with rotation
- ✅ Cookie-based authentication
- ✅ Comprehensive logging and metrics

---

## How to Use This Changelog

When making changes:
1. Add entry under `[Unreleased]` section
2. Use categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`
3. Include date and brief description
4. Link to relevant documentation or PRs if applicable
