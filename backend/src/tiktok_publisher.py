"""
TikTok Publisher - Upload videos to TikTok via the Content Posting API.

WARNING: NOT END TO END TESTED
This publisher is implemented based on TikTok Content Posting API docs but has
not been verified with a live account by the author. Expect to debug app
approval, scopes, or polling behavior. Pull requests with fixes are welcome.

Requires:
  - TikTok Developer App with Video Publish scope (video.publish, video.upload)
  - OAuth 2.0 flow to get access_token and refresh_token
  - App must be approved for Content Posting API access

TikTok Content Posting API Flow:
  1. Initialize upload, get upload_url
  2. Upload video bytes to upload_url
  3. Publish with caption, privacy, etc.
  4. Poll publish status

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started

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

logger = logging.getLogger("tiktok_publisher")

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"

FIXED_HASHTAGS = [
    "#redditstories", "#reddit", "#fyp", "#trending",
    "#viral", "#storytime", "#foryou",
]

RANDOM_HASHTAG_POOL = [
    "#askreddit", "#relatable", "#drama", "#crazystory",
    "#truestory", "#redditstory", "#redditreadings",
    "#relationship", "#aita", "#tifu", "#confession",
    "#unbelievable", "#mindblown", "#realstory", "#explore",
    "#tiktok", "#greenscreen",
]


class TikTokPublisher:
    """Upload videos to TikTok via the Content Posting API."""

    def __init__(self, access_token: str, refresh_token: str = "",
                 client_key: str = "", client_secret: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_key = client_key
        self.client_secret = client_secret

    # ──────────────────── Auth ────────────────────

    def refresh_access_token(self) -> Optional[str]:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token or not self.client_key or not self.client_secret:
            logger.warning("Cannot refresh — missing refresh_token, client_key, or client_secret")
            return None

        try:
            resp = requests.post(
                f"{TIKTOK_API_BASE}/oauth/token/",
                json={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                timeout=30,
            )
            data = resp.json()
            if data.get("data", {}).get("access_token"):
                self.access_token = data["data"]["access_token"]
                new_refresh = data["data"].get("refresh_token")
                if new_refresh:
                    self.refresh_token = new_refresh
                logger.info("TikTok access token refreshed")
                return self.access_token
            else:
                logger.error(f"TikTok token refresh failed: {data}")
                return None
        except Exception as e:
            logger.error(f"TikTok token refresh error: {e}")
            return None

    # ──────────────────── Caption ────────────────────

    @staticmethod
    def build_caption(title: str, part_num: int = 1, total_parts: int = 1,
                      extra_hashtags: List[str] | None = None) -> str:
        """Build a TikTok caption (max ~2200 chars)."""
        if total_parts > 1:
            header = f"Part {part_num}: {title}"
        else:
            header = title

        hashtags = list(FIXED_HASHTAGS)
        if extra_hashtags:
            hashtags.extend(extra_hashtags)
        pool = [h for h in RANDOM_HASHTAG_POOL if h not in hashtags]
        hashtags.extend(random.sample(pool, min(random.randint(3, 5), len(pool))))

        caption = f"{header} {' '.join(hashtags)}"
        return caption[:2200]

    # ──────────────────── Upload Flow ────────────────────

    def upload_video(self, video_path: str, caption: str,
                     privacy: str = "PUBLIC_TO_EVERYONE",
                     disable_comments: bool = False,
                     disable_duet: bool = False,
                     disable_stitch: bool = False) -> Optional[str]:
        """
        Upload a video to TikTok using the Content Posting API.

        Privacy options: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS,
                         FOLLOWER_OF_CREATOR, SELF_ONLY

        Returns the publish_id or None on failure.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return None

        file_size = os.path.getsize(video_path)
        logger.info(f"Uploading to TikTok: {caption[:50]}… ({file_size / 1024 / 1024:.1f}MB)")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            # ── Step 1: Initialize upload ──
            init_body = {
                "post_info": {
                    "title": caption[:150],
                    "description": caption,
                    "privacy_level": privacy,
                    "disable_comment": disable_comments,
                    "disable_duet": disable_duet,
                    "disable_stitch": disable_stitch,
                    "video_cover_timestamp_ms": 500,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,  # Single chunk upload
                    "total_chunk_count": 1,
                },
            }

            init_resp = requests.post(
                f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/",
                headers=headers,
                json=init_body,
                timeout=60,
            )

            init_data = init_resp.json()
            if init_data.get("error", {}).get("code") != "ok":
                logger.error(f"TikTok init failed: {init_data}")
                # Try token refresh and retry once
                if "access_token" in str(init_data).lower() or init_resp.status_code == 401:
                    if self.refresh_access_token():
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        init_resp = requests.post(
                            f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/",
                            headers=headers, json=init_body, timeout=60,
                        )
                        init_data = init_resp.json()
                        if init_data.get("error", {}).get("code") != "ok":
                            logger.error(f"TikTok init retry failed: {init_data}")
                            return None
                    else:
                        return None
                else:
                    return None

            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")

            if not upload_url:
                logger.error("No upload URL from TikTok")
                return None

            # ── Step 2: Upload video bytes ──
            with open(video_path, "rb") as f:
                video_data = f.read()

            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            }

            upload_resp = requests.put(
                upload_url,
                headers=upload_headers,
                data=video_data,
                timeout=600,
            )

            if upload_resp.status_code not in (200, 201):
                logger.error(f"TikTok upload failed [{upload_resp.status_code}]: {upload_resp.text}")
                return None

            logger.info(f"Video uploaded, publish_id: {publish_id}")

            # ── Step 3: Poll publish status ──
            if publish_id:
                final_status = self._poll_publish_status(publish_id)
                if final_status == "PUBLISH_COMPLETE":
                    logger.info(f"✅ TikTok publish complete — publish_id: {publish_id}")
                    return publish_id
                else:
                    logger.warning(f"TikTok publish status: {final_status}")
                    return publish_id  # Return anyway — might still be processing

            return publish_id

        except Exception as e:
            logger.error(f"TikTok upload error: {e}")
            return None

    def _poll_publish_status(self, publish_id: str, timeout: int = 120) -> str:
        """Poll the publish status endpoint."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        deadline = time.time() + timeout
        interval = 5

        while time.time() < deadline:
            try:
                resp = requests.post(
                    f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                    timeout=30,
                )
                data = resp.json()
                status = data.get("data", {}).get("status", "UNKNOWN")

                if status in ("PUBLISH_COMPLETE", "FAILED", "PUBLISH_CANCELLED"):
                    return status

            except Exception:
                pass

            time.sleep(interval)
            interval = min(interval + 3, 20)

        return "TIMEOUT"

    def check_creator_info(self) -> Optional[dict]:
        """Check the authenticated creator's info."""
        try:
            resp = requests.get(
                f"{TIKTOK_API_BASE}/user/info/",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"fields": "display_name,avatar_url,follower_count"},
                timeout=30,
            )
            data = resp.json()
            if data.get("data", {}).get("user"):
                return data["data"]["user"]
            return None
        except Exception as e:
            logger.error(f"TikTok creator info error: {e}")
            return None


def get_setup_instructions() -> str:
    return """
=== TikTok Content Posting API Setup ===

1. Go to https://developers.tiktok.com/ and create a Developer account
2. Create an App → select "Content Posting API"
3. Request "video.publish" and "video.upload" scopes
4. Set up OAuth redirect URL
5. Complete the one-time OAuth flow to get access_token and refresh_token:

   Authorization URL:
   https://www.tiktok.com/v2/auth/authorize/?client_key=YOUR_KEY&scope=video.publish,video.upload&response_type=code&redirect_uri=YOUR_REDIRECT

6. Exchange the auth code for tokens:
   POST https://open.tiktokapis.com/v2/oauth/token/
   {
     "client_key": "...",
     "client_secret": "...",
     "code": "AUTH_CODE_FROM_REDIRECT",
     "grant_type": "authorization_code",
     "redirect_uri": "YOUR_REDIRECT"
   }

7. Put access_token, refresh_token, client_key, client_secret in channels.json

Note: TikTok access tokens expire in 24h, refresh tokens in 365 days.
      The bot auto-refreshes access tokens when needed.
"""
