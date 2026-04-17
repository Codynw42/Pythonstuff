#!/usr/bin/env python3
"""
UFC Upcoming Fights Scraper
============================
Scrapes upcoming UFC events and fight cards from multiple sources,
then saves all info to a formatted text file: ufc_upcoming_fights.txt

Sources tried (in order):
  1. Tapology (tapology.com/fightcenter)
  2. ESPN MMA (espn.com/mma/schedule/_/league/ufc)
  3. Sherdog (sherdog.com/events/UFC)

Requirements:
  pip install requests beautifulsoup4 lxml

Usage:
  python ufc_scraper.py
"""

# /// script
# dependencies = [
#   "requests",
#   "beautifulsoup4",
#   "lxml",
# ]
# ///








import requests
from bs4 import BeautifulSoup
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_FILE = "ufc_upcoming_fights.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

class Fight:
    def __init__(self, fighter1, fighter2, card_type="Main Card",
                 weight_class="", is_title=False, bout_order=None):
        self.fighter1 = fighter1.strip()
        self.fighter2 = fighter2.strip()
        self.card_type = card_type.strip()
        self.weight_class = weight_class.strip()
        self.is_title = is_title
        self.bout_order = bout_order  # e.g. "Main Event", "Co-Main Event"

    def __repr__(self):
        return f"Fight({self.fighter1} vs {self.fighter2})"


class UFCEvent:
    def __init__(self, name, date_str, time_str="", timezone="ET",
                 venue="", location="", url=""):
        self.name = name.strip()
        self.date_str = date_str.strip()
        self.time_str = time_str.strip()
        self.timezone = timezone.strip()
        self.venue = venue.strip()
        self.location = location.strip()
        self.url = url.strip()
        self.fights: list[Fight] = []  # list of Fight objects

    def __repr__(self):
        return f"UFCEvent({self.name}, {self.date_str})"


# ---------------------------------------------------------------------------
# Source 1: Tapology
# ---------------------------------------------------------------------------

def scrape_tapology() -> list[UFCEvent]:
    """
    Scrapes upcoming UFC events from tapology.com/fightcenter.
    Returns a list of UFCEvent objects (with fights populated where possible).
    """
    print("  → Trying Tapology...")
    events = []

    try:
        url = "https://www.tapology.com/fightcenter"
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Each event is in a section with class "promotion" or similar
        # Tapology groups events by date; we look for UFC-labeled event blocks
        event_sections = soup.select("div.promotion_events, section.promotion_events, ul.eventListings > li")

        if not event_sections:
            # Try alternative selectors
            event_sections = soup.select("li[id*='event'], div[id*='event']")

        # Tapology's fightcenter page has a list of events
        # Let's find all links that look like UFC events
        all_links = soup.find_all("a", href=re.compile(r"/fightcenter/events/"))

        seen_hrefs = set()
        ufc_links = []
        for a in all_links:
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href not in seen_hrefs and ("ufc" in text.lower() or "ufc" in href.lower()):
                seen_hrefs.add(href)
                ufc_links.append((text, "https://www.tapology.com" + href))

        print(f"     Found {len(ufc_links)} UFC event link(s) on Tapology listing page.")

        # For each UFC event link, scrape the event detail page
        for event_name, event_url in ufc_links[:10]:  # limit to 10 upcoming events
            ev = scrape_tapology_event(event_name, event_url)
            if ev:
                events.append(ev)

    except Exception as e:
        print(f"     Tapology listing error: {e}")

    return events


