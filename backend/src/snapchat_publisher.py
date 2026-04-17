"""
Snapchat Spotlight Publisher - Upload videos to Snapchat Spotlight
via the Snap Kit Content API / Marketing API.

WARNING: NOT END TO END TESTED
This publisher is implemented based on Snap public API docs but has not been
verified with a live account by the author. Spotlight API access requires
explicit approval from Snap. Pull requests with fixes are welcome.

Requires:
  - Snap Kit Developer App with content publishing permissions
  - OAuth 2.0 credentials (client_id, client_secret, refresh_token)

Snapchat Spotlight upload flow:
  1. Get upload URL from Snap API
  2. Upload media file
  3. Create a Spotlight post referencing the uploaded media

Docs: https://developers.snap.com/api/marketing-api/Spotlight
Note: Spotlight API access may require approval from Snap.

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

logger = logging.getLogger("snapchat_publisher")

SNAP_ACCOUNTS_API = "https://adsapi.snapchat.com/v1"
SNAP_TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"

FIXED_HASHTAGS = [
    "#redditstories", "#reddit", "#spotlight", "#trending",
    "#viral", "#storytime",
]

RANDOM_HASHTAG_POOL = [
    "#askreddit", "#relatable", "#drama", "#crazystory",
    "#truestory", "#redditstory", "#explore",
    "#relationship", "#aita", "#tifu", "#confession",
    "#unbelievable", "#mindblown", "#realstory", "#fyp",
    "#snapchat", "#snap",
]


class SnapchatPublisher:
    """Upload videos to Snapchat Spotlight via the Marketing/Content API."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 organization_id: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.organization_id = organization_id
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    # ──────────────────── Auth ────────────────────

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        resp = requests.post(SNAP_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)

        data = resp.json()
        if "access_token" not in data:
            logger.error(f"Snapchat token refresh failed: {data}")
            raise RuntimeError(f"Snapchat token refresh failed: {data.get('error_description', 'unknown')}")

        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 1800)
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        logger.info("Snapchat access token refreshed")
        return self._access_token

    # ──────────────────── Caption ────────────────────

    @staticmethod
    def build_caption(title: str, part_num: int = 1, total_parts: int = 1,
                      extra_hashtags: List[str] | None = None) -> str:
        """Build a Spotlight caption."""
        if total_parts > 1:
            header = f"Part {part_num}: {title}"
        else:
            header = title

        hashtags = list(FIXED_HASHTAGS)
        if extra_hashtags:
            hashtags.extend(extra_hashtags)
        pool = [h for h in RANDOM_HASHTAG_POOL if h not in hashtags]
        hashtags.extend(random.sample(pool, min(random.randint(3, 5), len(pool))))

        return f"{header} {' '.join(hashtags)}"

    # ──────────────────── Upload Flow ────────────────────

    def upload_spotlight(self, video_path: str, caption: str) -> Optional[str]:
        """
        Upload a video to Snapchat Spotlight.

        Flow:
          1. Upload media to Snap CDN
          2. Create a Spotlight creative
          3. Submit for publishing

        Returns the creative/media ID or None on failure.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return None

        file_size = os.path.getsize(video_path)
        logger.info(f"Uploading to Snapchat Spotlight: {caption[:50]}… ({file_size / 1024 / 1024:.1f}MB)")

        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
            }

            # ── Step 1: Create media upload ──
            # Request an upload URL from Snap
            create_media_resp = requests.post(
                f"{SNAP_ACCOUNTS_API}/organizations/{self.organization_id}/media",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "media": [{
                        "name": os.path.basename(video_path),
                        "type": "VIDEO",
                    }]
                },
                timeout=60,
            )

            if create_media_resp.status_code not in (200, 201):
                logger.error(f"Snap media create failed [{create_media_resp.status_code}]: {create_media_resp.text}")
                return None

            media_data = create_media_resp.json()
            media_list = media_data.get("media", [])
            if not media_list:
                logger.error(f"No media object returned: {media_data}")
                return None

            media_obj = media_list[0]
            media_id = media_obj.get("media", {}).get("id", media_obj.get("id", ""))
            upload_link = media_obj.get("media", {}).get("upload_link", media_obj.get("upload_link", ""))

            if not upload_link:
                # Alternative: use the direct upload endpoint
                upload_link = f"{SNAP_ACCOUNTS_API}/media/{media_id}/upload"

            # ── Step 2: Upload the video file ──
            with open(video_path, "rb") as f:
                upload_resp = requests.post(
                    upload_link,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "video/mp4",
                    },
                    data=f,
                    timeout=600,
                )

            if upload_resp.status_code not in (200, 201, 204):
                logger.error(f"Snap upload failed [{upload_resp.status_code}]: {upload_resp.text}")
                return None

            logger.info(f"Video uploaded to Snap CDN — media_id: {media_id}")

            # ── Step 3: Create Spotlight submission ──
            # Note: The exact endpoint and payload may vary based on
            # Snap's API version and your app's approved permissions.
            # This is the general pattern for Spotlight submissions.
            spotlight_resp = requests.post(
                f"{SNAP_ACCOUNTS_API}/organizations/{self.organization_id}/spotlight",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "spotlight": [{
                        "media_id": media_id,
                        "caption": caption[:280],  # Spotlight caption limit
                    }]
                },
                timeout=60,
            )

            if spotlight_resp.status_code in (200, 201):
                result = spotlight_resp.json()
                spotlight_id = result.get("spotlight", [{}])[0].get("id", media_id)
                logger.info(f"✅ Snapchat Spotlight submitted — ID: {spotlight_id}")
                return spotlight_id
            else:
                # If Spotlight-specific endpoint isn't available, the media upload itself
                # may be sufficient depending on the account type
                logger.warning(
                    f"Spotlight submission returned [{spotlight_resp.status_code}]: {spotlight_resp.text}. "
                    f"Media was uploaded successfully (media_id: {media_id})."
                )
                return media_id

        except Exception as e:
            logger.error(f"Snapchat upload error: {e}")
            return None

    def check_auth(self) -> bool:
        """Verify that authentication is working."""
        try:
            token = self._get_access_token()
            resp = requests.get(
                f"{SNAP_ACCOUNTS_API}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            return resp.status_code == 200
        except Exception:
            return False


def get_setup_instructions() -> str:
    return """
=== Snapchat Spotlight Setup ===

1. Go to https://kit.snapchat.com/ and create a Snap Kit app
2. Enable "Content" capability
3. Request API access for Spotlight publishing (may require approval)
4. Set up OAuth 2.0:
   - Add redirect URI
   - Note your client_id and client_secret
5. Complete OAuth flow to get refresh_token:

   Auth URL:
   https://accounts.snapchat.com/login/oauth2/authorize?client_id=YOUR_ID&redirect_uri=YOUR_URI&response_type=code&scope=spotlight.write

   Exchange code for tokens:
   POST https://accounts.snapchat.com/login/oauth2/access_token
   {
     "client_id": "...",
     "client_secret": "...",
     "code": "AUTH_CODE",
     "grant_type": "authorization_code",
     "redirect_uri": "YOUR_URI"
   }

6. Find your organization_id in the Snap Ads Manager
7. Put all credentials in channels.json under "snapchat" config

Note: Spotlight API access is limited. If unavailable, consider using
      Snap's manual upload or third-party tools as alternatives.
"""
