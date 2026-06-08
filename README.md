# Daily Trade Analysis Report — Automated via GitHub Actions

Sends a comprehensive daily email with **Gold**, **Silver**, and **Indian Equity Swing Trade** analysis every weekday at 7:00 AM IST — fully automated, zero maintenance.

## Setup (3 steps, 5 minutes)

### Step 1: Create a Gmail App Password
1. Go to https://myaccount.google.com/apppasswords
2. Sign in → Select "Mail" → "Other" → name it `TradeReport` → Generate
3. Copy the 16-character password

### Step 2: Add GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 4 secrets:

| Secret Name     | Value                          |
|-----------------|--------------------------------|
| `SENDER_EMAIL`  | `sanatsarin8@gmail.com`        |
| `APP_PASSWORD`  | your 16-char app password      |
| `TO_EMAILS`     | `advaynath007@gmail.com`       |
| `CC_EMAILS`     | `sanatsarin8@gmail.com`        |

### Step 3: Enable Actions
Go to **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**

**Done!** The report will send automatically every weekday at 7 AM IST.

## Manual Trigger
Actions tab → "Daily Trade Report" → "Run workflow" → "Run workflow"

## What's in the Report
- Gold & Silver: price, RSI, SMA-10/20, trend, support/resistance, buy/sell/wait verdict
- 9 Indian stocks: ICICI Bank, SBI, HDFC Bank, L&T, REC, Reliance, Tata Motors, Bharti Airtel, Infosys
- Each with RSI, moving averages, volume analysis, and swing trade action signals
