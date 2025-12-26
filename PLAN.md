# Amul Protein Alert Bot - Complete FREE Build Plan

## Project Overview
A Telegram bot that monitors Amul website for product availability and sends real-time notifications to users.

**Cost: ZERO** - Everything uses free, open-source tools

---

## Current Status: 90% Complete

### Already Built:
- [x] Telegram bot framework (python-telegram-bot)
- [x] Amul website API integration
- [x] Pincode validation and store lookup
- [x] Product catalog fetching
- [x] User subscription management
- [x] Background stock monitoring (every 5 mins)
- [x] SQLite database (users, products, subscriptions, alerts)
- [x] 4 types of notifications (back in stock, increased, low stock, sold out)
- [x] All bot commands (/start, /help, /setpincode, /products, /mystatus, /instock, /stop)

### Remaining:
- [ ] Create Telegram bot via BotFather
- [ ] Configure environment variables
- [ ] Test locally
- [ ] Deploy to free hosting

---

## Phase 1: Setup Telegram Bot (5 minutes)

### Step 1.1: Create Bot with BotFather
1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `Amul Protein Alert`
4. Choose username: `AmulProteinAlertBot` (must end with 'bot')
5. **Copy the BOT TOKEN** - you'll need this!

### Step 1.2: Configure Bot Commands (Optional but recommended)
Send to BotFather:
```
/setcommands
```
Then select your bot and paste:
```
start - Start the bot and register
help - Show available commands
setpincode - Set your delivery pincode
products - Browse and subscribe to products
mystatus - View your subscriptions
instock - Check currently available products
stop - Unsubscribe from all notifications
```

### Step 1.3: Set Bot Description
```
/setdescription
```
Paste:
```
I help you get real-time notifications when Amul High Protein products become available in your area.

1. Set your pincode
2. Choose products to track
3. Get instant alerts when stock is available
4. Never miss your favorite Amul products!
```

---

## Phase 2: Local Configuration (2 minutes)

### Step 2.1: Create Environment File
Create `.env` file in project root:
```env
BOT_TOKEN=your_telegram_bot_token_here
```

### Step 2.2: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Phase 3: Local Testing (10 minutes)

### Step 3.1: Run the Bot
```bash
python main.py
```

### Step 3.2: Test Commands
1. Open your bot in Telegram
2. Send `/start` - Should welcome you
3. Send `/setpincode` - Enter your 6-digit pincode
4. Send `/products` - Browse and select products
5. Send `/mystatus` - Check your subscriptions
6. Send `/instock` - See available products

### Step 3.3: Verify Stock Monitoring
- Wait 5 minutes or check logs for stock check activity
- The bot should log: "Starting stock check for all active users"

---

## Phase 4: FREE Deployment Options

### Option A: Railway.app (Recommended - Easiest)
**Free Tier:** 500 hours/month (enough for 24/7 running)

1. Go to https://railway.app
2. Sign up with GitHub (free)
3. Click "New Project" → "Deploy from GitHub repo"
4. Connect your GitHub and push your code
5. Add environment variable: `BOT_TOKEN`
6. Deploy automatically!

**Pros:** Auto-deploy, easy setup, good free tier
**Cons:** May need to redeploy monthly

### Option B: Render.com
**Free Tier:** 750 hours/month

1. Go to https://render.com
2. Sign up (free)
3. Create "Background Worker" (not Web Service)
4. Connect GitHub repo
5. Set build command: `pip install -r requirements.txt`
6. Set start command: `python main.py`
7. Add environment variable: `BOT_TOKEN`

**Pros:** Generous free tier, reliable
**Cons:** Spins down after inactivity (use cron-job.org to ping)

### Option C: PythonAnywhere
**Free Tier:** Always-on task available
ac
1. Go to https://www.pythonanywhere.com
2. Sign up (free)
3. Upload files via Files tab
4. Go to Tasks → Create new task
5. Command: `python /home/yourusername/AmulBot/main.py`

**Pros:** True always-on, no spindown
**Cons:** Limited CPU time, manual file upload

### Option D: Your Own Computer (24/7)
Run on Raspberry Pi or old laptop:
```bash
# Use screen to keep running after disconnect
screen -S amulbot
python main.py
# Press Ctrl+A then D to detach
```

### Option E: Oracle Cloud Free Tier (Best for Power Users)
**Free Forever:** 2 AMD VMs with 1GB RAM each

