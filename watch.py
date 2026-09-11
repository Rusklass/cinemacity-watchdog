#!/usr/bin/env python3
"""Monitors Cinema City schedule and reports newly announced screenings.

Default configuration: film matching "dun" (Dune / Duna) in "IMAX" auditorium.
Fetches data from the public Cinema City JSON API (no API key or login required).

Maintains state (already seen screenings) in a JSON file to only report
new additions since the last run.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SITE_ID = "10101"  # cinemacity.cz
BASE = f"https://www.cinemacity.cz/cz/data-api-service/v1/quickbook/{SITE_ID}"
LANG = "cs_CZ"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

FILM_PATTERN = os.environ.get("FILM_PATTERN", "dun").lower()
AUDITORIUM_PATTERN = os.environ.get("AUDITORIUM_PATTERN", "imax").lower()
HORIZON_DAYS = int(os.environ.get("HORIZON_DAYS", "180"))
# Attribute used by API to pre-filter cinemas — helps discover IMAX auditoriums cheaply
HINT_ATTR = os.environ.get("HINT_ATTR", "70-mm")
DELAY = float(os.environ.get("REQUEST_DELAY", "0.25"))
# Minimum ratio of free seats required to trigger alert (0.45 = at least 45% seats free)
MIN_AVAILABILITY_RATIO = float(os.environ.get("MIN_AVAILABILITY_RATIO", "0.45"))

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# The API returns eventDateTime in cinema's local time without timezone info.
# GitHub Actions runner runs in UTC, so we must evaluate in Prague timezone.
CINEMA_TZ = ZoneInfo("Europe/Prague")


def now():
    """Current time in cinema timezone, without tzinfo — comparable with API timestamps."""
    return datetime.now(CINEMA_TZ).replace(tzinfo=None)


def api(path):
    """GET request to data-api-service; returns content of the 'body' key."""
    url = f"{BASE}{path}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))["body"]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise SystemExit(f"API failed after 4 attempts: {url}\n{last}")


def horizon():
    return (date.today() + timedelta(days=HORIZON_DAYS)).isoformat()


def fetch_cinemas():
    body = api(f"/cinemas/with-event/until/{horizon()}?attr=&lang={LANG}")
    return {c["id"]: c for c in body["cinemas"]}


def fetch_dates(cinema_id):
    time.sleep(DELAY)
    return api(f"/dates/in-cinema/{cinema_id}/until/{horizon()}?attr=&lang={LANG}")["dates"]


def fetch_day(cinema_id, day):
    time.sleep(DELAY)
    body = api(f"/film-events/in-cinema/{cinema_id}/at-date/{day}?attr=&lang={LANG}")
    films = {f["id"]: f for f in body.get("films", [])}
    return films, body.get("events", [])


def hint_cinema_ids():
    """Cinemas that have events with HINT_ATTR according to the API."""
    if not HINT_ATTR:
        return set()
    body = api(f"/cinemas/with-event/until/{horizon()}?attr={HINT_ATTR}&lang={LANG}")
    return {c["id"] for c in body["cinemas"]}


def matches_film(film_name):
    if not film_name:
        return False
    name = film_name.lower()
    patterns = [p.strip() for p in FILM_PATTERN.split(",") if p.strip()]
    for pat in patterns:
        if pat in name:
            return True
        # cinemacity.cz lists the movie in Czech ("Duna" instead of "Dune")
        if pat == "dune" and "duna" in name:
            return True
    return False


def is_target_hall(event):
    return AUDITORIUM_PATTERN in (event.get("auditorium") or "").lower()


def collect():
    """Scans relevant cinemas and returns {event_id: record} for target screenings.

    To avoid downloading full schedules for all cinemas, it runs in two phases:
    first checks which cinemas have the target auditorium, then scans those in depth.
    """
    cinemas = fetch_cinemas()
    dates_by_cinema = {cid: fetch_dates(cid) for cid in cinemas}

    candidates = hint_cinema_ids() & set(cinemas)
    day_cache = {}
    for cid, days in dates_by_cinema.items():
        if not days:
            continue
        probe = days[0]
        day_cache[(cid, probe)] = fetch_day(cid, probe)
        if any(is_target_hall(e) for e in day_cache[(cid, probe)][1]):
            candidates.add(cid)

    found = {}
    for cid in sorted(candidates):
        for day in dates_by_cinema.get(cid, []):
            films, events = day_cache.get((cid, day)) or fetch_day(cid, day)
            for e in events:
                film = films.get(e["filmId"], {})
                if not matches_film(film.get("name", "")):
                    continue
                if not is_target_hall(e):
                    continue
                found[e["id"]] = {
                    "id": e["id"],
                    "film": film.get("name", e["filmId"]),
                    "filmLink": film.get("link"),
                    "cinema": cinemas[cid]["displayName"],
                    "cinemaId": cid,
                    "datetime": e["eventDateTime"],
                    "auditorium": e.get("auditorium"),
                    "attrs": e.get("attributeIds", []),
                    # The bookingRouterLaunchLink leads to a self-submitting POST form
                    # that redirects to /order/{id}, which opens the seat selection directly.
                    "booking": f"https://tickets.cinemacity.cz/order/{e.get('presentationCode') or e['id']}",
                    "soldOut": bool(e.get("soldOut")),
                    "availabilityRatio": e.get("availabilityRatio"),
                }
    return found


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"updated": None, "events": {}}


def save_state(path, events):
    """Writes state to file, but only when the set of event IDs has changed.

    Prevents creating empty commits if only the 'updated' timestamp would change.
    """
    if set(events) == set(load_state(path).get("events", {})):
        return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "updated": now().replace(microsecond=0).isoformat(),
        "events": dict(sorted(events.items(), key=lambda kv: kv[1]["datetime"])),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    return True


def prune_past(events):
    """Removes past screenings from state so the file does not grow indefinitely."""
    cutoff = (now() - timedelta(days=1)).isoformat()
    return {k: v for k, v in events.items() if v["datetime"] >= cutoff}


def fmt_dt(iso):
    dt = datetime.fromisoformat(iso)
    return f"{DAYS[dt.weekday()]} {dt.day}. {dt.month}. {dt.year} at {dt:%H:%M}"


def fmt_short(iso):
    dt = datetime.fromisoformat(iso)
    return f"{dt.day}. {dt.month}."


def render(new_events, gone_events):
    """Markdown report body."""
    lines = []
    if new_events:
        lines.append(f"### Newly Scheduled ({len(new_events)})\n")
        for cinema, group in group_by_cinema(new_events):
            lines.append(f"**{cinema}**\n")
            for e in group:
                flags = []
                if "70-mm" in e["attrs"]:
                    flags.append("70mm")
                if "subbed" in e["attrs"]:
                    flags.append("subtitles")
                if "dubbed" in e["attrs"]:
                    flags.append("dubbed")
                if e["soldOut"]:
                    flags.append("**sold out**")
                elif e.get("availabilityRatio") is not None:
                    flags.append(f"{round(e['availabilityRatio'] * 100)}% free")
                suffix = f" — {', '.join(flags)}" if flags else ""
                link = f" — [buy tickets]({e['booking']})" if e["booking"] else ""
                lines.append(f"- {fmt_dt(e['datetime'])} · {e['auditorium']}{suffix}{link}")
            lines.append("")
    if gone_events:
        lines.append(f"### Removed from Schedule ({len(gone_events)})\n")
        for cinema, group in group_by_cinema(gone_events):
            lines.append(f"**{cinema}**\n")
            for e in group:
                lines.append(f"- {fmt_dt(e['datetime'])} · {e['auditorium']}")
            lines.append("")
    film_link = next(
        (e["filmLink"] for e in list(new_events) + list(gone_events) if e.get("filmLink")),
        None,
    )
    if film_link:
        lines.append(f"[Cinema City Movie Page]({film_link})")
    lines.append("")
    lines.append(
        f"<sub>Checked {now():%Y-%m-%d %H:%M} · "
        f"film ~ `{FILM_PATTERN}` · auditorium ~ `{AUDITORIUM_PATTERN}` · "
        f"free seats ≥ {int(MIN_AVAILABILITY_RATIO * 100)}%</sub>"
    )
    return "\n".join(lines)


def group_by_cinema(events):
    order = {}
    for e in sorted(events, key=lambda x: (x["cinema"], x["datetime"])):
        order.setdefault(e["cinema"], []).append(e)
    return order.items()


def title_for(new_events):
    film = new_events[0]["film"]
    days = sorted({e["datetime"][:10] for e in new_events})
    span = fmt_short(days[0])
    if len(days) > 1:
        span += f"–{fmt_short(days[-1])}"
    n = len(new_events)
    word = "new screening" if n == 1 else "new screenings"
    hall_str = (
        " in IMAX"
        if AUDITORIUM_PATTERN == "imax"
        else (f" ({AUDITORIUM_PATTERN.upper()})" if AUDITORIUM_PATTERN else "")
    )
    return f"🎬 {film}{hall_str}: {n} {word} ({span})"


def send_ntfy(title, body):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=body.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Tags": "movie_camera,ticket",
                "Priority": "high",
                "User-Agent": UA,
            },
        )
        with urllib.request.urlopen(req, timeout=10):
            print(f"Push notification sent to ntfy.sh/{topic}")
    except Exception as exc:
        print(f"Failed to send ntfy notification: {exc}", file=sys.stderr)


def send_telegram(title, body):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    raw_chat_ids = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not raw_chat_ids:
        return
    # Supports multiple chat IDs separated by commas, semicolons, or spaces
    chat_ids = [c.strip() for c in re.split(r"[,;\s]+", raw_chat_ids) if c.strip()]
    if not chat_ids:
        return

    msg = f"*{title}*\n\n{body}"
    for chat_id in chat_ids:
        try:
            payload = json.dumps({
                "chat_id": chat_id,
                "text": msg,
                "disable_web_page_preview": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": UA},
            )
            with urllib.request.urlopen(req, timeout=10):
                print(f"Telegram notification sent to {chat_id}.")
        except Exception as exc:
            print(f"Failed to send Telegram notification to {chat_id}: {exc}", file=sys.stderr)


def gh_output(**kwargs):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in kwargs.items():
            fh.write(f"{key}={value}\n")


def passes_availability(e):
    if e["soldOut"]:
        return False
    ratio = e.get("availabilityRatio")
    if ratio is not None and ratio < MIN_AVAILABILITY_RATIO:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="state/seen.json", help="path to state file")
    ap.add_argument("--seed", action="store_true", help="save current state without reporting")
    ap.add_argument("--force-report", action="store_true", help="report all matching screenings regardless of state")
    ap.add_argument("--test-notification", action="store_true", help="send initial/startup test notification to verify Telegram and ntfy")
    ap.add_argument("--report", default="report.md", help="file to write markdown report to")
    ap.add_argument("--title", default="title.txt", help="file to write issue title to")
    args = ap.parse_args()

    if args.test_notification:
        test_title = "🎬 Cinema City Watchdog: Active"
        test_body = (
            "✅ Watchdog is running and notifications are working!\n\n"
            f"• Film: `{FILM_PATTERN}`\n"
            f"• Hall: `{AUDITORIUM_PATTERN}`\n"
            f"• Min free seats: `{int(MIN_AVAILABILITY_RATIO * 100)}%`\n\n"
            "Monitoring Cinema City schedule 24/7."
        )
        print(f"\n{test_title}\n{test_body}\n")
        send_ntfy(test_title, test_body)
        send_telegram(test_title, test_body)

    current = collect()
    state = load_state(args.state)
    known = state.get("events", {})

    print(f"Found {len(current)} matching screenings, {len(known)} in state.")

    if args.seed:
        save_state(args.state, prune_past(current))
        print(f"State saved to {args.state} (seed, nothing reported).")
        gh_output(has_news="false")
        return

    if args.force_report:
        new_events = sorted(
            (v for v in current.values() if passes_availability(v)),
            key=lambda e: e["datetime"],
        )
        gone = []
    else:
        new_events = sorted(
            (v for k, v in current.items() if k not in known and passes_availability(v)),
            key=lambda e: e["datetime"],
        )
        future = now().isoformat()
        gone = sorted(
            (v for k, v in known.items() if k not in current and v["datetime"] > future),
            key=lambda e: e["datetime"],
        )

    # Only persist events that were already known, or newly passed availability,
    # so events below the threshold aren't permanently swallowed if availability improves.
    events_to_save = {
        k: v for k, v in current.items()
        if k in known or passes_availability(v)
    }
    save_state(args.state, prune_past(events_to_save))

    if not new_events and not gone:
        print("No new updates.")
        gh_output(has_news="false")
        return

    body = render(new_events, gone)
    if new_events:
        title = title_for(new_events)
    elif gone:
        film = gone[0]["film"]
        hall_str = (
            " in IMAX"
            if AUDITORIUM_PATTERN == "imax"
            else (f" ({AUDITORIUM_PATTERN.upper()})" if AUDITORIUM_PATTERN else "")
        )
        title = f"🎬 {film}{hall_str}: cancelled screenings"
    else:
        title = "🎬 Cinema City: schedule update"
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(body + "\n")
    with open(args.title, "w", encoding="utf-8") as fh:
        fh.write(title + "\n")

    print(f"\n{title}\n")
    print(body)
    send_ntfy(title, body)
    send_telegram(title, body)
    gh_output(has_news="true")


if __name__ == "__main__":
    sys.exit(main())
