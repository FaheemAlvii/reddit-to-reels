"""
Reddit Browser Scraper (Fallback & Non-.json Method)
Fetches Reddit posts and comments directly via headless Playwright browser,
without calling or depending on Reddit's .json API endpoints.
Bypasses 403 Forbidden and 429 Too Many Requests blocks on JSON endpoints.

Author: Faheem Alvi
License: CC BY-NC 4.0
"""

import sys
import os
import time
import asyncio
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def _run_in_isolated_thread(fn, *args, **kwargs):
    """
    Ensure fn(*args, **kwargs) runs in a thread free of active asyncio event loops,
    with WindowsProactorEventLoopPolicy set on Windows.
    Prevents Playwright Sync API "inside the asyncio loop" and NotImplementedError.
    """
    def _runner():
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass
        return fn(*args, **kwargs)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_runner)
            return future.result()
    return _runner()


def _clean_post_url(post_url: str) -> str:
    """Normalize and clean a post URL or ID for browser navigation."""
    url = post_url.strip()
    # Strip any .json or /.json extension
    url = url.replace("/.json", "").replace(".json", "")
    url = url.rstrip("/")
    
    # If it's a bare post ID (e.g., '1xw5l3f')
    if not url.startswith("http://") and not url.startswith("https://"):
        if url.startswith("r/"):
            url = f"https://www.reddit.com/{url}"
        elif url.startswith("comments/"):
            url = f"https://www.reddit.com/{url}"
        else:
            url = f"https://www.reddit.com/comments/{url}"
    return url


