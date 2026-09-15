"""
Reddit Session Warmer
Uses Playwright (or Camoufox if available) to warm up a real browser session on Reddit,
saves session cookies and User-Agent headers to disk, and populates python requests.Session
to bypass 403 anti-bot blocks on Reddit's JSON API endpoints.

Author: Faheem Alvi
License: CC BY-NC 4.0
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

import requests

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SESSION_FILE_PATH = os.path.join(PROJECT_ROOT, "reddit_session.json")
MAX_SESSION_AGE_HOURS = 12


class RedditSessionWarmer:
    """
    Manages Reddit browser session warming, cookie persistence,
    and HTTP requests.Session initialization.
    """

    def __init__(self, session_path: str = SESSION_FILE_PATH):
        self.session_path = session_path
        self._cached_session_data: Optional[Dict[str, Any]] = None

    def get_session_info(self) -> Dict[str, Any]:
        """Check current saved session status and return diagnostic info."""
        if not os.path.exists(self.session_path):
            return {"exists": False, "valid": False, "reason": "No session file found"}

        try:
            with open(self.session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            warmed_at_str = data.get("warmed_at", "")
            cookies = data.get("cookies", [])
            user_agent = data.get("user_agent", "")

            if not warmed_at_str or not cookies:
                return {"exists": True, "valid": False, "reason": "Invalid or empty session data"}

            warmed_at = datetime.fromisoformat(warmed_at_str)
            age_seconds = (datetime.now(timezone.utc) - warmed_at).total_seconds()
            age_hours = age_seconds / 3600.0

            is_valid = age_hours < MAX_SESSION_AGE_HOURS

            return {
                "exists": True,
                "valid": is_valid,
                "warmed_at": warmed_at_str,
                "age_hours": round(age_hours, 2),
                "cookie_count": len(cookies),
                "user_agent": user_agent[:60] + "..." if len(user_agent) > 60 else user_agent,
                "reason": "Valid session" if is_valid else f"Expired ({age_hours:.1f}h old)",
            }
        except Exception as e:
            return {"exists": True, "valid": False, "reason": f"Error reading session file: {e}"}

    def warmup_session(self, force_refresh: bool = False, headless: bool = True) -> Tuple[bool, str]:
        """
        Launch Playwright (or Camoufox), navigate to Reddit, verify connection,
        and save cookies + User-Agent to disk.
        Returns (success, message).
        """
        # Check if current session is already valid and force_refresh is False
        if not force_refresh:
            info = self.get_session_info()
            if info.get("valid"):
                return True, f"Using existing valid session (warmed {info.get('age_hours')}h ago)"

        print("[RedditSessionWarmer] Warming up Reddit browser session...")

        # Try Playwright sync_api
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "Playwright python package is not installed. Run: pip install playwright"

        try:
            with sync_playwright() as p:
                print("[RedditSessionWarmer] Launching headless browser...")
                browser = None
                # Try Chromium first, fallback to Firefox
                try:
                    browser = p.chromium.launch(headless=headless)
                except Exception as ex1:
                    print(f"[RedditSessionWarmer] Chromium launch failed ({ex1}), trying Firefox...")
                    try:
                        browser = p.firefox.launch(headless=headless)
                    except Exception as ex2:
                        return False, f"Could not launch browser. Try running: playwright install. Error: {ex2}"

                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                )

                page = context.new_page()

                print("[RedditSessionWarmer] Navigating to https://www.reddit.com...")
                response = page.goto("https://www.reddit.com/", wait_until="domcontentloaded", timeout=25000)

                status_code = response.status if response else 0
                title = page.title()
                print(f"[RedditSessionWarmer] Page loaded (Status: {status_code}, Title: '{title[:40]}')")

                if status_code in (403, 429):
                    browser.close()
                    return False, f"Reddit blocked browser navigation with status {status_code}"

                # Short sleep to allow session cookie initialization
                time.sleep(2.5)

                cookies = context.cookies("https://www.reddit.com")
                user_agent = page.evaluate("navigator.userAgent")

                browser.close()

                if not cookies:
                    return False, "No cookies obtained from Reddit page visit"

                session_data = {
                    "warmed_at": datetime.now(timezone.utc).isoformat(),
                    "user_agent": user_agent,
                    "cookies": cookies,
                }

                with open(self.session_path, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, indent=2)

                self._cached_session_data = session_data
                print(f"[RedditSessionWarmer] ✓ Session saved to {self.session_path} with {len(cookies)} cookies.")
                return True, f"Session warmed successfully ({len(cookies)} cookies saved)"

        except Exception as e:
            print(f"[RedditSessionWarmer] ✗ Warmup failed: {e}")
            return False, f"Session warmup exception: {str(e)}"

    def get_requests_session(self, force_refresh: bool = False) -> Tuple[requests.Session, bool]:
        """
        Return a requests.Session pre-configured with cookies and custom headers.
        Returns (session_object, is_warmed).
        """
        info = self.get_session_info()
        if not info.get("valid") or force_refresh:
            success, msg = self.warmup_session(force_refresh=force_refresh)
            if not success:
                print(f"[RedditSessionWarmer] Warning: {msg}. Falling back to default session.")

        session = requests.Session()

        if os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                user_agent = data.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                cookies_list = data.get("cookies", [])

                for c in cookies_list:
                    name = c.get("name")
                    value = c.get("value")
                    domain = c.get("domain", ".reddit.com")
                    path = c.get("path", "/")
                    if name and value:
                        session.cookies.set(name, value, domain=domain, path=path)

                session.headers.update({
                    "User-Agent": user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.reddit.com/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                })
                return session, True
            except Exception as e:
                print(f"[RedditSessionWarmer] Error loading saved cookies onto requests session: {e}")

        # Fallback standard session
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        })
        return session, False

    def invalidate_session(self):
        """Remove saved session file."""
        if os.path.exists(self.session_path):
            try:
                os.remove(self.session_path)
                print("[RedditSessionWarmer] Invalidated saved session file.")
            except Exception as e:
                print(f"[RedditSessionWarmer] Could not delete session file: {e}")


# Singleton instance helper
_default_warmer = RedditSessionWarmer()

def get_session_warmer() -> RedditSessionWarmer:
    return _default_warmer
