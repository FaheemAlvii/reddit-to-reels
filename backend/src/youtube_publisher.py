"""
YouTube Shorts Publisher - Upload short-form videos to YouTube via the Data API v3.

WARNING: NOT END TO END TESTED
This publisher is implemented based on YouTube Data API v3 docs but has not been
verified with a live channel by the author. Expect to debug OAuth refresh, quota,
or upload edge cases. Pull requests with fixes are welcome.

Requires:
  - Google Cloud project with YouTube Data API v3 enabled
  - OAuth 2.0 credentials (client_id, client_secret, refresh_token)
  - Channel must be verified for uploads

Setup:
  1. Create OAuth 2.0 credentials in Google Cloud Console
  2. Run the one-time auth flow to get a refresh_token (see get_initial_token())
  3. Store client_id, client_secret, refresh_token in channels.json

Author: Faheem Alvi <faheemalvi2000@gmail.com>
GitHub: https://github.com/FaheemAlvii
"""

import os
import time
import json
import random
import logging
import requests
from typing import Optional, List, Dict, Any

logger = logging.getLogger("youtube_publisher")

YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

FIXED_HASHTAGS = [
    "#redditstories", "#reddit", "#shorts", "#trending",
    "#viral", "#storytime",
]

RANDOM_HASHTAG_POOL = [
    "#askreddit", "#relatable", "#drama", "#crazystory",
    "#truestory", "#redditstory", "#redditreadings",
    "#relationship", "#aita", "#tifu", "#confession",
    "#unbelievable", "#mindblown", "#realstory", "#fyp",
]


class YouTubePublisher:
    """Upload YouTube Shorts via the YouTube Data API v3."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    # ──────────────────── Auth ────────────────────

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        resp = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)

        data = resp.json()
        if "access_token" not in data:
            logger.error(f"Failed to refresh YouTube token: {data}")
            raise RuntimeError(f"YouTube token refresh failed: {data.get('error_description', 'unknown')}")

        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        logger.info("YouTube access token refreshed")
        return self._access_token

    # ──────────────────── Caption ────────────────────

    @staticmethod
    def build_title(title: str, part_num: int = 1, total_parts: int = 1) -> str:
        """Build a YouTube Shorts title (max 100 chars)."""
        if total_parts > 1:
            t = f"Part {part_num}: {title}"
        else:
            t = title
        return t[:100]

    @staticmethod
    def build_description(title: str, part_num: int = 1, total_parts: int = 1,
                          extra_hashtags: List[str] | None = None) -> str:
        """Build description with hashtags."""
        lines = []
        if total_parts > 1:
            lines.append(f"Part {part_num} of {total_parts}: {title}")
        else:
            lines.append(title)

        lines.append("")

        hashtags = list(FIXED_HASHTAGS)
        if extra_hashtags:
            hashtags.extend(extra_hashtags)
        pool = [h for h in RANDOM_HASHTAG_POOL if h not in hashtags]
        hashtags.extend(random.sample(pool, min(random.randint(3, 5), len(pool))))

        lines.append(" ".join(hashtags))
        return "\n".join(lines)

    # ──────────────────── Upload ────────────────────

    def upload_short(self, video_path: str, title: str, description: str,
                     thumbnail_path: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     category_id: str = "22",
                     privacy: str = "public") -> Optional[str]:
        """
        Upload a video as a YouTube Short.

        Args:
            video_path: Local path to the video file
            title: Video title (max 100 chars)
            description: Video description
            thumbnail_path: Optional custom thumbnail (requires verified channel)
            tags: Optional list of tags
            category_id: YouTube category (22 = People & Blogs)
            privacy: public, unlisted, or private

        Returns:
            YouTube video ID or None on failure
        """
        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return None

        token = self._get_access_token()

        # Video metadata
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or ["reddit", "shorts", "storytime"],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "shorts": {  # Mark as Short
                    "isShort": True,
                },
            },
        }

        file_size = os.path.getsize(video_path)
        logger.info(f"Uploading to YouTube: {title[:50]}… ({file_size / 1024 / 1024:.1f}MB)")

        try:
            # ── Step 1: Initiate resumable upload ──
            init_resp = requests.post(
                YOUTUBE_UPLOAD_URL,
                params={
                    "uploadType": "resumable",
                    "part": "snippet,status",
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/mp4",
                    "X-Upload-Content-Length": str(file_size),
                },
                json=body,
                timeout=60,
            )

            if init_resp.status_code not in (200, 308):
                logger.error(f"YouTube upload init failed [{init_resp.status_code}]: {init_resp.text}")
                return None

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                logger.error("No upload URL returned by YouTube")
                return None

            # ── Step 2: Upload the video file ──
            with open(video_path, "rb") as f:
                upload_resp = requests.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(file_size),
                    },
                    data=f,
                    timeout=600,
                )

            if upload_resp.status_code not in (200, 201):
                logger.error(f"YouTube upload failed [{upload_resp.status_code}]: {upload_resp.text}")
                return None

            video_data = upload_resp.json()
            video_id = video_data.get("id")
            logger.info(f"✅ YouTube upload complete — video ID: {video_id}")

            # ── Step 3: Set custom thumbnail (optional) ──
            if thumbnail_path and video_id and os.path.exists(thumbnail_path):
                self._set_thumbnail(video_id, thumbnail_path)

            return video_id

        except Exception as e:
            logger.error(f"YouTube upload error: {e}")
            return None

    def _set_thumbnail(self, video_id: str, thumbnail_path: str):
        """Upload a custom thumbnail for a video."""
        try:
            token = self._get_access_token()
            with open(thumbnail_path, "rb") as f:
                resp = requests.post(
                    f"{YOUTUBE_API_BASE}/thumbnails/set",
                    params={"videoId": video_id},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "image/jpeg",
                    },
                    data=f,
                    timeout=60,
                )
            if resp.status_code == 200:
                logger.info(f"Thumbnail set for {video_id}")
            else:
                logger.warning(f"Thumbnail upload failed [{resp.status_code}]: {resp.text}")
        except Exception as e:
            logger.warning(f"Thumbnail error: {e}")

    def check_quota(self) -> Optional[dict]:
        """Check remaining API quota (best-effort)."""
        try:
            token = self._get_access_token()
            resp = requests.get(
                f"{YOUTUBE_API_BASE}/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            if resp.status_code == 200:
                return {"status": "ok", "channel": resp.json().get("items", [{}])[0].get("snippet", {}).get("title", "Unknown")}
            else:
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_initial_token_instructions() -> str:
    """Return instructions for the one-time OAuth flow."""
    return """
=== YouTube OAuth Setup ===

1. Go to https://console.cloud.google.com/
2. Create a project (or use existing)
3. Enable "YouTube Data API v3"
4. Go to Credentials → Create OAuth 2.0 Client ID (Desktop app)
5. Download the client JSON — note client_id and client_secret
6. Run this one-time auth flow in Python:

    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        scopes=['https://www.googleapis.com/auth/youtube.upload']
    )
    credentials = flow.run_local_server(port=8080)
    print("Refresh token:", credentials.refresh_token)

7. Put client_id, client_secret, and refresh_token in channels.json
"""
