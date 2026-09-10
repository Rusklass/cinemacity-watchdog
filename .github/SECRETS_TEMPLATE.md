# GitHub Secrets & Variables Configuration Template

This document lists the secrets and variables you can configure in your GitHub repository to enable mobile notifications and seat filtering.

---

## Where to add them in GitHub

1. Open your repository on GitHub.
2. Go to **Settings** (top navigation bar of your repo).
3. In the left sidebar, click **Secrets and variables** → **Actions**.
4. Click the green button **"New repository secret"** (or **"New repository variable"**).

---

## 📱 Mobile Notification Secrets

| Secret Name | Required? | Example Value | Description |
|---|---|---|---|
| `NTFY_TOPIC` | Optional | `dune-imax-watchdog-abc123xyz` | **Recommended:** Topic name for the free [ntfy.sh](https://ntfy.sh) mobile app. Sends instant push notifications with sound directly to your phone. |
| `TELEGRAM_BOT_TOKEN` | Optional | `7123456789:AAFn...` | Bot token obtained from [@BotFather](https://t.me/BotFather) on Telegram. |
| `TELEGRAM_CHAT_ID` | Optional | `123456789, 987654321` | Numeric Telegram user or chat ID(s). **Supports multiple IDs separated by commas or spaces** to notify multiple people at once! |

> [!TIP]
> You do **not** need to configure both. Setting just `NTFY_TOPIC` is the easiest and fastest way to get mobile push alerts without creating bots or signing up for accounts.

---

## 🎯 Seat Availability & Filter Variables

You can set these under **Repository Variables** (or Secrets) if you wish to customize them beyond their defaults:

| Variable Name | Default | Description |
|---|---|---|
| `MIN_AVAILABILITY_RATIO` | `0.50` | Only triggers alerts when **more than 50% of the seats are free** (`0.50` = 50%, `0.80` = 80%). This filters out already crowded or almost sold-out shows and ensures you only get alerted when prime rows (like rows 7–10) are still open! |
| `FILM_PATTERN` | `dun` | Matches the Czech title *„Duna: část třetí“* and English *„Dune“*. |
| `AUDITORIUM_PATTERN` | `imax` | Filters for `IMAX VOLVO` at Praha Flora. Set to empty string `""` to monitor all auditoriums. |

---

## Quick Setup Steps

### 1. Fast Mobile Push via `ntfy.sh` (No account needed)
1. Download **ntfy** from the iOS App Store or Google Play.
2. Tap `+` and choose a unique, hard-to-guess topic name (e.g. `dune-watchdog-unity-8921`).
3. In GitHub, add `NTFY_TOPIC` as a Repository Secret with that exact topic name.

### 2. Fast Mobile Push via Telegram
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and follow prompts to get the token.
2. Message [@userinfobot](https://t.me/userinfobot) on Telegram to get your user ID. Have any other person who wants alerts do the same.
3. In GitHub, add:
   - `TELEGRAM_BOT_TOKEN`: your bot token
   - `TELEGRAM_CHAT_ID`: your chat ID (or multiple IDs separated by commas, e.g. `123456789, 987654321`)
4. **Important:** Every person must send `/start` to your newly created bot in Telegram so the bot has permission to message them.