def scrape_tapology_event(event_name: str, url: str) -> UFCEvent | None:
    """Scrapes a single Tapology event page for fight card details."""
    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # --- Event meta ---
        date_str = ""
        time_str = ""
        timezone = "ET"
        venue = ""
        location = ""

        # Date is often in a <span> or <li> with class containing 'date'
        date_el = soup.select_one("span.datetime, li.datetime, div.datetime, [class*='date']")
        if date_el:
            date_str = date_el.get_text(strip=True)

        # More targeted: look for structured detail list items
        detail_items = soup.select("ul.details > li, div.details > span, div.eventDetails > li")
        for item in detail_items:
            text = item.get_text(" ", strip=True)
            if re.search(r"\d{4}", text) and not date_str:
                date_str = text
            if re.search(r"\d{1,2}:\d{2}", text) and not time_str:
                time_str = text

        # Try the page's <title> or header for the event name
        h1 = soup.select_one("h1, h2")
        if h1:
            event_name = h1.get_text(strip=True) or event_name

        # Venue / location
        venue_el = soup.select_one("[class*='venue'], [class*='location'], [itemprop='location']")
        if venue_el:
            venue = venue_el.get_text(strip=True)

        event = UFCEvent(
            name=event_name,
            date_str=date_str,
            time_str=time_str,
            timezone=timezone,
            venue=venue,
            location=location,
            url=url,
        )

        # --- Fight card ---
        # Tapology organizes fights in sections by card type
        card_sections = soup.select("section.bout_card, div.bout_card, div[class*='card']")

        if not card_sections:
            # Fallback: look for any fight rows
            fight_rows = soup.select("li.bout, div.bout, tr.bout")
            parse_tapology_fights_flat(fight_rows, event)
        else:
            for section in card_sections:
                card_label_el = section.select_one("h2, h3, .card_label, .card-label")
                card_label = card_label_el.get_text(strip=True) if card_label_el else "Card"
                fight_rows = section.select("li.bout, div.bout, tr.bout, li[class*='bout']")
                for i, row in enumerate(fight_rows):
                    fight = parse_tapology_fight_row(row, card_label, i)
                    if fight:
                        event.fights.append(fight)

        print(f"     ✓ {event.name}: {len(event.fights)} fight(s)")
        return event

    except Exception as e:
        print(f"     Error scraping event {url}: {e}")
        return None


def parse_tapology_fights_flat(rows, event: UFCEvent):
    for i, row in enumerate(rows):
        fight = parse_tapology_fight_row(row, "Card", i)
        if fight:
            event.fights.append(fight)


def parse_tapology_fight_row(row, card_label: str, index: int) -> Fight | None:
    try:
        # Fighter names are typically in spans/divs with class 'name' or 'fighter'
        fighters = row.select("[class*='name'], [class*='fighter'], span.fName")
        if len(fighters) >= 2:
            f1 = fighters[0].get_text(strip=True)
            f2 = fighters[1].get_text(strip=True)
        else:
            # Try splitting on "vs" or "vs."
            text = row.get_text(" ", strip=True)
            vs_match = re.split(r"\bvs\.?\b", text, flags=re.IGNORECASE)
            if len(vs_match) >= 2:
                f1 = vs_match[0].strip().split()[-2] + " " + vs_match[0].strip().split()[-1] if len(vs_match[0].split()) >= 2 else vs_match[0].strip()
                f2 = vs_match[1].strip().split()[0] + " " + vs_match[1].strip().split()[1] if len(vs_match[1].split()) >= 2 else vs_match[1].strip()
            else:
                return None

        if not f1 or not f2 or f1 == f2:
            return None

        # Weight class
        wc_el = row.select_one("[class*='weight'], [class*='class']")
        weight_class = wc_el.get_text(strip=True) if wc_el else ""

        # Title bout?
        is_title = bool(row.select_one("[class*='title'], [class*='belt']")) or \
                   "title" in row.get_text().lower() or "championship" in row.get_text().lower()

        # Bout order
        bout_order = None
        if index == 0:
            bout_order = "Main Event"
        elif index == 1:
            bout_order = "Co-Main Event"

        return Fight(f1, f2, card_label, weight_class, is_title, bout_order)

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Source 2: ESPN MMA Schedule
# ---------------------------------------------------------------------------

