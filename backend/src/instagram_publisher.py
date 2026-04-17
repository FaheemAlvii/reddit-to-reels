"""
Instagram Graph API Publisher - Publish Reels to Instagram Business/Creator accounts.

WARNING: NOT END TO END TESTED
This publisher is implemented based on Instagram Graph API docs but has not been
verified with a live account by the author. Expect to debug auth, permission, or
upload issues. Pull requests with fixes are welcome.

Requires:
  - Facebook App with instagram_basic + instagram_content_publish permissions
  - Instagram Business or Creator account linked to a Facebook Page
  - Long-lived access token (60-day, auto-refreshable)
  - Videos accessible via public URL during upload

Author: Faheem Alvi <faheemalvi2000@gmail.com>
GitHub: https://github.com/FaheemAlvii
"""

import os
import re
import time
import json
import random
import logging
import requests
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
from typing import Optional, Tuple, List

logger = logging.getLogger("instagram_publisher")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# Pre-looked-up Facebook location page ID for "United States"
USA_LOCATION_ID = "110264868983528"

FIXED_HASHTAGS = [
    "#redditstories", "#reddit", "#explore", "#trending",
    "#fyp", "#viral", "#storytime",
]

RANDOM_HASHTAG_POOL = [
    "#askreddit", "#relatable", "#drama", "#crazystory",
    "#truestory", "#redditstory", "#storiesofreddit",
    "#redditreadings", "#reddittiktok", "#redditthread",
    "#relationship", "#aita", "#tifu", "#confession",
    "#unbelievable", "#mindblown", "#realstory",
]


class _SilentHandler(SimpleHTTPRequestHandler):
    """HTTP handler that suppresses request logs."""

    def log_message(self, format, *args):
        pass


