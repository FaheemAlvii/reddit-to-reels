#!/usr/bin/env python3
"""
Reddit Reel Maker. CLI / TUI entry point.

Designed to run on A-Shell (iOS, Python 3.13) as well as any desktop terminal.
Uses `rich` for a polished TUI when available; falls back to plain text menus.

Usage:
    python cli_app.py

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
from datetime import datetime

# ---------------------------------------------------------------------------
# Project root (same logic as other backend modules)
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure src is on the path so sibling modules can be imported
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

# ---------------------------------------------------------------------------
# Rich detection — graceful fallback
# ---------------------------------------------------------------------------
USE_RICH = False
console = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()
    USE_RICH = True
except ImportError:
    pass


def rprint(msg: str, style: str | None = None):
    """Print helper that uses rich when available."""
    if USE_RICH and console:
        console.print(msg, style=style)
    else:
        print(msg)


def rprint_header(title: str):
    if USE_RICH and console:
        console.print(Panel(title, style="bold cyan", expand=False))
    else:
        print()
        print("=" * 50)
        print(f"  {title}")
        print("=" * 50)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        rprint("[!] config.json not found — using defaults.", style="yellow")
        return {}
    except json.JSONDecodeError as e:
        rprint(f"[!] config.json parse error: {e}", style="red")
        return {}


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    rprint("Config saved.", style="green")


# ---------------------------------------------------------------------------
# Pipeline step wrappers (graceful degradation)
# ---------------------------------------------------------------------------

def step_fetch_post(config: dict) -> str | None:
    """Fetch a new Reddit post. Returns post_id or None."""
    try:
        from reddit_story_maker import RedditStoryMaker
    except ImportError as e:
        rprint(f"[!] Cannot fetch posts — missing dependency: {e}", style="yellow")
        return None

    rprint("Fetching new post…", style="cyan")
    try:
        maker = RedditStoryMaker()
        post_id = maker.process_new_post()
        if post_id:
            rprint(f"Fetched post: {post_id}", style="green")
        else:
            rprint("No suitable post found.", style="yellow")
        return post_id
    except Exception as e:
        rprint(f"[!] Fetch failed: {e}", style="red")
        return None


def step_format(post_id: str, mode: str) -> bool:
    """Format a fetched post for narration."""
    try:
        from story_formatter import StoryFormatter
    except ImportError as e:
        rprint(f"[!] Formatter unavailable: {e}", style="yellow")
        return False

    try:
        fmt = StoryFormatter(post_id)
        fmt.save_formatted_story(mode)
        rprint(f"Formatted ({mode}) ✓", style="green")
        return True
    except Exception as e:
        rprint(f"[!] Format failed: {e}", style="red")
        return False


def step_tts(post_id: str, mode: str, config: dict) -> list | None:
    """Generate TTS audio. Returns timeline list or None."""
    try:
        from tts_engine import TTSManager
        from story_formatter import StoryFormatter
    except ImportError as e:
        rprint(f"[!] TTS unavailable: {e}. Skipping.", style="yellow")
        return None

    try:
        tts = TTSManager()
        if not tts.enabled:
            rprint("[!] TTS disabled in config. Skipping.", style="yellow")
            return None

        fmt = StoryFormatter(post_id)
        title = fmt.summary.get("title", "")
        selftext = fmt.summary.get("selftext", "")
        author = fmt.summary.get("author", "Anonymous")

        comments = []
        if mode == "qa":
            max_c = config.get("formatting", {}).get("max_comments", 10)
            min_s = config.get("formatting", {}).get("min_comment_score", 10)
            comments = fmt._extract_top_comments(max_c, min_s)

        timeline = tts.generate_full_narrative(
            post_id=post_id,
            post_title=title,
            post_body=selftext if mode == "story" or selftext else "",
            post_author=author,
            comments=comments,
        )
        if timeline:
            rprint(f"TTS generated {len(timeline)} segments ✓", style="green")
        else:
            rprint("[!] TTS returned no segments.", style="yellow")
        return timeline
    except Exception as e:
        rprint(f"[!] TTS failed: {e}", style="red")
        return None


def step_video(post_id: str, timeline: list, config: dict) -> str | None:
    """Render video from timeline. Returns output path or None."""
    video_cfg = config.get("video", {})
    engine = video_cfg.get("engine", "moviepy")

    # Auto-detect: if moviepy unavailable, force ffmpeg
    try:
        from video_generator import MOVIEPY_AVAILABLE
        if not MOVIEPY_AVAILABLE:
            engine = "ffmpeg"
            rprint("[i] moviepy unavailable — using FFmpeg engine.", style="cyan")
    except ImportError:
        engine = "ffmpeg"

    try:
        from video_generator import VideoGenerator
    except ImportError as e:
        rprint(f"[!] VideoGenerator unavailable: {e}. Skipping.", style="yellow")
        return None

    try:
        video_mode = video_cfg.get("mode", "reel")
        hw = video_cfg.get("hw_accel", "none")
        threads = video_cfg.get("threads", 0)
        branding = config.get("branding", "")

        vg = VideoGenerator(mode=video_mode, hw_accel=hw, threads=threads)
        output_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
        output_path = os.path.join(output_dir, "video.mp4")

        if engine == "ffmpeg":
            result = vg.generate_video_ffmpeg(timeline, output_path, branding=branding)
        else:
            result = vg.generate_video(timeline, output_path, branding=branding)

        if result:
            # Move to videos/ directory
            videos_dir = os.path.join(PROJECT_ROOT, "videos")
            os.makedirs(videos_dir, exist_ok=True)
            import re, shutil
            from story_formatter import StoryFormatter
            fmt = StoryFormatter(post_id)
            title = fmt.summary.get("title", "video")
            safe_title = re.sub(r"[^\w\-_]", "_", title)[:50].strip("_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"{safe_title}_{video_mode}_{ts}.mp4"
            final_path = os.path.join(videos_dir, final_name)
            try:
                shutil.move(result, final_path)
                result = final_path
            except Exception:
                pass
            rprint(f"Video saved: {result}", style="green")
        else:
            rprint("[!] Video generation returned nothing.", style="yellow")
        return result
    except Exception as e:
        rprint(f"[!] Video failed: {e}", style="red")
        return None


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_full_pipeline(config: dict, post_id: str | None = None):
    """Run the complete pipeline: fetch → format → gemini hooks → TTS → video."""
    mode = config.get("formatting", {}).get("default_mode", "qa")

    # Step 1: Fetch
    if not post_id:
        post_id = step_fetch_post(config)
    if not post_id:
        return

    # Step 2: Format
    step_format(post_id, mode)

    # Step 2.5: Gemini Hooks
    gemini_hook_text = None
    gemini_thumbnail_text = None
    gemini_cfg = config.get("gemini", {})
    if gemini_cfg.get("enabled", False) and gemini_cfg.get("api_key", ""):
        try:
            from gemini_hooks import generate_hooks
            from story_formatter import StoryFormatter
            fmt = StoryFormatter(post_id)
            title = fmt.summary.get("title", "")
            selftext = fmt.summary.get("selftext", "")
            comments_ctx = ""
            if mode == "qa":
                max_c = config.get("formatting", {}).get("max_comments", 10)
                min_s = config.get("formatting", {}).get("min_comment_score", 10)
                top_c = fmt._extract_top_comments(max_c, min_s)
                comments_ctx = "\n".join(c.get("body", "")[:200] for c in top_c[:5])
            rprint("Generating Gemini hooks...", style="cyan")
            gemini_hook_text, gemini_thumbnail_text = generate_hooks(config, title, selftext, comments_ctx)
            if gemini_hook_text:
                rprint(f"Hook: \"{gemini_hook_text[:80]}\"", style="green")
            if gemini_thumbnail_text:
                rprint(f"Thumbnail: \"{gemini_thumbnail_text[:60]}\"", style="green")
        except Exception as e:
            rprint(f"[!] Gemini hooks failed (non-fatal): {e}", style="yellow")

    # Step 3: TTS
    timeline = step_tts(post_id, mode, config)

    # Prepend Gemini hook to timeline
    if gemini_hook_text and timeline:
        try:
            from tts_engine import StreamlabsTTS
            from story_formatter import StoryFormatter
            fmt = StoryFormatter(post_id)
            author = fmt.summary.get("author", "Anonymous")
            hook_audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
            tts_cfg = config.get("tts", {})
            hook_tts = StreamlabsTTS(voice=tts_cfg.get("main_voice", "Brian"), output_dir=hook_audio_dir)
            hook_segs = hook_tts.generate_segments(gemini_hook_text)
            if hook_segs:
                for s in hook_segs:
                    s["author"] = author
                timeline = hook_segs + timeline
                rprint(f"Hook prepended ({len(hook_segs)} segments)", style="green")
        except Exception as e:
            rprint(f"[!] Hook TTS failed: {e}", style="yellow")

    if not timeline:
        rprint("Pipeline stopped — no audio timeline.", style="yellow")
        return

    # Step 4: Video
    step_video(post_id, timeline, config)


# ---------------------------------------------------------------------------
# Post browser
# ---------------------------------------------------------------------------

def list_posts() -> list[str]:
    posts_dir = os.path.join(PROJECT_ROOT, "posts")
    if not os.path.isdir(posts_dir):
        return []
    folders = sorted(
        [d for d in os.listdir(posts_dir) if os.path.isdir(os.path.join(posts_dir, d))],
        reverse=True,
    )
    return folders


def browse_posts():
    """List fetched posts and let user pick one."""
    folders = list_posts()
    if not folders:
        rprint("No posts found. Fetch one first.", style="yellow")
        return None

    if USE_RICH and console:
        table = Table(title="Fetched Posts")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Post ID", style="green")
        table.add_column("Title")
        for i, pid in enumerate(folders, 1):
            title = _post_title(pid)
            table.add_row(str(i), pid, title[:60])
        console.print(table)
    else:
        rprint(f"\nFetched posts ({len(folders)}):")
        for i, pid in enumerate(folders, 1):
            title = _post_title(pid)
            print(f"  {i}. {pid} — {title[:60]}")

    choice = _prompt_int(f"Select post (1-{len(folders)}, 0=cancel): ", 0, len(folders))
    if choice == 0:
        return None
    return folders[choice - 1]


def _post_title(post_id: str) -> str:
    try:
        p = os.path.join(PROJECT_ROOT, "posts", post_id, "summary.json")
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("title", "(no title)")
    except Exception:
        return "(unknown)"


# ---------------------------------------------------------------------------
# Video listing
# ---------------------------------------------------------------------------

def list_videos():
    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    if not os.path.isdir(videos_dir):
        rprint("No videos directory found.", style="yellow")
        return

    entries = []
    for root, dirs, files in os.walk(videos_dir):
        for f in files:
            if f.lower().endswith((".mp4", ".mov", ".mkv")):
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                entries.append((f, sz))

    if not entries:
        rprint("No videos found.", style="yellow")
        return

    if USE_RICH and console:
        table = Table(title="Generated Videos")
        table.add_column("#", width=4)
        table.add_column("File")
        table.add_column("Size", justify="right")
        for i, (name, sz) in enumerate(entries, 1):
            table.add_row(str(i), name, _human_size(sz))
        console.print(table)
    else:
        rprint(f"\nGenerated videos ({len(entries)}):")
        for i, (name, sz) in enumerate(entries, 1):
            print(f"  {i}. {name}  ({_human_size(sz)})")


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


# ---------------------------------------------------------------------------
# Interactive config editor
# ---------------------------------------------------------------------------

def edit_config(config: dict):
    """Interactive config editor."""
    while True:
        rprint_header("Configuration")
        subreddits = config.get("subreddits", [])
        mode = config.get("formatting", {}).get("default_mode", "qa")
        branding = config.get("branding", "")
        hw = config.get("video", {}).get("hw_accel", "none")
        engine = config.get("video", {}).get("engine", "moviepy")
        video_mode = config.get("video", {}).get("mode", "reel")
        tts_enabled = config.get("tts", {}).get("enabled", False)
        tts_voice = config.get("tts", {}).get("main_voice", "Brian")
        gemini_enabled = config.get("gemini", {}).get("enabled", False)
        gemini_key = config.get("gemini", {}).get("api_key", "")

        items = [
            f"1. Subreddits:    {subreddits}",
            f"2. Mode:          {mode}",
            f"3. Branding:      {branding or '(none)'}",
            f"4. TTS Enabled:   {tts_enabled}",
            f"5. TTS Voice:     {tts_voice}",
            f"6. Video Mode:    {video_mode}",
            f"7. Engine:        {engine}",
            f"8. HW Accel:      {hw}",
            f"9. Gemini AI:     {'ON' if gemini_enabled else 'OFF'} {'(key set)' if gemini_key else '(no key)'}",
            f"10. Back to main menu",
        ]
        for item in items:
            rprint(f"  {item}")

        choice = _prompt_int("Edit which setting? > ", 1, 10)

        if choice == 10:
            break
        elif choice == 1:
            raw = input("Subreddits (comma-separated): ").strip()
            if raw:
                config["subreddits"] = [s.strip() for s in raw.split(",") if s.strip()]
        elif choice == 2:
            m = input("Mode (story / qa): ").strip().lower()
            if m in ("story", "qa"):
                config.setdefault("formatting", {})["default_mode"] = m
        elif choice == 3:
            config["branding"] = input("Branding handle: ").strip()
        elif choice == 4:
            config.setdefault("tts", {})["enabled"] = not tts_enabled
            rprint(f"TTS {'enabled' if not tts_enabled else 'disabled'}.", style="cyan")
        elif choice == 5:
            config.setdefault("tts", {})["main_voice"] = input("Voice name: ").strip() or "Brian"
        elif choice == 6:
            vm = input("Video mode (reel / short_reel / full): ").strip().lower()
            if vm in ("reel", "short_reel", "full"):
                config.setdefault("video", {})["mode"] = vm
        elif choice == 7:
            eng = input("Engine (moviepy / ffmpeg): ").strip().lower()
            if eng in ("moviepy", "ffmpeg"):
                config.setdefault("video", {})["engine"] = eng
        elif choice == 8:
            h = input("HW Accel (none / nvenc / amf): ").strip().lower()
            if h in ("none", "nvenc", "amf"):
                config.setdefault("video", {})["hw_accel"] = h
        elif choice == 9:
            gem = config.setdefault("gemini", {})
            rprint(f"\n  Gemini is currently {'ON' if gemini_enabled else 'OFF'}")
            toggle = input("  Toggle on/off? (y/n): ").strip().lower()
            if toggle == "y":
                gem["enabled"] = not gemini_enabled
                rprint(f"  Gemini {'enabled' if not gemini_enabled else 'disabled'}.", style="cyan")
            key_input = input("  API Key (enter to keep current): ").strip()
            if key_input:
                gem["api_key"] = key_input
                rprint("  API key updated.", style="green")

        save_config(config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prompt_int(prompt: str, lo: int, hi: int) -> int:
    while True:
        try:
            v = int(input(prompt).strip())
            if lo <= v <= hi:
                return v
        except (ValueError, EOFError):
            pass
        rprint(f"Please enter a number between {lo} and {hi}.", style="yellow")


# ---------------------------------------------------------------------------
# Main menu loop
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Reddit Reel Maker — CLI / TUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli_app.py                          # interactive TUI
  python cli_app.py pipeline                 # fetch + full pipeline
  python cli_app.py pipeline --id abc123     # pipeline on existing post
  python cli_app.py pipeline --mode story    # pipeline in story mode
  python cli_app.py fetch                    # fetch a new post only
  python cli_app.py videos                   # list generated videos
  python cli_app.py posts                    # list fetched posts
  python cli_app.py url <reddit-url>         # generate from a Reddit URL
  python cli_app.py url <reddit-url> --mode story --video-mode short_reel
        """,
    )

    sub = parser.add_subparsers(dest="command")

    # -- pipeline --
    p_pipe = sub.add_parser("pipeline", aliases=["run"], help="Run the full pipeline")
    p_pipe.add_argument("--id", dest="post_id", help="Use an existing post ID (skip fetch)")
    p_pipe.add_argument("--mode", choices=["story", "qa"], help="Content mode (default: from config)")
    p_pipe.add_argument("--video-mode", choices=["reel", "short_reel", "full"], help="Video format override")
    p_pipe.add_argument("--engine", choices=["moviepy", "ffmpeg"], help="Render engine override")

    # -- fetch --
    sub.add_parser("fetch", help="Fetch a new Reddit post")

    # -- videos --
    sub.add_parser("videos", help="List generated videos")

    # -- posts --
    sub.add_parser("posts", help="List fetched posts")

    # -- url --
    p_url = sub.add_parser("url", help="Generate from a Reddit URL")
    p_url.add_argument("reddit_url", help="Full Reddit post URL")
    p_url.add_argument("--mode", choices=["story", "qa"], help="Content mode")
    p_url.add_argument("--video-mode", choices=["reel", "short_reel", "full"], help="Video format")
    p_url.add_argument("--engine", choices=["moviepy", "ffmpeg"], help="Render engine override")
    p_url.add_argument("--no-tts", action="store_true", help="Skip TTS generation")

    args = parser.parse_args()

    config = load_config()

    # ── Non-interactive commands ──
    if args.command in ("pipeline", "run"):
        # Apply overrides
        if args.mode:
            config.setdefault("formatting", {})["default_mode"] = args.mode
        if args.video_mode:
            config.setdefault("video", {})["mode"] = args.video_mode
        if args.engine:
            config.setdefault("video", {})["engine"] = args.engine
        run_full_pipeline(config, post_id=args.post_id)
        return

    elif args.command == "fetch":
        step_fetch_post(config)
        return

    elif args.command == "videos":
        list_videos()
        return

    elif args.command == "posts":
        folders = list_posts()
        if not folders:
            rprint("No posts found.", style="yellow")
        else:
            for i, pid in enumerate(folders, 1):
                title = _post_title(pid)
                rprint(f"  {i}. {pid} — {title[:60]}")
        return

    elif args.command == "url":
        import re as _re
        match = _re.search(r'/comments/([a-z0-9]+)', args.reddit_url)
        if not match:
            rprint("Could not extract post ID from URL.", style="red")
            sys.exit(1)
        post_id = match.group(1)

        # Fetch the post via RedditStoryMaker
        try:
            from reddit_story_maker import RedditStoryMaker
            maker = RedditStoryMaker()
            # Build the .json URL
            url = args.reddit_url.rstrip('/')
            if not url.endswith('.json'):
                url += '/.json'
            full_data = maker.fetch_post_details(url)
            if not full_data:
                rprint("Failed to fetch post data.", style="red")
                sys.exit(1)
            post_data = full_data[0]['data']['children'][0]['data']
            maker.save_post_data(post_id, post_data, full_data)
            maker.used_posts.append(post_id)
            maker._save_used_posts()
        except Exception as e:
            rprint(f"Error fetching URL: {e}", style="red")
            sys.exit(1)

        # Apply overrides
        if args.mode:
            config.setdefault("formatting", {})["default_mode"] = args.mode
        if args.video_mode:
            config.setdefault("video", {})["mode"] = args.video_mode
        if args.engine:
            config.setdefault("video", {})["engine"] = args.engine
        if args.no_tts:
            config.setdefault("tts", {})["enabled"] = False

        run_full_pipeline(config, post_id=post_id)
        return

    # ── No command → interactive TUI ──
    rprint_header("Reddit Reel Maker")
    if USE_RICH:
        rprint("[dim]Rich TUI active[/dim]")
    else:
        rprint("(plain text mode — install 'rich' for a nicer UI)")

    while True:
        print()
        rprint("1. Fetch New Post", style="bold")
        rprint("2. Run Full Pipeline")
        rprint("3. Run Pipeline on Existing Post")
        rprint("4. Edit Config")
        rprint("5. List Videos")
        rprint("6. Exit")

        choice = _prompt_int("> ", 1, 6)

        if choice == 1:
            step_fetch_post(config)
        elif choice == 2:
            run_full_pipeline(config)
        elif choice == 3:
            pid = browse_posts()
            if pid:
                run_full_pipeline(config, post_id=pid)
        elif choice == 4:
            edit_config(config)
            config = load_config()
        elif choice == 5:
            list_videos()
        elif choice == 6:
            rprint("Goodbye!", style="bold green")
            break


if __name__ == "__main__":
    main()