def scrape_espn() -> list[UFCEvent]:
    """
    Scrapes upcoming UFC events from ESPN's MMA schedule page.
    """
    print("  → Trying ESPN MMA schedule...")
    events = []

    try:
        url = "https://www.espn.com/mma/schedule/_/league/ufc"
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # ESPN renders some data server-side; look for schedule tables
        tables = soup.select("table.schedule, table[class*='Table']")
        if not tables:
            tables = soup.select("table")

        for table in tables:
            rows = table.select("tr")
            current_date = ""
            for row in rows:
                cells = row.select("td, th")
                if not cells:
                    continue
                text_cells = [c.get_text(strip=True) for c in cells]
                full_text = " | ".join(text_cells)

                # Date header rows
                if len(cells) == 1 and re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", full_text):
                    current_date = full_text
                    continue

                # Event row: should have a UFC link or "UFC" in text
                if "ufc" in full_text.lower():
                    event_link = row.select_one("a[href*='mma/fightcenter'], a[href*='/fight/']")
                    event_name = text_cells[0] if text_cells else "UFC Event"
                    time_str = ""
                    for cell_text in text_cells:
                        if re.search(r"\d{1,2}:\d{2}", cell_text):
                            time_str = cell_text
                            break

                    ev = UFCEvent(
                        name=event_name,
                        date_str=current_date,
                        time_str=time_str,
                        timezone="ET",
                        url=event_link["href"] if event_link else "",
                    )
                    events.append(ev)

        print(f"     Found {len(events)} event(s) via ESPN.")

    except Exception as e:
        print(f"     ESPN error: {e}")

    return events


# ---------------------------------------------------------------------------
# Source 3: Sherdog events page
# ---------------------------------------------------------------------------

def scrape_sherdog() -> list[UFCEvent]:
    """
    Scrapes upcoming UFC events from sherdog.com.
    """
    print("  → Trying Sherdog...")
    events = []

    try:
        url = "https://www.sherdog.com/organizations/Ultimate-Fighting-Championship-2"
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Sherdog has an "Upcoming Events" table
        upcoming_section = soup.find("section", id="upcoming_events") or \
                           soup.find("div", id="upcoming_events")

        if not upcoming_section:
            # Try to find any table with upcoming fights
            upcoming_section = soup.find("div", string=re.compile(r"Upcoming", re.I))
            if upcoming_section:
                upcoming_section = upcoming_section.find_parent("section") or upcoming_section.find_parent("div")

        if not upcoming_section:
            print("     Could not find upcoming events section on Sherdog.")
            return events

        rows = upcoming_section.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            name_cell = cells[0].get_text(strip=True)
            date_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            location_cell = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            if not name_cell or "ufc" not in name_cell.lower():
                continue

            event_link_el = cells[0].select_one("a[href]")
            event_url = "https://www.sherdog.com" + event_link_el["href"] if event_link_el else ""

            ev = UFCEvent(
                name=name_cell,
                date_str=date_cell,
                location=location_cell,
                url=event_url,
            )

            # Optionally scrape individual event page for fight card
            if event_url:
                populate_sherdog_event(ev)

            events.append(ev)

        print(f"     Found {len(events)} event(s) via Sherdog.")

    except Exception as e:
        print(f"     Sherdog error: {e}")

    return events