class TemporaryFileServer:
    """Spin up a throwaway HTTP server to make a local file publicly accessible."""

    def __init__(self, directory: str, port: int = 9123):
        self.directory = directory
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        handler = partial(_SilentHandler, directory=self.directory)
        self._server = HTTPServer(("0.0.0.0", self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Temporary file server started on port {self.port}")

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("Temporary file server stopped")

    def get_url(self, filename: str, public_host: str) -> str:
        """Return the public URL for a file served by this server."""
        return f"http://{public_host}:{self.port}/{filename}"


class InstagramPublisher:
    """Publish Reels to Instagram via the Graph API."""

    def __init__(self, user_id: str, access_token: str,
                 app_id: str = "", app_secret: str = "",
                 public_host: str = "",
                 file_server_port: int = 9123):
        self.user_id = user_id
        self.access_token = access_token
        self.app_id = app_id
        self.app_secret = app_secret
        self.public_host = public_host
        self.file_server_port = file_server_port

    # ──────────────────── Caption Builder ────────────────────

    @staticmethod
    def build_caption(title: str, part_num: int = 1, total_parts: int = 1,
                      extra_fixed_hashtags: List[str] | None = None) -> str:
        """
        Build an Instagram caption.

        Format:
            Part {n}: {title}
            .
            .
            .
            {hashtags}
        """
        if total_parts > 1:
            header = f"Part {part_num}: {title}"
        else:
            header = title

        hashtags = list(FIXED_HASHTAGS)
        if extra_fixed_hashtags:
            hashtags.extend(extra_fixed_hashtags)

        # Pick 3-5 random extras (no duplicates with fixed)
        pool = [h for h in RANDOM_HASHTAG_POOL if h not in hashtags]
        num_random = min(random.randint(3, 5), len(pool))
        hashtags.extend(random.sample(pool, num_random))

        hashtag_str = " ".join(hashtags)

        return f"{header}\n.\n.\n.\n{hashtag_str}"

    # ──────────────────── Publishing Flow ────────────────────

    def publish_reel(self, video_path: str, caption: str,
                     thumbnail_path: Optional[str] = None,
                     location_id: str = USA_LOCATION_ID,
                     public_video_url: Optional[str] = None,
                     public_thumbnail_url: Optional[str] = None) -> Optional[str]:
        """
        Publish a single Reel to Instagram.

        If public_video_url is not provided, a temporary file server is spun up
        to serve the video (requires public_host to be set and the port to be
        accessible from the internet — use with a VPS/cloud server or ngrok).

        Returns the published media ID or None on failure.
        """
        file_server: Optional[TemporaryFileServer] = None

        try:
            # ── Resolve video URL ──
            if not public_video_url:
                if not self.public_host:
                    logger.error("No public_video_url and no public_host configured. Cannot upload.")
                    return None
                serve_dir = os.path.dirname(video_path)
                file_server = TemporaryFileServer(serve_dir, self.file_server_port)
                file_server.start()
                video_filename = os.path.basename(video_path)
                public_video_url = file_server.get_url(video_filename, self.public_host)

                if thumbnail_path and not public_thumbnail_url:
                    # Copy thumbnail next to video if in different dir
                    thumb_filename = os.path.basename(thumbnail_path)
                    public_thumbnail_url = file_server.get_url(thumb_filename, self.public_host)

            # ── Step 1: Create media container ──
            container_id = self._create_container(
                video_url=public_video_url,
                caption=caption,
                cover_url=public_thumbnail_url,
                location_id=location_id,
            )
            if not container_id:
                return None

            # ── Step 2: Poll until processing finishes ──
            if not self._wait_for_processing(container_id, timeout=300):
                return None

            # ── Step 3: Publish ──
            media_id = self._publish_container(container_id)
            return media_id

        except Exception as e:
            logger.error(f"Failed to publish reel: {e}")
            return None

        finally:
            if file_server:
                # Keep server alive a bit for Instagram to finish downloading
                time.sleep(10)
                file_server.stop()

    def _create_container(self, video_url: str, caption: str,
                          cover_url: Optional[str] = None,
                          location_id: Optional[str] = None) -> Optional[str]:
        """POST /{user_id}/media to create a Reels container."""
        url = f"{GRAPH_API_BASE}/{self.user_id}/media"
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": self.access_token,
        }
        if cover_url:
            params["cover_url"] = cover_url
        if location_id:
            params["location_id"] = location_id

        resp = requests.post(url, data=params, timeout=60)
        data = resp.json()

        if "id" in data:
            container_id = data["id"]
            logger.info(f"Created media container: {container_id}")
            return container_id
        else:
            logger.error(f"Failed to create container: {data}")
            return None

    def _wait_for_processing(self, container_id: str, timeout: int = 300) -> bool:
        """Poll container status until FINISHED or timeout."""
        url = f"{GRAPH_API_BASE}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token,
        }
        deadline = time.time() + timeout
        poll_interval = 5

        while time.time() < deadline:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            status = data.get("status_code", "UNKNOWN")
            logger.debug(f"Container {container_id} status: {status}")

            if status == "FINISHED":
                logger.info(f"Container {container_id} processing finished")
                return True
            elif status == "ERROR":
                logger.error(f"Container processing error: {data.get('status', 'unknown')}")
                return False
            elif status == "EXPIRED":
                logger.error("Container expired before publishing")
                return False

            time.sleep(poll_interval)
            # Gradually increase poll interval
            poll_interval = min(poll_interval + 2, 30)

        logger.error(f"Container {container_id} processing timed out after {timeout}s")
        return False

    def _publish_container(self, container_id: str) -> Optional[str]:
        """POST /{user_id}/media_publish to publish the container."""
        url = f"{GRAPH_API_BASE}/{self.user_id}/media_publish"
        params = {
            "creation_id": container_id,
            "access_token": self.access_token,
        }
        resp = requests.post(url, data=params, timeout=60)
        data = resp.json()

        if "id" in data:
            media_id = data["id"]
            logger.info(f"Published reel — media ID: {media_id}")
            return media_id
        else:
            logger.error(f"Failed to publish: {data}")
            return None

    # ──────────────────── Token Management ────────────────────

    def refresh_long_lived_token(self) -> Optional[str]:
        """
        Exchange a valid long-lived token for a new one (extends expiry by 60 days).
        Requires app_id and app_secret to be set.
        Returns the new token or None on failure.
        """
        if not self.app_id or not self.app_secret:
            logger.warning("Cannot refresh token — app_id and app_secret not configured")
            return None

        url = f"{GRAPH_API_BASE}/oauth/access_token"
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": self.access_token,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            new_token = data.get("access_token")
            if new_token:
                logger.info("Successfully refreshed long-lived token")
                self.access_token = new_token
                return new_token
            else:
                logger.error(f"Token refresh failed: {data}")
                return None
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None

    def check_token_validity(self) -> Tuple[bool, Optional[int]]:
        """
        Check if the current token is valid and return remaining seconds.
        Returns (is_valid, seconds_remaining_or_None).
        """
        url = f"{GRAPH_API_BASE}/debug_token"
        params = {
            "input_token": self.access_token,
            "access_token": self.access_token,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json().get("data", {})
            is_valid = data.get("is_valid", False)
            expires_at = data.get("expires_at", 0)
            remaining = max(0, expires_at - int(time.time())) if expires_at else None
            return is_valid, remaining
        except Exception as e:
            logger.error(f"Token check error: {e}")
            return False, None
