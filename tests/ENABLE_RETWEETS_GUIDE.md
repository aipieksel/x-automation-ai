# Quick Start: Enabling Retweet/Repost Features

## ✅ What Was Fixed

The retweet dropdown menu detection has been completely rewritten with:
- Multiple fallback selector strategies
- Retry mechanism (3 attempts)
- Better error handling and logging
- Detection of already-retweeted state

## 🧪 Step 1: Test the Fix

Before enabling in production, test with a single tweet:

```bash
cd /path/to/x-automation-ai
source .venv/bin/activate
python tests/test_retweet_fix.py https://x.com/example/status/1234567890
```

Replace the URL with an actual tweet you want to test retweet on.

**What to expect:**
- Browser opens automatically
- Navigates to the tweet
- Clicks retweet button
- Selects "Repost" from dropdown
- Browser stays open for 30 seconds for inspection
- Console shows success/failure

## 🚀 Step 2: Enable Keyword Retweets

If the test succeeds, enable it in the automation:

### Edit `config/accounts.json`

Find the `"enable_keyword_retweets"` line and change it:

```json
{
  "action_config_override": {
    "enable_keyword_retweets": true,
    "max_retweets_per_keyword_run": 1
  }
}
```

**Recommended settings:**
- Start with `max_retweets_per_keyword_run: 1` (conservative)
- After 24h of successful operation, increase to `2`
- Maximum recommended: `3` to avoid rate limits

## 🎯 Step 3: Enable Competitor Reposts (Optional)

If you also want to retweet competitor posts:

```json
{
  "action_config_override": {
    "enable_competitor_reposts": true,
    "max_posts_per_competitor_run": 1,
    "competitor_post_interaction_type": "retweet"
  }
}
```

**Options for `competitor_post_interaction_type`:**
- `"retweet"` - Simple retweet (no comment)
- `"quote_tweet"` - Retweet with AI-generated comment
- `"repost"` - Create new post inspired by the original

## 📊 Step 4: Monitor Activity

### Watch live activity:
```bash
tail -f logs/accounts/example-account.jsonl | grep retweet
```

### Count successful retweets today:
```bash
grep "$(date +%Y-%m-%d)" logs/accounts/example-account.jsonl | grep '"action": "retweet"' | grep -c success
```

### Check for errors:
```bash
grep "$(date +%Y-%m-%d)" logs/accounts/example-account.jsonl | grep retweet | grep failure
```

## ⚙️ Full Configuration Example

Here's a complete working configuration:

```json
{
  "action_config_override": {
    "min_delay_between_actions_seconds": 120,
    "max_delay_between_actions_seconds": 240,
    
    "enable_keyword_replies": true,
    "max_replies_per_keyword_run": 5,
    
    "enable_keyword_retweets": true,
    "max_retweets_per_keyword_run": 1,
    
    "enable_competitor_reposts": false,
    "max_posts_per_competitor_run": 1,
    "competitor_post_interaction_type": "quote_tweet"
  }
}
```

## 🔄 Rollback if Needed

If you encounter issues:

1. **Quick disable:**
   ```json
   "enable_keyword_retweets": false
   ```

2. **Check what went wrong:**
   ```bash
   tail -50 logs/accounts/example-account.jsonl | grep -E "(retweet|error)"
   ```

## ⚠️ Rate Limit Guidelines

Twitter/X has rate limits for retweets:
- **Recommended:** 10-15 retweets per hour maximum
- **Conservative:** 5-10 retweets per hour
- **With delays:** 2-4 minute delays between actions help avoid detection

Our current settings:
- Min delay: 120 seconds (2 min)
- Max delay: 240 seconds (4 min)
- Max per keyword: 1 retweet
- With 15 keywords: ~15 retweets per full cycle

This is safe and within Twitter's limits.

## 📝 Notes

- The bot automatically skips tweets already retweeted
- Failed retweets are logged but don't stop the automation
- Competitor reposting may need additional testing before enabling

---

**Ready to test?** Run:
```bash
python tests/test_retweet_fix.py <tweet-url>
```
