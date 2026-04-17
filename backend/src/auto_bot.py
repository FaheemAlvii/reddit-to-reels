"""
Autonomous Video Bot. Runs 24/7, cycles through channel configs,
generates videos via the existing pipeline, publishes to Instagram Reels,
and sends Discord webhook notifications.

Usage:
    python src/auto_bot.py                      # Run the bot
    python src/auto_bot.py --once               # Run one cycle only
    python src/auto_bot.py --channel RedditDrama # Run for one channel only

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""

import os
import sys
import json
import time
import copy
import signal
import logging
import argparse
import random
import glob
import shutil
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# ── Path Setup ──
if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from main import run_pipeline, load_config
from discord_notifier import DiscordNotifier
from instagram_publisher import InstagramPublisher
from youtube_publisher import YouTubePublisher
from tiktok_publisher import TikTokPublisher
from snapchat_publisher import SnapchatPublisher

# ── Logging ──
LOG_FILE = os.path.join(PROJECT_ROOT, "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("auto_bot")

# ── Globals ──
CHANNELS_PATH = os.path.join(PROJECT_ROOT, "channels.json")
STATE_PATH = os.path.join(PROJECT_ROOT, "bot_state.json")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info(f"Received signal {signum}, shutting down gracefully…")
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ═══════════════════════ State Persistence ═══════════════════════

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def get_channel_state(state: dict, channel_name: str) -> dict:
    """Return per-channel state, initializing if missing."""
    if channel_name not in state:
        state[channel_name] = {
            "last_posted_at": None,
            "posts_today": 0,
            "last_reset_date": str(date.today()),
            "total_posts": 0,
            "last_post_id": None,
        }
    cs = state[channel_name]
    # Reset daily counter if date changed
    if cs.get("last_reset_date") != str(date.today()):
        cs["posts_today"] = 0
        cs["last_reset_date"] = str(date.today())
    return cs


# ═══════════════════════ Config Management ═══════════════════════

def load_channels() -> List[dict]:
    try:
        with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
            channels = json.load(f)
        return [c for c in channels if c.get("enabled", True)]
    except Exception as e:
        logger.error(f"Failed to load channels.json: {e}")
        return []


def merge_config(base: dict, overrides: dict) -> dict:
    """Deep-merge overrides into a copy of base config."""
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def write_temp_config(merged: dict):
    """Write merged config to config.json for the pipeline to pick up."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)