def populate_sherdog_event(event: UFCEvent):
    """Scrapes a Sherdog event page for fight card details."""
    try:
        resp = SESSION.get(event.url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Date / venue / location
        date_el = soup.select_one("span.date, .date_location .date")
        venue_el = soup.select_one("span.venue, .date_location .venue")
        location_el = soup.select_one("span.location, .date_location .location")

        if date_el and not event.date_str:
            event.date_str = date_el.get_text(strip=True)
        if venue_el and not event.venue:
            event.venue = venue_el.get_text(strip=True)
        if location_el and not event.location:
            event.location = location_el.get_text(strip=True)

        # Fight card sections: main card, prelims, early prelims
        # Sherdog uses tables for this
        fight_tables = soup.select("div.fight_card table, section.fight_card table, table.fight_card")
        if not fight_tables:
            fight_tables = soup.select("table")

        card_labels = ["Main Card", "Preliminary Card", "Early Preliminary Card"]

        for table_idx, table in enumerate(fight_tables):
            # Determine card label from heading near the table
            prev_heading = table.find_previous(["h2", "h3", "h4"])
            if prev_heading:
                ph_text = prev_heading.get_text(strip=True)
                if "early" in ph_text.lower() or "early prelim" in ph_text.lower():
                    card_label = "Early Prelims"
                elif "prelim" in ph_text.lower():
                    card_label = "Prelims"
                elif "main" in ph_text.lower():
                    card_label = "Main Card"
                else:
                    card_label = card_labels[table_idx] if table_idx < len(card_labels) else "Card"
            else:
                card_label = card_labels[table_idx] if table_idx < len(card_labels) else "Card"

            rows = table.select("tr.fight")
            if not rows:
                rows = table.select("tr")[1:]  # skip header

            for i, row in enumerate(rows):
                cells = row.select("td")
                if len(cells) < 2:
                    continue

                # Fighter names
                fighter_els = row.select("td.fighter_result_data, td[class*='fighter']")
                if len(fighter_els) >= 2:
                    f1 = fighter_els[0].get_text(strip=True)
                    f2 = fighter_els[1].get_text(strip=True)
                else:
                    text = row.get_text(" ", strip=True)
                    vs_parts = re.split(r"\bvs\.?\b", text, flags=re.IGNORECASE)
                    if len(vs_parts) >= 2:
                        f1 = vs_parts[0].strip()
                        f2 = vs_parts[1].strip()
                    else:
                        continue

                if not f1 or not f2:
                    continue

                # Weight class
                wc_el = row.select_one("td[class*='weight'], td[class*='class']")
                weight_class = wc_el.get_text(strip=True) if wc_el else ""

                is_title = "title" in row.get_text().lower() or "championship" in row.get_text().lower()

                bout_order = None
                if i == 0 and card_label in ("Main Card", "UFC Main Card"):
                    bout_order = "Main Event"
                elif i == 1 and card_label in ("Main Card", "UFC Main Card"):
                    bout_order = "Co-Main Event"

                fight = Fight(f1, f2, card_label, weight_class, is_title, bout_order)
                event.fights.append(fight)

    except Exception as e:
        print(f"     Error scraping Sherdog event {event.url}: {e}")


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_events(all_events: list[UFCEvent]) -> list[UFCEvent]:
    """Merges duplicate events across sources (matched by similar name)."""
    seen = {}
    merged = []

    for ev in all_events:
        # Normalize name for comparison
        key = re.sub(r"[^a-z0-9]", "", ev.name.lower())

        if key in seen:
            existing = seen[key]
            # Merge: prefer whichever has more data
            if not existing.date_str and ev.date_str:
                existing.date_str = ev.date_str
            if not existing.time_str and ev.time_str:
                existing.time_str = ev.time_str
            if not existing.venue and ev.venue:
                existing.venue = ev.venue
            if not existing.location and ev.location:
                existing.location = ev.location
            if not existing.fights and ev.fights:
                existing.fights = ev.fights
        else:
            seen[key] = ev
            merged.append(ev)

    return merged


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_output(events: list[UFCEvent]) -> str:
    lines = []
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    lines.append("=" * 70)
    lines.append("                 UFC UPCOMING FIGHTS")
    lines.append(f"            Generated: {now}")
    lines.append("=" * 70)

    if not events:
        lines.append("")
        lines.append("  No upcoming UFC events found.")
        lines.append("  Try running the script again or check your internet connection.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"  Total Events Found: {len(events)}")
    lines.append("=" * 70)

    for ev_num, ev in enumerate(events, 1):
        lines.append("")
        lines.append(f"  EVENT #{ev_num}")
        lines.append(f"  {'─' * 66}")
        lines.append(f"  Name     : {ev.name}")

        if ev.date_str:
            lines.append(f"  Date     : {ev.date_str}")
        if ev.time_str:
            tz = f" {ev.timezone}" if ev.timezone else ""
            lines.append(f"  Time     : {ev.time_str}{tz}")
        if ev.venue:
            lines.append(f"  Venue    : {ev.venue}")
        if ev.location:
            lines.append(f"  Location : {ev.location}")
        if ev.url:
            lines.append(f"  More Info: {ev.url}")

        if ev.fights:
            lines.append("")
            lines.append(f"  FIGHT CARD ({len(ev.fights)} bout(s)):")
            lines.append(f"  {'─' * 66}")

            # Group by card type
            from collections import defaultdict
            card_groups = defaultdict(list)
            card_order = []
            for fight in ev.fights:
                if fight.card_type not in card_order:
                    card_order.append(fight.card_type)
                card_groups[fight.card_type].append(fight)

            preferred_order = ["Main Card", "Prelims", "Preliminary Card",
                               "Early Prelims", "Early Preliminary Card"]
            sorted_cards = sorted(
                card_order,
                key=lambda x: preferred_order.index(x) if x in preferred_order else 99
            )

            for card_label in sorted_cards:
                fights = card_groups[card_label]
                lines.append("")
                lines.append(f"  ┌─ {card_label.upper()} {'─' * max(0, 55 - len(card_label))}┐")

                for fight in fights:
                    bout_tag = ""
                    if fight.bout_order:
                        bout_tag = f"  [{fight.bout_order}]"

                    title_tag = " ★ TITLE BOUT" if fight.is_title else ""
                    wc_tag = f"  ({fight.weight_class})" if fight.weight_class else ""

                    lines.append(f"  │  {fight.fighter1}")
                    lines.append(f"  │      vs.")
                    lines.append(f"  │  {fight.fighter2}")

                    meta = f"{bout_tag}{wc_tag}{title_tag}".strip()
                    if meta:
                        lines.append(f"  │  {meta}")

                    lines.append(f"  │")

                lines.append(f"  └{'─' * 68}┘")

        else:
            lines.append("")
            lines.append("  Fight card details not yet available.")

        lines.append("")
        lines.append("  " + "═" * 66)

    lines.append("")
    lines.append("  Data sourced from: Tapology, ESPN MMA, Sherdog")
    lines.append("  Always verify times at ufc.com or your local listings.")
    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  UFC Upcoming Fights Scraper")
    print("=" * 60)
    print("\nScraping sources...")

    all_events: list[UFCEvent] = []

    # --- Source 1: Tapology ---
    tapology_events = scrape_tapology()
    all_events.extend(tapology_events)

    # --- Source 2: ESPN (if Tapology got nothing) ---
    if not all_events:
        espn_events = scrape_espn()
        all_events.extend(espn_events)

    # --- Source 3: Sherdog (if still nothing) ---
    if not all_events:
        sherdog_events = scrape_sherdog()
        all_events.extend(sherdog_events)

    # Deduplicate
    events = deduplicate_events(all_events)
    events_with_fights = [e for e in events if e.fights]
    events_without = [e for e in events if not e.fights]

    # Sort by event name (puts numbered UFC events in rough order)
    events.sort(key=lambda e: e.name.lower())

    print(f"\n  ✓ Total unique events: {len(events)}")
    print(f"  ✓ Events with fight card details: {len(events_with_fights)}")
    if events_without:
        print(f"  ⚠ Events without card details yet: {len(events_without)}")

    # Format and write output
    output = format_output(events)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\n  ✓ Saved to: {OUTPUT_FILE}")
    print("=" * 60 + "\n")

    # Preview the first few lines
    preview_lines = output.split("\n")[:20]
    print("  --- Preview ---")
    for line in preview_lines:
        print(line)
    print("  ...")
    print(f"\n  Open '{OUTPUT_FILE}' to see the full results.\n")


if __name__ == "__main__":
    main()
