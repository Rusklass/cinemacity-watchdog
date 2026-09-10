# cinemacity-watchdog

Monitors [Cinema City](https://www.cinemacity.cz) schedule and automatically alerts you when new screenings of **Dune in IMAX** (December 2026) are scheduled.

Notifications can be delivered to your phone via:
- **GitHub Mobile** push notifications & email
- **[ntfy.sh](https://ntfy.sh)** instant loud push alerts (no registration required)
- **Telegram Bot** chat messages

Runs automatically 24/7 on GitHub Actions, requiring no local server or running computer.

---

## How It Works

- **GitHub Actions Cron:** The workflow [`.github/workflows/watch.yml`](.github/workflows/watch.yml) runs every ~30 minutes (at :08, :38, :21, :51 past the hour). Since public repositories receive unlimited GitHub Actions minutes, it runs completely free.
- **Public API:** [`watch.py`](watch.py) queries Cinema City's public JSON API (`/cz/data-api-service/v1/quickbook/10101/…`) without requiring any login or API keys.
- **State Management:** Seen screenings are tracked in [`state/seen.json`](state/seen.json), which the workflow commits back to the repository after each run. Only new additions or cancellations trigger alerts.
- **Delivery via GitHub Issues:** When new screenings appear, GitHub Actions creates an issue assigned directly to you, immediately firing email and phone push notifications via the GitHub Mobile app. The issue is closed immediately afterward to keep your open issues list clean.
- **Direct Mobile Push:** Optionally delivers instant notifications with direct ticket purchase links to **ntfy** or **Telegram**.
- **Accurate Timezones:** Screenings are evaluated in cinema local time (`Europe/Prague`), avoiding false alerts due to UTC runner offsets.

Each run executes ~45 fast HTTP queries in ~20 seconds.

---

## What It Monitors

By default, it tracks screenings where:
- **Film title** contains `dun` (matches both Czech *„Duna: část třetí“* and English *„Dune“*).
- **Auditorium** contains `imax` (targeting **Praha Flora — IMAX VOLVO**).
- **Free seats** ratio is **≥ 50%** (`MIN_AVAILABILITY_RATIO=0.50`), ensuring you are only alerted when prime rows (rows 7–10) are still available!

### Configuration Options

You can customize the watchdog by setting environment variables or GitHub Secrets/Variables:

| Variable | Default | Description |
|---|---|---|
| `FILM_PATTERN` | `dun` | Film name substring (`dun` or `dune`, case-insensitive) |
| `AUDITORIUM_PATTERN` | `imax` | Auditorium name substring (or empty `""` for all auditoriums) |
| `MIN_AVAILABILITY_RATIO` | `0.50` | Only report screenings with **at least 50% free seats** (guarantees prime rows are open) |
| `HORIZON_DAYS` | `180` | Days ahead to search (180 days easily covers December 2026) |
| `HINT_ATTR` | `70-mm` | Attribute used to pre-filter candidate cinemas cheaply |
| `REQUEST_DELAY` | `0.25` | Delay between API requests (seconds) |
| `NTFY_TOPIC` | *(empty)* | Topic name for instant push notifications via [ntfy.sh](https://ntfy.sh) |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Telegram Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | *(empty)* | Telegram user or group chat ID |

---

## Setting Up Your Own Watchdog (GitHub Fork)

The watchdog requires no third-party hosting:

1. **Fork** this repository to your GitHub account.
2. **Enable Issues:** Go to **Settings → General → Features → check `Issues`**. *(Forks have issues disabled by default; without this, notifications cannot be created).*
3. **Enable Actions:** Go to the **Actions** tab and click **"I understand my workflows, go ahead and enable them"**.
4. Done! The workflow uses `${{ github.repository_owner }}` to assign notifications directly to you.

To verify immediately, run the workflow manually:
- Go to **Actions → Cinema City watchdog → Run workflow** (optionally check `force_report`).

---

## 📱 Mobile Phone Notifications

Choose whichever method you prefer:

### 1. GitHub Mobile App (Default, No Extra Setup)
- Install the official **GitHub** app on iOS or Android and log in.
- Because issues are assigned to your account, GitHub sends a **push notification straight to your lock screen** and an email.

### 2. ntfy.sh (Instant Loud Push, No Account Needed — Recommended)
- Install the free **ntfy** app (iOS / Android).
- Tap `+` and subscribe to any unique topic name (e.g. `dune-imax-watchdog-unique123`).
- In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
  - Name: `NTFY_TOPIC`
  - Value: `dune-imax-watchdog-unique123`
- You will receive instant notifications with direct links to book seats.

### 3. Telegram Bot
- Create a bot with [@BotFather](https://t.me/BotFather) on Telegram to get your `TELEGRAM_BOT_TOKEN`.
- Get your user ID from [@userinfobot](https://t.me/userinfobot) (`TELEGRAM_CHAT_ID`). Supports **multiple IDs** separated by commas (e.g. `123456789, 987654321`) to notify multiple people at once.
- Add both as GitHub Secrets (`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`).

For step-by-step guidance, see [`.github/SECRETS_TEMPLATE.md`](.github/SECRETS_TEMPLATE.md).

---

## Local Execution

Runs on pure Python 3 with **zero third-party dependencies**:

### Windows (PowerShell)
```powershell
# Standard check (reports only new screenings vs state/seen.json)
python watch.py --state state/seen.json

# Report all matching screenings regardless of state
python watch.py --force-report

# Search all auditoriums (not just IMAX):
$env:AUDITORIUM_PATTERN = ""
python watch.py --force-report

# Test phone alert locally via ntfy:
$env:NTFY_TOPIC = "your-topic-name"
$env:MIN_AVAILABILITY_RATIO = "0.01"
python watch.py --force-report
```

### Linux / macOS (Bash)
```bash
python3 watch.py --state state/seen.json
python3 watch.py --force-report
```

Useful CLI options:
- `--force-report`: outputs all matching screenings regardless of state.
- `--seed`: saves current schedule state to JSON file without sending notifications.

---

## Maintenance

- **Actions quota:** Public repositories have unlimited Actions minutes for free.
- **60-day pause prevention:** GitHub automatically pauses scheduled cron workflows if a repository has no commits for 60 days. This watchdog commits state changes back to the repository, keeping it active.
- **After the movie run:** Disable the workflow (**Actions → Disable workflow**) or update `FILM_PATTERN` to monitor another upcoming release.