class RedditBrowserScraper:
    """
    Browser-based scraper using Playwright to extract Reddit posts and comments
    directly from rendered HTML / web components without hitting .json endpoints.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    def _launch_browser(self, p: Any):
        """Launch browser, attempting Chromium first with stealth args, then Firefox."""
        try:
            return p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                ignore_default_args=["--enable-automation"]
            )
        except Exception as ex1:
            print(f"[BrowserScraper] Chromium launch failed ({ex1}), trying Firefox...")
            return p.firefox.launch(headless=self.headless)

    def scrape_subreddit(
        self,
        subreddit: str = "AskReddit",
        sort: str = "hot",
        limit: int = 25
    ) -> List[Dict]:
        """
        Scrape post summaries from a subreddit without touching .json endpoints.
        Returns list of post data dictionaries compatible with RedditStoryMaker.
        """
        return _run_in_isolated_thread(self._scrape_subreddit_impl, subreddit, sort, limit)

    def _scrape_subreddit_impl(
        self,
        subreddit: str = "AskReddit",
        sort: str = "hot",
        limit: int = 25
    ) -> List[Dict]:
        from playwright.sync_api import sync_playwright

        clean_sub = subreddit.strip().replace("r/", "").replace("/", "")
        valid_sorts = ["best", "hot", "new", "rising", "top"]
        if sort not in valid_sorts:
            sort = "hot"

        url = f"https://www.reddit.com/r/{clean_sub}/{sort}/"
        if sort == "top":
            url += "?t=week"

        print(f"[BrowserScraper] Navigating to {url} (non-.json)...")
        posts: List[Dict] = []

        try:
            with sync_playwright() as p:
                browser = self._launch_browser(p)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="en-US"
                )
                page = context.new_page()
                try:
                    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                except Exception:
                    pass

                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    status = response.status if response else 0
                    print(f"[BrowserScraper] Subreddit page loaded (Status: {status})")
                except Exception as net_err:
                    print(f"[BrowserScraper] Navigation warning: {net_err}")

                page.wait_for_timeout(2500)

                # If more than 25 posts are requested, scroll to load additional items
                if limit > 25:
                    scroll_passes = min(6, (limit // 20))
                    for _ in range(scroll_passes):
                        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1200)

                raw_posts = page.evaluate('''() => {
                    const items = [];
                    // Modern Reddit web components
                    const elements = document.querySelectorAll('shreddit-post');
                    if (elements.length > 0) {
                        for (const el of elements) {
                            const idAttr = el.getAttribute('id') || '';
                            const id = idAttr.replace(/^t3_/, '');
                            const title = el.getAttribute('post-title') || el.innerText?.split('\\n')[0] || '';
                            const author = el.getAttribute('author') || '';
                            const scoreStr = el.getAttribute('score') || '0';
                            const commentsStr = el.getAttribute('comment-count') || '0';
                            const permalink = el.getAttribute('permalink') || '';
                            const createdStr = el.getAttribute('created-timestamp') || '';
                            const subPrefixed = el.getAttribute('subreddit-prefixed-name') || '';
                            const nsfw = el.hasAttribute('nsfw') || el.getAttribute('over-18') === 'true';
                            const bodyEl = el.querySelector('[slot="text-body"]');
                            let selftext = bodyEl ? bodyEl.innerText.trim() : '';
                            if (selftext.endsWith('Read more')) {
                                selftext = selftext.substring(0, selftext.length - 9).trim();
                            }

                            if (id && title) {
                                items.push({
                                    id,
                                    title,
                                    author,
                                    score: parseInt(scoreStr, 10) || 0,
                                    num_comments: parseInt(commentsStr, 10) || 0,
                                    permalink,
                                    created_timestamp: createdStr,
                                    subreddit: subPrefixed.replace(/^r\\//, ''),
                                    over_18: nsfw,
                                    selftext
                                });
                            }
                        }
                    } else {
                        // Fallback for classic / old Reddit DOM elements
                        const things = document.querySelectorAll('div.thing.link');
                        for (const el of things) {
                            const idAttr = el.getAttribute('data-fullname') || el.getAttribute('id') || '';
                            const id = idAttr.replace(/^t3_/, '');
                            const titleEl = el.querySelector('a.title');
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            const author = el.getAttribute('data-author') || '';
                            const scoreStr = el.getAttribute('data-score') || '0';
                            const commentsStr = el.getAttribute('data-comments-count') || '0';
                            const permalink = el.getAttribute('data-permalink') || '';
                            const timeEl = el.querySelector('time');
                            const createdStr = timeEl ? (timeEl.getAttribute('datetime') || '') : '';
                            const subreddit = el.getAttribute('data-subreddit') || '';
                            const nsfw = el.classList.contains('over18');

                            if (id && title) {
                                items.push({
                                    id,
                                    title,
                                    author,
                                    score: parseInt(scoreStr, 10) || 0,
                                    num_comments: parseInt(commentsStr, 10) || 0,
                                    permalink,
                                    created_timestamp: createdStr,
                                    subreddit,
                                    over_18: nsfw,
                                    selftext: ''
                                });
                            }
                        }
                    }
                    return items;
                }''')

                browser.close()

                for item in raw_posts[:limit]:
                    created_utc = 0
                    if item.get("created_timestamp"):
                        try:
                            dt = datetime.fromisoformat(item["created_timestamp"].replace("Z", "+00:00"))
                            created_utc = dt.timestamp()
                        except Exception:
                            created_utc = datetime.now(timezone.utc).timestamp()
                    else:
                        created_utc = datetime.now(timezone.utc).timestamp()

                    permalink = item.get("permalink", "")
                    if permalink and not permalink.startswith("/"):
                        permalink = "/" + permalink

                    posts.append({
                        "id": item["id"],
                        "title": item["title"],
                        "author": item["author"] or "Anonymous",
                        "subreddit": item["subreddit"] or clean_sub,
                        "score": item["score"],
                        "upvote_ratio": 1.0,
                        "num_comments": item["num_comments"],
                        "created_utc": created_utc,
                        "url": f"https://www.reddit.com{permalink}" if permalink else "",
                        "permalink": permalink,
                        "selftext": item.get("selftext", ""),
                        "over_18": item.get("over_18", False),
                        "is_video": False,
                    })

            print(f"[BrowserScraper] ✓ Extracted {len(posts)} posts from r/{clean_sub}")
            return posts

        except Exception as e:
            print(f"[BrowserScraper] ✗ Error scraping subreddit r/{clean_sub}: {e}")
            return []

    def scrape_post_details(self, post_url: str) -> Optional[List]:
        """
        Scrape detailed post data including comments from a post page
        without touching .json endpoints.
        Returns [post_listing, comments_listing] compatible with Reddit API JSON format.
        """
        return _run_in_isolated_thread(self._scrape_post_details_impl, post_url)

    def _scrape_post_details_impl(self, post_url: str) -> Optional[List]:
        from playwright.sync_api import sync_playwright

        clean_url = _clean_post_url(post_url)
        print(f"[BrowserScraper] Navigating to post: {clean_url} (non-.json)...")

        try:
            with sync_playwright() as p:
                browser = self._launch_browser(p)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="en-US"
                )
                page = context.new_page()
                try:
                    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                except Exception:
                    pass

                try:
                    response = page.goto(clean_url, wait_until="domcontentloaded", timeout=25000)
                    status = response.status if response else 0
                    print(f"[BrowserScraper] Post page loaded (Status: {status})")
                except Exception as net_err:
                    print(f"[BrowserScraper] Navigation warning: {net_err}")

                page.wait_for_timeout(3000)

                # Scroll slightly to trigger comment loading if needed
                page.evaluate("window.scrollBy(0, 400)")
                page.wait_for_timeout(1000)

                data = page.evaluate('''() => {
                    // Try modern Reddit shreddit-post
                    const postEl = document.querySelector('shreddit-post');
                    let post = null;

                    if (postEl) {
                        const idAttr = postEl.getAttribute('id') || '';
                        const id = idAttr.replace(/^t3_/, '');
                        const title = postEl.getAttribute('post-title') || document.querySelector('h1')?.innerText?.trim() || '';
                        const author = postEl.getAttribute('author') || '';
                        const score = parseInt(postEl.getAttribute('score') || '0', 10);
                        const num_comments = parseInt(postEl.getAttribute('comment-count') || '0', 10);
                        const permalink = postEl.getAttribute('permalink') || window.location.pathname;
                        const createdStr = postEl.getAttribute('created-timestamp') || '';
                        const subPrefixed = postEl.getAttribute('subreddit-prefixed-name') || '';
                        const nsfw = postEl.hasAttribute('nsfw') || postEl.getAttribute('over-18') === 'true';

                        const bodyEl = postEl.querySelector('[slot="text-body"]');
                        let selftext = bodyEl ? bodyEl.innerText.trim() : '';
                        if (selftext.endsWith('Read more')) {
                            selftext = selftext.substring(0, selftext.length - 9).trim();
                        }

                        post = {
                            id,
                            title,
                            author,
                            score,
                            num_comments,
                            permalink,
                            created_timestamp: createdStr,
                            subreddit: subPrefixed.replace(/^r\\//, ''),
                            over_18: nsfw,
                            selftext
                        };
                    } else {
                        // Classic Reddit fallback
                        const thing = document.querySelector('div.thing.link');
                        if (thing) {
                            const idAttr = thing.getAttribute('data-fullname') || thing.getAttribute('id') || '';
                            const id = idAttr.replace(/^t3_/, '');
                            const titleEl = thing.querySelector('a.title') || document.querySelector('h1');
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            const author = thing.getAttribute('data-author') || '';
                            const score = parseInt(thing.getAttribute('data-score') || '0', 10);
                            const num_comments = parseInt(thing.getAttribute('data-comments-count') || '0', 10);
                            const permalink = thing.getAttribute('data-permalink') || window.location.pathname;
                            const timeEl = thing.querySelector('time');
                            const createdStr = timeEl ? (timeEl.getAttribute('datetime') || '') : '';
                            const subreddit = thing.getAttribute('data-subreddit') || '';
                            const nsfw = thing.classList.contains('over18');
                            const bodyEl = thing.querySelector('div.usertext-body');
                            const selftext = bodyEl ? bodyEl.innerText.trim() : '';

                            post = {
                                id,
                                title,
                                author,
                                score,
                                num_comments,
                                permalink,
                                created_timestamp: createdStr,
                                subreddit,
                                over_18: nsfw,
                                selftext
                            };
                        }
                    }

                    // Extract comments
                    const comments = [];
                    const commentEls = document.querySelectorAll('shreddit-comment');
                    if (commentEls.length > 0) {
                        for (const c of commentEls) {
                            const depth = parseInt(c.getAttribute('depth') || '0', 10);
                            const cAuthor = c.getAttribute('author') || '[deleted]';
                            const cScore = parseInt(c.getAttribute('score') || '0', 10);
                            const thingid = (c.getAttribute('thingid') || '').replace(/^t1_/, '');
                            const cTime = c.getAttribute('created-timestamp') || '';
                            const cBodyEl = c.querySelector('[slot="comment"]');
                            const cBody = cBodyEl ? cBodyEl.innerText.trim() : '';

                            if (cBody && cAuthor !== '[deleted]') {
                                comments.push({
                                    id: thingid,
                                    author: cAuthor,
                                    score: cScore,
                                    body: cBody,
                                    depth: depth,
                                    created_timestamp: cTime
                                });
                            }
                        }
                    } else {
                        // Classic comments fallback
                        const classicComments = document.querySelectorAll('div.thing.comment');
                        for (const c of classicComments) {
                            const thingid = (c.getAttribute('data-fullname') || '').replace(/^t1_/, '');
                            const cAuthor = c.getAttribute('data-author') || '[deleted]';
                            const cScore = parseInt(c.querySelector('span.score.unvoted')?.innerText || '0', 10);
                            const cBodyEl = c.querySelector('div.usertext-body');
                            const cBody = cBodyEl ? cBodyEl.innerText.trim() : '';

                            if (cBody && cAuthor !== '[deleted]') {
                                comments.push({
                                    id: thingid,
                                    author: cAuthor,
                                    score: cScore,
                                    body: cBody,
                                    depth: 0,
                                    created_timestamp: ''
                                });
                            }
                        }
                    }

                    return { post, comments };
                }''')

                browser.close()

                if not data or not data.get("post"):
                    print("[BrowserScraper] ✗ Failed to extract post content from page")
                    return None

                post_raw = data["post"]
                created_utc = 0
                if post_raw.get("created_timestamp"):
                    try:
                        dt = datetime.fromisoformat(post_raw["created_timestamp"].replace("Z", "+00:00"))
                        created_utc = dt.timestamp()
                    except Exception:
                        created_utc = datetime.now(timezone.utc).timestamp()
                else:
                    created_utc = datetime.now(timezone.utc).timestamp()

                permalink = post_raw.get("permalink", "")
                if permalink and not permalink.startswith("/"):
                    permalink = "/" + permalink

                post_data = {
                    "id": post_raw["id"],
                    "title": post_raw["title"],
                    "author": post_raw["author"] or "Anonymous",
                    "subreddit": post_raw["subreddit"] or "AskReddit",
                    "score": post_raw["score"],
                    "upvote_ratio": 1.0,
                    "num_comments": post_raw["num_comments"],
                    "created_utc": created_utc,
                    "url": f"https://www.reddit.com{permalink}" if permalink else clean_url,
                    "permalink": permalink,
                    "selftext": post_raw.get("selftext", ""),
                    "over_18": post_raw.get("over_18", False),
                    "is_video": False,
                }

                # Construct standard Reddit API 2-element listing structure
                post_listing = {
                    "kind": "Listing",
                    "data": {
                        "children": [
                            {
                                "kind": "t3",
                                "data": post_data
                            }
                        ]
                    }
                }

                comment_children = []
                for c in data.get("comments", []):
                    c_utc = 0
                    if c.get("created_timestamp"):
                        try:
                            dt = datetime.fromisoformat(c["created_timestamp"].replace("Z", "+00:00"))
                            c_utc = dt.timestamp()
                        except Exception:
                            c_utc = datetime.now(timezone.utc).timestamp()

                    comment_children.append({
                        "kind": "t1",
                        "data": {
                            "id": c.get("id", ""),
                            "author": c.get("author", "Anonymous"),
                            "score": c.get("score", 0),
                            "body": c.get("body", ""),
                            "created_utc": c_utc,
                            "depth": c.get("depth", 0),
                            "replies": ""
                        }
                    })

                comments_listing = {
                    "kind": "Listing",
                    "data": {
                        "children": comment_children
                    }
                }

                print(f"[BrowserScraper] ✓ Extracted post '{post_data['title'][:50]}...' with {len(comment_children)} comments")
                return [post_listing, comments_listing]

        except Exception as e:
            print(f"[BrowserScraper] ✗ Error scraping post details for {clean_url}: {e}")
            return None


_default_browser_scraper = RedditBrowserScraper()

def get_browser_scraper() -> RedditBrowserScraper:
    return _default_browser_scraper

def scrape_subreddit_posts(subreddit: str = "AskReddit", sort: str = "hot", limit: int = 25) -> List[Dict]:
    return get_browser_scraper().scrape_subreddit(subreddit=subreddit, sort=sort, limit=limit)

def scrape_post_details(post_url: str) -> Optional[List]:
    return get_browser_scraper().scrape_post_details(post_url=post_url)
