import requests
from datetime import datetime, timedelta
import pytz
import json

# Free ForexFactory JSON calendar endpoint
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Currencies we care about (matching our asset list)
RELEVANT_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU"}

# IMPACT LEVELS (Aggressive Filter includes Medium)
IMPACT_LEVELS = {"High", "high", "Medium", "medium", "Holiday"}

# Minutes to block before and after a high-impact event (Aggressive: 60 min)
BLOCK_BEFORE_MINUTES = 60
BLOCK_AFTER_MINUTES  = 60

class NewsFeedService:
    def __init__(self):
        self._cache = []
        self._cache_time = None
        self._cache_ttl_minutes = 60  # Refresh every 60 minutes

    def _fetch_events(self):
        """Fetches this week's economic calendar from ForexFactory."""
        try:
            resp = requests.get(FF_CALENDAR_URL, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"⚠️ [NEWS] Could not fetch economic calendar: {e}")
        return []

    def get_events(self, force_refresh=False):
        """Returns the current week's high-impact events, cached for 60 min."""
        now = datetime.now()
        if self._cache_time is None or (now - self._cache_time).seconds > self._cache_ttl_minutes * 60 or force_refresh:
            raw = self._fetch_events()
            # Filter for IMPACT and relevant currencies
            self._cache = [
                e for e in raw
                if e.get("impact") in IMPACT_LEVELS and e.get("currency") in RELEVANT_CURRENCIES
            ]
            self._cache_time = now
            print(f"📰 [NEWS] Calendar refreshed: {len(self._cache)} high-impact events this week.")
        return self._cache

    def is_news_blackout(self, symbol=None):
        """
        Returns (True, event_title) if we are within the blackout window of a high-impact event.
        Returns (False, None) if it's safe to trade.
        """
        events = self.get_events()
        now_utc = datetime.now(pytz.utc)

        # Determine which currencies this symbol involves
        relevant = set(RELEVANT_CURRENCIES)
        if symbol:
            symbol_upper = symbol.upper()
            # Extract base/quote currency from symbol if possible (e.g. EURUSD -> EUR, USD)
            relevant = {cur for cur in RELEVANT_CURRENCIES if cur in symbol_upper}
            if not relevant:
                relevant = RELEVANT_CURRENCIES  # fallback: check all

        for event in events:
            if event.get("currency") not in relevant:
                continue

            # Parse event date
            event_time_str = event.get("date")
            if not event_time_str:
                continue
            try:
                # ForexFactory format: "2025-03-17T12:30:00-04:00"
                event_time = datetime.fromisoformat(event_time_str).astimezone(pytz.utc)
            except Exception:
                continue

            block_start = event_time - timedelta(minutes=BLOCK_BEFORE_MINUTES)
            block_end   = event_time + timedelta(minutes=BLOCK_AFTER_MINUTES)

            if block_start <= now_utc <= block_end:
                title = event.get("title", "High Impact Event")
                print(f"🚨 [NEWS BLACKOUT] {title} ({event.get('currency')}) – Trading blocked!")
                return True, title

        return False, None

    def get_upcoming_events(self, hours_ahead=24):
        """Returns upcoming high-impact events in the next N hours for display on dashboard."""
        events = self.get_events()
        now_utc = datetime.now(pytz.utc)
        cutoff = now_utc + timedelta(hours=hours_ahead)
        upcoming = []
        for event in events:
            event_time_str = event.get("date")
            if not event_time_str:
                continue
            try:
                event_time = datetime.fromisoformat(event_time_str).astimezone(pytz.utc)
            except Exception:
                continue
            if now_utc <= event_time <= cutoff:
                # Convert to local readable
                local_time = event_time.astimezone(pytz.timezone("America/New_York"))
                upcoming.append({
                    "title": event.get("title", "Event"),
                    "currency": event.get("currency"),
                    "impact": event.get("impact"),
                    "time_ny": local_time.strftime("%Y-%m-%d %H:%M NY"),
                    "forecast": event.get("forecast", ""),
                    "previous": event.get("previous", "")
                })
        return upcoming