def backup_config() -> Optional[dict]:
    """Read and return the current config.json (so we can restore it)."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


# ═══════════════════════ Video Discovery ═══════════════════════

def find_latest_videos(videos_dir: str, before_entries: set) -> List[dict]:
    """
    Find newly generated video files/directories in videos/ that weren't
    there before the pipeline ran.
    Returns list of dicts: {path, thumbnail, title}
    """
    results = []
    if not os.path.isdir(videos_dir):
        return results

    for entry in os.listdir(videos_dir):
        if entry in before_entries:
            continue
        entry_path = os.path.join(videos_dir, entry)

        if os.path.isdir(entry_path):
            # Multi-part series directory
            mp4s = sorted(glob.glob(os.path.join(entry_path, "*.mp4")))
            for mp4 in mp4s:
                base = os.path.splitext(mp4)[0]
                thumb = base + ".jpg"
                results.append({
                    "path": mp4,
                    "thumbnail": thumb if os.path.exists(thumb) else None,
                    "title": os.path.basename(mp4),
                })
        elif entry.endswith(".mp4"):
            base = os.path.splitext(entry_path)[0]
            thumb = base + ".jpg"
            results.append({
                "path": entry_path,
                "thumbnail": thumb if os.path.exists(thumb) else None,
                "title": entry,
            })

    return results


def extract_post_title_from_video(video_filename: str) -> str:
    """Best-effort extraction of the post title from the video filename."""
    # Format: {safe_title}_{video_mode}_{timestamp}[_partN].mp4
    name = os.path.splitext(video_filename)[0]
    # Remove _partN suffix
    import re
    name = re.sub(r'_part\d+$', '', name)
    # Remove timestamp (YYYYMMDD_HHMMSS)
    name = re.sub(r'_\d{8}_\d{6}$', '', name)
    # Remove video mode suffix
    for mode in ('short_reel', 'full_video', 'reel'):
        if name.endswith(f'_{mode}'):
            name = name[: -len(mode) - 1]
            break
    return name.replace('_', ' ').strip()


# ═══════════════════════ Main Bot Logic ═══════════════════════

def is_channel_due(channel: dict, channel_state: dict) -> bool:
    """Check if a channel is due for its next post."""
    # Daily limit
    max_per_day = channel.get("max_posts_per_day", 4)
    if channel_state["posts_today"] >= max_per_day:
        return False

    last = channel_state.get("last_posted_at")
    if not last:
        return True

    try:
        last_dt = datetime.fromisoformat(last)
    except (ValueError, TypeError):
        return True

    interval = channel.get("posting_interval_minutes", 240)
    elapsed = (datetime.now() - last_dt).total_seconds() / 60
    return elapsed >= interval


# ═══════════════════════ Platform Publishers ═══════════════════════

def _platform_configured(channel: dict, platform: str) -> bool:
    """Check if a platform has credentials configured."""
    if platform == "instagram":
        return bool(channel.get("instagram_user_id") and channel.get("instagram_access_token"))
    elif platform == "youtube":
        yt = channel.get("youtube", {})
        return bool(yt.get("client_id") and yt.get("refresh_token"))
    elif platform == "tiktok":
        tt = channel.get("tiktok", {})
        return bool(tt.get("access_token"))
    elif platform == "snapchat":
        sc = channel.get("snapchat", {})
        return bool(sc.get("client_id") and sc.get("refresh_token"))
    return False


def _publish_instagram(channel: dict, name: str, videos: list, title: str, total: int) -> List[str]:
    ig_user_id = channel.get("instagram_user_id", "")
    ig_token = channel.get("instagram_access_token", "")
    if not ig_user_id or not ig_token:
        return []

    published = []
    publisher = InstagramPublisher(
        user_id=ig_user_id, access_token=ig_token,
        app_id=channel.get("app_id", ""), app_secret=channel.get("app_secret", ""),
        public_host=channel.get("public_host", ""),
        file_server_port=channel.get("file_server_port", 9123),
    )

    is_valid, remaining = publisher.check_token_validity()
    if not is_valid:
        logger.error(f"Instagram token for {name} is invalid!")
        return []
    if remaining and remaining < 7 * 24 * 3600:
        publisher.refresh_long_lived_token()

    for idx, vi in enumerate(videos, 1):
        caption = InstagramPublisher.build_caption(title, idx, total)
        logger.info(f"📸 Instagram: Publishing Part {idx}/{total}…")
        mid = publisher.publish_reel(vi["path"], caption, vi.get("thumbnail"))
        if mid:
            published.append(mid)
        if idx < total:
            time.sleep(30)
    return published


def _publish_youtube(channel: dict, name: str, videos: list, title: str, total: int) -> List[str]:
    yt_cfg = channel.get("youtube", {})
    if not yt_cfg.get("client_id") or not yt_cfg.get("refresh_token"):
        return []

    published = []
    publisher = YouTubePublisher(
        client_id=yt_cfg["client_id"],
        client_secret=yt_cfg.get("client_secret", ""),
        refresh_token=yt_cfg["refresh_token"],
    )

    for idx, vi in enumerate(videos, 1):
        yt_title = YouTubePublisher.build_title(title, idx, total)
        desc = YouTubePublisher.build_description(title, idx, total)
        logger.info(f"▶️  YouTube: Uploading Part {idx}/{total}…")
        vid = publisher.upload_short(vi["path"], yt_title, desc, vi.get("thumbnail"),
                                     privacy=yt_cfg.get("privacy", "public"))
        if vid:
            published.append(vid)
        if idx < total:
            time.sleep(10)
    return published


def _publish_tiktok(channel: dict, name: str, videos: list, title: str, total: int) -> List[str]:
    tt_cfg = channel.get("tiktok", {})
    if not tt_cfg.get("access_token"):
        return []

    published = []
    publisher = TikTokPublisher(
        access_token=tt_cfg["access_token"],
        refresh_token=tt_cfg.get("refresh_token", ""),
        client_key=tt_cfg.get("client_key", ""),
        client_secret=tt_cfg.get("client_secret", ""),
    )

    for idx, vi in enumerate(videos, 1):
        caption = TikTokPublisher.build_caption(title, idx, total)
        logger.info(f"🎵 TikTok: Uploading Part {idx}/{total}…")
        pid = publisher.upload_video(vi["path"], caption,
                                     privacy=tt_cfg.get("privacy", "PUBLIC_TO_EVERYONE"))
        if pid:
            published.append(pid)
        if idx < total:
            time.sleep(15)
    return published


def _publish_snapchat(channel: dict, name: str, videos: list, title: str, total: int) -> List[str]:
    sc_cfg = channel.get("snapchat", {})
    if not sc_cfg.get("client_id") or not sc_cfg.get("refresh_token"):
        return []

    published = []
    publisher = SnapchatPublisher(
        client_id=sc_cfg["client_id"],
        client_secret=sc_cfg.get("client_secret", ""),
        refresh_token=sc_cfg["refresh_token"],
        organization_id=sc_cfg.get("organization_id", ""),
    )

    for idx, vi in enumerate(videos, 1):
        caption = SnapchatPublisher.build_caption(title, idx, total)
        logger.info(f"👻 Snapchat: Uploading Part {idx}/{total}…")
        sid = publisher.upload_spotlight(vi["path"], caption)
        if sid:
            published.append(sid)
        if idx < total:
            time.sleep(10)
    return published



    """
    Execute the full cycle for one channel:
    1. Merge & swap config
    2. Run pipeline
    3. Publish to Instagram
    4. Discord notification
    5. Update state
    """
    name = channel["name"]
    logger.info(f"{'='*60}")
    logger.info(f"  CHANNEL: {name}")
    logger.info(f"{'='*60}")

    # ── Config swap ──
    original_config = backup_config()
    base_config = original_config or {}
    merged = merge_config(base_config, channel.get("config_overrides", {}))

    # Disable Discord in pipeline config (we'll send our own notifications)
    merged.setdefault("discord", {})["enabled"] = False

    write_temp_config(merged)

    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    before_entries = set(os.listdir(videos_dir)) if os.path.isdir(videos_dir) else set()

    try:
        # ── Run pipeline ──
        mode = merged.get("formatting", {}).get("default_mode", "qa")
        logger.info(f"Running pipeline in {mode} mode…")
        success = run_pipeline(mode=mode)

        if not success:
            logger.error(f"Pipeline failed for channel {name}")
            return False

        # ── Discover generated videos ──
        new_videos = find_latest_videos(videos_dir, before_entries)
        if not new_videos:
            logger.warning(f"Pipeline succeeded but no new videos found for {name}")
            return False

        logger.info(f"Found {len(new_videos)} new video(s)")

        # ── Determine post title ──
        post_title = extract_post_title_from_video(new_videos[0]["title"])
        total_parts = len(new_videos)

        # ── Publish to all configured platforms ──
        publish_results: Dict[str, List[str]] = {}

        publish_results["instagram"] = _publish_instagram(channel, name, new_videos, post_title, total_parts)
        publish_results["youtube"] = _publish_youtube(channel, name, new_videos, post_title, total_parts)
        publish_results["tiktok"] = _publish_tiktok(channel, name, new_videos, post_title, total_parts)
        publish_results["snapchat"] = _publish_snapchat(channel, name, new_videos, post_title, total_parts)

        # Aggregate results
        all_published = {k: v for k, v in publish_results.items() if v}
        any_published = bool(all_published)

        # ── Discord Notification ──
        webhook = channel.get("discord_webhook_url", "")
        if webhook:
            try:
                notifier = DiscordNotifier(webhook)
                status_emoji = "✅" if any_published else "⚠️"

                # Build platform summary
                platform_lines = []
                for plat, ids in publish_results.items():
                    if ids:
                        platform_lines.append(f"✅ {plat.capitalize()}: {len(ids)}/{total_parts}")
                    elif _platform_configured(channel, plat):
                        platform_lines.append(f"❌ {plat.capitalize()}: failed")

                fields = [
                    {"name": "Channel", "value": name, "inline": True},
                    {"name": "Parts", "value": str(total_parts), "inline": True},
                ]
                if platform_lines:
                    fields.append({
                        "name": "Platforms",
                        "value": "\n".join(platform_lines),
                        "inline": False,
                    })

                notifier.send_embed(
                    title=f"{status_emoji} {'Published' if any_published else 'Video Generated (publish failed)'}",
                    description=f"**{post_title}**",
                    fields=fields,
                    color=0x00C853 if any_published else 0xFF9800,
                )

                upload_media = channel.get("config_overrides", {}).get("discord", {}).get("upload_media", True)
                if upload_media:
                    for vi in new_videos:
                        notifier.send_file(vi["path"])

            except Exception as e:
                logger.error(f"Discord notification failed: {e}")

        # ── Update state ──
        cs = get_channel_state(state, name)
        cs["last_posted_at"] = datetime.now().isoformat()
        cs["posts_today"] += 1
        cs["total_posts"] += 1
        if new_videos:
            cs["last_post_id"] = os.path.basename(os.path.dirname(new_videos[0]["path"]))
        save_state(state)

        return True

    except Exception as e:
        logger.error(f"Error running channel {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Restore original config
        if original_config is not None:
            write_temp_config(original_config)


def main_loop(single_run: bool = False, target_channel: Optional[str] = None):
    """Main bot loop — runs forever unless single_run=True."""
    logger.info("=" * 60)
    logger.info("  🤖 AUTO BOT STARTED")
    logger.info(f"  Project root: {PROJECT_ROOT}")
    logger.info(f"  Channels file: {CHANNELS_PATH}")
    logger.info(f"  State file: {STATE_PATH}")
    logger.info("=" * 60)

    while not _shutdown:
        channels = load_channels()
        if not channels:
            logger.warning("No enabled channels found. Sleeping 60s…")
            time.sleep(60)
            if single_run:
                break
            continue

        if target_channel:
            channels = [c for c in channels if c["name"] == target_channel]
            if not channels:
                logger.error(f"Channel '{target_channel}' not found or disabled.")
                return

        state = load_state()

        any_ran = False
        for channel in channels:
            if _shutdown:
                break

            name = channel["name"]
            cs = get_channel_state(state, name)

            if not is_channel_due(channel, cs):
                next_in = ""
                if cs.get("last_posted_at"):
                    try:
                        last_dt = datetime.fromisoformat(cs["last_posted_at"])
                        interval = channel.get("posting_interval_minutes", 240)
                        remaining = interval - (datetime.now() - last_dt).total_seconds() / 60
                        if remaining > 0:
                            next_in = f" (next in {remaining:.0f}m)"
                    except Exception:
                        pass
                logger.info(f"⏭ Skipping {name} — not due yet{next_in}")
                continue

            any_ran = True
            run_for_channel(channel, state)

            # Reload state in case another channel updated it
            state = load_state()

        if single_run:
            break

        # Sleep before next check cycle
        sleep_secs = 120 if any_ran else 60
        logger.info(f"💤 Sleeping {sleep_secs}s before next cycle…")

        # Interruptible sleep
        for _ in range(sleep_secs):
            if _shutdown:
                break
            time.sleep(1)

    logger.info("🛑 Auto bot stopped.")


# ═══════════════════════ Entry Point ═══════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Video Bot")
    parser.add_argument("--once", action="store_true", help="Run one cycle only")
    parser.add_argument("--channel", type=str, help="Run for a specific channel only")
    args = parser.parse_args()

    main_loop(single_run=args.once, target_channel=args.channel)