1. Sign up at https://cloud.oracle.com (requires card, NO charges)
2. Create "Always Free" VM (Ubuntu)
3. SSH into VM
4. Clone repo and run with systemd service

---

## Phase 5: Make it Production Ready

### Step 5.1: Add Logging to File
Already configured in `main.py` - logs go to console

### Step 5.2: Database Backup (Optional)
The `amul_bot.db` SQLite file contains all data.
For cloud deployment, consider backing up periodically.

### Step 5.3: Error Monitoring (Optional - Free)
Use Sentry.io free tier for error tracking:
```python
# Add to main.py
import sentry_sdk
sentry_sdk.init("your-sentry-dsn")
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM USERS                          │
│                   (Your subscribers)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 TELEGRAM BOT API                            │
│              (Free, hosted by Telegram)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│               YOUR BOT APPLICATION                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Handlers  │  │  Scheduler  │  │   Database  │        │
│  │  /start     │  │  (5 min     │  │   (SQLite)  │        │
│  │  /products  │  │   interval) │  │             │        │
│  │  /setpin    │  │             │  │  - users    │        │
│  └─────────────┘  └─────────────┘  │  - products │        │
│                                     │  - subs     │        │
│                                     └─────────────┘        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  AMUL WEBSITE API                           │
│              (shop.amul.com - Free to access)               │
│                                                             │
│  Endpoints used:                                            │
│  - /entity/pincode (validate delivery area)                 │
│  - /api/1/entity/ms.products (get products & stock)         │
└─────────────────────────────────────────────────────────────┘
```

---

## Bot Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Register and see welcome message | Just send /start |
| `/help` | View all available commands | Just send /help |
| `/setpincode` | Set delivery location | Sends prompt, enter 6-digit code |
| `/products` | Browse products, toggle subscriptions | Click buttons to subscribe |
| `/mystatus` | View current subscriptions | Shows pincode + tracked products |
| `/instock` | Check what's available now | Shows stock with quantities |
| `/stop` | Unsubscribe from everything | Requires confirmation |

---

## Notification Types

1. **Back in Stock** - Product reappeared after being sold out
2. **Stock Increased** - More units added to inventory
3. **Low Stock Warning** - Only 5 or fewer units left
4. **Sold Out** - Product no longer available

---

## Customization Options

### Change Stock Check Interval
Edit `config.py`:
```python
STOCK_CHECK_INTERVAL = 5  # Change to minutes you want
```

### Change Low Stock Threshold
Edit `scheduler/stock_monitor.py`:
```python
LOW_STOCK_THRESHOLD = 5  # Change threshold
```

### Add More Product Categories
Currently tracks "protein" products. To add more:
Edit `scraper/amul_api.py` and add more category URLs.

---

## Troubleshooting

### Bot not responding?
- Check if `BOT_TOKEN` is set correctly
- Verify bot is running (check logs)
- Ensure you messaged the correct bot

### Pincode not working?
- Amul may not deliver to that area
- Try a different pincode

### No notifications?
- Check `/mystatus` to verify subscriptions
- Products may already be out of stock
- Wait for next stock check cycle (5 mins)

### Rate limited by Amul?
- Increase `STOCK_CHECK_INTERVAL` in config
- The bot already has 2-second delays between requests

---

## Cost Summary

| Component | Cost |
|-----------|------|
| Telegram Bot API | FREE |
| Python | FREE |
| SQLite Database | FREE |
| All Libraries | FREE (Open Source) |
| Hosting (Railway/Render/etc) | FREE Tier |
| **TOTAL** | **$0.00** |

---

## Next Steps Checklist

- [ ] Create Telegram bot with BotFather
- [ ] Copy BOT_TOKEN to `.env` file
- [ ] Run `pip install -r requirements.txt`
- [ ] Test locally with `python main.py`
- [ ] Test all commands in Telegram
- [ ] Choose hosting option and deploy
- [ ] Share bot with friends/family!

---

## Files Reference

```
Amul Bot/
├── main.py              # Start here - entry point
├── config.py            # Configuration settings
├── requirements.txt     # Dependencies
├── .env                 # Your BOT_TOKEN (create this)
├── bot/
│   └── handlers.py      # All Telegram commands
├── database/
│   └── db.py            # SQLite operations
├── scraper/
│   └── amul_api.py      # Amul website integration
└── scheduler/
    └── stock_monitor.py # Background monitoring
```

---

**You're ready to go! The code is complete. Just configure and deploy.**
