"""
FastAPI server that wraps the Reddit Video Generator pipeline.
Provides REST endpoints for the frontend dashboard.

Run with: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import asyncio
import os
import sys
import json
import time
import shutil
import re
import glob
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Import existing backend modules
from reddit_story_maker import RedditStoryMaker
from story_formatter import StoryFormatter
from tts_engine import TTSManager, LazyPyTikTokTTS
from local_tts import (
    check_vibevoice, install_vibevoice, VibeVoiceTTS, discover_vibevoice_voices, VIBEVOICE_MODELS,
    check_qwen3tts, install_qwen3tts, Qwen3TTS, QWEN3_TTS_MODELS,
)
# ── State ────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "dist"))
        candidates.append(os.path.join(meipass, "frontend_dist"))
    candidates.append(os.path.join(PROJECT_ROOT, "frontend_dist"))
    candidates.append(os.path.join(PROJECT_ROOT, "dist"))
    FRONTEND_DIST = None
    for c in candidates:
        if os.path.isdir(c):
            FRONTEND_DIST = c
            break
    if FRONTEND_DIST is None:
        FRONTEND_DIST = os.path.join(PROJECT_ROOT, "dist")
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND_DIST = os.path.join(PROJECT_ROOT, "dist")
FRONTEND_ASSETS = os.path.join(FRONTEND_DIST, "assets")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
CONFIG_EXAMPLE_PATH = os.path.join(PROJECT_ROOT, "config.json.example")

DEFAULT_CONFIG = {
    "subreddits": ["AskReddit"],
    "request_delay": 2.0,
    "filters": {
        "min_upvotes": 50, "min_comments": 10, "max_comments": 999999999,
        "min_age_hours": 1, "max_age_hours": 168,
        "allow_nsfw": False, "require_selftext": False,
    },
    "formatting": {"default_mode": "qa", "max_comments": 10, "min_comment_score": 10},
    "tts": {
        "enabled": True, "provider": "streamlabs_polly", "main_voice": "Matthew",
        "use_multiple_voices": True,
        "comment_voices": ["Brian","Amy","Emma","Joanna","Matthew","Joey","Justin","Kendra","Kimberly","Salli"],
        "output_format": "mp3", "speed": 0.5,
    },
    "video": {
        "mode": "short_reel", "use_gpu": True, "auto_cleanup": False,
        "threads": 0, "engine": "ffmpeg", "split_duration": 30,
        "outro_text": "Follow for Part {next_part}",
        "branding": "",
    },
    "output": {"posts_directory": "posts", "used_posts_file": "used_posts.json"},
    "discord": {"enabled": True, "webhook_url": "", "upload_media": True},
    "gemini": {
        "enabled": False,
        "api_key": "",
        "openrouter_api_key": "",
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "generate_hook": True,
        "generate_thumbnail_text": True,
        "gemini_models": [
            "gemini-2.0-flash", "gemini-2.5-flash-preview-05-20",
            "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-lite",
        ],
        "openrouter_models": [
            "google/gemma-3-27b-it:free", "google/gemma-3-12b-it:free",
            "google/gemma-3-4b-it:free", "google/gemma-3-1b-it:free",
            "google/gemini-2.0-flash-exp:free", "google/gemini-2.5-flash-preview:thinking",
            "deepseek/deepseek-chat-v3-0324:free", "meta-llama/llama-4-maverick:free",
            "qwen/qwen3-235b-a22b:free", "mistralai/mistral-small-3.1-24b-instruct:free",
        ],
        "ollama_url": "http://localhost:11434",
        "ollama_models": [
            "llama3.2", "llama3.1", "gemma3", "gemma2",
            "mistral", "qwen2.5", "phi3", "deepseek-r1",
        ],
        "nvidia_nim_api_key": "",
        "nvidia_nim_models": [
            "meta/llama-3.1-405b-instruct", "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct", "google/gemma-2-27b-it",
            "google/gemma-2-9b-it", "mistralai/mixtral-8x22b-instruct-v0.1",
            "nvidia/llama-3.1-nemotron-70b-instruct", "deepseek-ai/deepseek-r1",
        ],
    },
}

pipeline_state = {
    "steps": [
        {"id": "ai_generate", "title": "AI Content Generation", "status": "idle", "detail": ""},
        {"id": "fetch", "title": "Fetch Reddit Post", "status": "idle", "detail": ""},
        {"id": "format", "title": "Format Story", "status": "idle", "detail": ""},
        {"id": "tts", "title": "Generate TTS Audio", "status": "idle", "detail": ""},
        {"id": "video", "title": "Render Video", "status": "idle", "detail": ""},
        {"id": "thumbnail", "title": "Generate Thumbnails", "status": "idle", "detail": ""},
        {"id": "notify", "title": "Notify & Upload", "status": "idle", "detail": ""},
    ],
    "is_running": False,
    "current_post": None,
    "started_at": None,
    "completed_at": None,
    "error": None,
}

# Cancellation flag
_cancel_requested = False

videos_db: List[Dict] = []
stats = {
    "videos_today": 0, "posts_scanned": 0,
    "total_render_time_s": 0, "total_runs": 0, "successful_runs": 0,
}
run_logs: List[str] = []


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    run_logs.append(entry)
    if len(run_logs) > 500:
        run_logs.pop(0)
    print(entry)


def _ensure_config():
    if os.path.exists(CONFIG_PATH):
        return
    if os.path.exists(CONFIG_EXAMPLE_PATH):
        shutil.copy2(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
        _log("Created config.json from config.json.example")
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        _log("Created config.json with default values")


def _load_config() -> dict:
    _ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _get_video_file_info(post_id: str) -> dict:
    """Get file size and paths for a video entry."""
    posts_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    paths = []
    total_size = 0

    # Check posts dir
    if os.path.isdir(posts_dir):
        for f in os.listdir(posts_dir):
            if f.endswith(".mp4"):
                fp = os.path.join(posts_dir, f)
                paths.append(fp)
                total_size += os.path.getsize(fp)

    # Check videos dir
    if os.path.isdir(videos_dir):
        for item in os.listdir(videos_dir):
            item_path = os.path.join(videos_dir, item)
            if item == post_id and os.path.isdir(item_path):
                for f in os.listdir(item_path):
                    if f.endswith(".mp4"):
                        fp = os.path.join(item_path, f)
                        paths.append(fp)
                        total_size += os.path.getsize(fp)
            elif item.endswith(".mp4") and post_id in item:
                paths.append(item_path)
                total_size += os.path.getsize(item_path)

    return {"paths": paths, "total_size": total_size}


def _load_videos_from_disk():
    posts_dir = os.path.join(PROJECT_ROOT, "posts")
    if not os.path.exists(posts_dir):
        return
    for post_id in os.listdir(posts_dir):
        post_dir = os.path.join(posts_dir, post_id)
        if not os.path.isdir(post_dir):
            continue
        summary_path = os.path.join(post_dir, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            # Check for video files (video.mp4 or video_part*.mp4)
            has_video = os.path.exists(os.path.join(post_dir, "video.mp4"))
            if not has_video:
                has_video = any(f.startswith("video_part") and f.endswith(".mp4") for f in os.listdir(post_dir))
            has_audio = os.path.exists(os.path.join(post_dir, "audio"))
            file_info = _get_video_file_info(post_id)
            mp4s = [f for f in os.listdir(post_dir) if f.endswith(".mp4")]
            # Use video file mtime for created_at if no downloaded_at
            created_at = summary.get("downloaded_at", "")
            if not created_at:
                # Use the most recent file modification time
                all_files = file_info["paths"] if file_info["paths"] else [os.path.join(post_dir, f) for f in os.listdir(post_dir)]
                mtimes = [os.path.getmtime(f) for f in all_files if os.path.exists(f)]
                if mtimes:
                    created_at = datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()

            videos_db.append({
                "id": post_id,
                "title": summary.get("title", "Untitled"),
                "subreddit": summary.get("subreddit", "unknown"),
                "score": summary.get("score", 0),
                "num_comments": summary.get("num_comments", 0),
                "status": "published" if has_video else ("audio_only" if has_audio else "fetched"),
                "created_at": created_at,
                "has_video": has_video,
                "has_audio": has_audio,
                "parts": len(mp4s) if len(mp4s) > 1 else None,
                "file_size_bytes": file_info["total_size"] or None,
                "video_paths": file_info["paths"],
            })
    # Also check videos/ directory
    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    if os.path.exists(videos_dir):
        for item in os.listdir(videos_dir):
            item_path = os.path.join(videos_dir, item)
            if os.path.isdir(item_path):
                mp4s = [f for f in os.listdir(item_path) if f.endswith(".mp4")]
                if mp4s and not any(v["id"] == item for v in videos_db):
                    total_size = sum(os.path.getsize(os.path.join(item_path, f)) for f in mp4s)
                    video_paths = [os.path.join(item_path, f) for f in mp4s]
                    # Use file mtime for created_at
                    mtimes = [os.path.getmtime(os.path.join(item_path, f)) for f in mp4s]
                    vid_created_at = datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat() if mtimes else ""

                    videos_db.append({
                        "id": item,
                        "title": item.replace("_", " "),
                        "subreddit": "—",
                        "score": 0, "num_comments": 0,
                        "status": "published",
                        "created_at": vid_created_at,
                        "has_video": True, "has_audio": True,
                        "parts": len(mp4s) if len(mp4s) > 1 else None,
                        "file_size_bytes": total_size or None,
                        "video_paths": video_paths,
                    })


def _load_used_posts() -> List[str]:
    config = _load_config()
    used_file = os.path.join(PROJECT_ROOT, config.get("output", {}).get("used_posts_file", "used_posts.json"))
    if os.path.exists(used_file):
        with open(used_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_config()
    _load_videos_from_disk()
    _log("Server started")
    yield


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(title="Reddit Video Engine API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ── Endpoints ────────────────────────────────────────────────────────

if os.path.isdir(FRONTEND_ASSETS):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")


@app.get("/api/health")
async def health():
    return {"status": "online", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/config")
async def get_config():
    return _load_config()


@app.post("/api/ai/test")
async def test_ai_model(req: dict):
    """Test the AI model with a sample prompt to verify connectivity."""
    provider = req.get("provider", "gemini")
    model = req.get("model", "gemini-2.0-flash")
    api_key = req.get("api_key", "")
    ollama_url = req.get("ollama_url", "http://localhost:11434")

    if provider not in ("ollama",) and not api_key:
        # For nvidia_nim, check nvidia_nim-specific key too
        if provider == "nvidia_nim":
            api_key = req.get("nvidia_nim_api_key", req.get("api_key", ""))
        if not api_key:
            raise HTTPException(400, "API key is required")

    try:
        from gemini_hooks import _call_ai
        sample_prompt = "Write a one-sentence hook for a story about a neighbor's strange midnight ritual."
        system_prompt = "You are a short-form video scriptwriter. Write a punchy 1-sentence hook. Output ONLY the hook text."

        result = await asyncio.to_thread(_call_ai, provider, api_key, sample_prompt, system_prompt, model, ollama_url)

        if result:
            _log(f"AI test successful ({provider}/{model})")
            return {"success": True, "response": result}
        else:
            _log(f"AI test returned empty ({provider}/{model})")
            raise HTTPException(502, "Model returned empty response — check API key and model availability")
    except HTTPException:
        raise
    except Exception as e:
        _log(f"AI test failed ({provider}/{model}): {e}")
        raise HTTPException(502, f"AI test failed: {str(e)}")


@app.put("/api/config")
async def update_config(update: dict):
    config = _load_config()
    def deep_merge(base, overlay):
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
    deep_merge(config, update)
    _save_config(config)
    _log("Config updated")
    return {"success": True, "config": config}


@app.get("/api/posts/discover")
async def discover_posts(sort: str = "hot"):
    try:
        maker = RedditStoryMaker()
        subreddits = maker.config.get("subreddits", [])
        if not subreddits and "subreddit" in maker.config:
            subreddits = [maker.config["subreddit"]]

        all_posts = []
        for subreddit in subreddits:
            posts = maker.fetch_subreddit_posts(subreddit=subreddit, limit=25, sort=sort)
            for post in posts:
                meets, reason = maker._meets_filters(post)
                created_utc = post.get("created_utc", 0)
                age_hours = (time.time() - created_utc) / 3600
                all_posts.append({
                    "id": post.get("id"), "title": post.get("title", ""),
                    "subreddit": post.get("subreddit", ""), "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "selftext": (post.get("selftext", "") or "")[:300],
                    "url": post.get("url", ""), "permalink": post.get("permalink", ""),
                    "age_hours": round(age_hours, 1), "over_18": post.get("over_18", False),
                    "meets_filters": meets,
                    "filter_reason": reason if not meets else None,
                    "already_used": post.get("id") in maker.used_posts,
                })
        stats["posts_scanned"] += len(all_posts)
        _log(f"Discovered {len(all_posts)} posts from {len(subreddits)} subreddits")
        return {"posts": all_posts, "total": len(all_posts)}
    except Exception as e:
        _log(f"Discover error: {e}")
        raise HTTPException(500, str(e))


# ── Post Comments ─────────────────────────────────────────────────────

@app.post("/api/posts/comments")
async def get_post_comments(req: dict = {}):
    """Fetch comments for a Reddit post. Accepts URL or post_id. Returns comments for selection."""
    url = req.get("url", "").strip()
    post_id = req.get("post_id", "").strip()

    # Extract post_id from URL if given
    if url and not post_id:
        match = re.search(r'/comments/([a-z0-9]+)', url)
        if match:
            post_id = match.group(1)
        else:
            match = re.search(r'redd\.it/([a-z0-9]+)', url)
            if match:
                post_id = match.group(1)

    if not post_id:
        raise HTTPException(400, "Could not determine post ID")

    try:
        # Check if post already exists on disk
        post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
        if os.path.exists(post_dir) and os.path.exists(os.path.join(post_dir, "full_data.json")):
            formatter = StoryFormatter(post_id)
        else:
            # Fetch from Reddit first
            maker = RedditStoryMaker()
            post_url = f"https://www.reddit.com/comments/{post_id}"
            full_data = await asyncio.to_thread(maker.fetch_post_details, post_url)
            if not full_data:
                raise HTTPException(502, "Could not fetch post from Reddit")
            post_data = full_data[0]["data"]["children"][0]["data"] if isinstance(full_data, list) else full_data
            post_obj = {
                "id": post_id, "title": post_data.get("title", ""),
                "author": post_data.get("author", ""), "subreddit": post_data.get("subreddit", ""),
                "score": post_data.get("score", 0), "upvote_ratio": post_data.get("upvote_ratio", 0),
                "url": post_data.get("url", ""), "permalink": post_data.get("permalink", ""),
                "selftext": post_data.get("selftext", ""), "num_comments": post_data.get("num_comments", 0),
                "over_18": post_data.get("over_18", False), "is_video": post_data.get("is_video", False),
                "created_utc": post_data.get("created_utc", 0),
            }
            await asyncio.to_thread(maker.save_post_data, post_id, post_obj, full_data)
            formatter = StoryFormatter(post_id)

        comments = formatter.get_all_comments(min_score=0)
        title = formatter.summary.get("title", "")
        return {
            "post_id": post_id,
            "title": title,
            "comments": [
                {
                    "index": i,
                    "author": c["author"],
                    "body": c["body"],
                    "score": c["score"],
                    "char_count": len(c["body"]),
                }
                for i, c in enumerate(comments)
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        _log(f"Comments fetch error: {e}")
        raise HTTPException(500, str(e))

# ── Pipeline ──────────────────────────────────────────────────────────

@app.get("/api/pipeline/status")
async def pipeline_status():
    return pipeline_state


@app.post("/api/pipeline/run")
async def run_pipeline(req: dict = {}):
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Pipeline is already running")
    post_id = req.get("post_id")
    selected_comments = req.get("selected_comments")  # optional list of indices
    max_comment_chars = req.get("max_comment_chars", 0)
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)
    # Skip AI step for Reddit pipeline
    _set_step("ai_generate", "done", "Reddit mode — skipped")
    pipeline_state["is_running"] = True
    pipeline_state["error"] = None
    pipeline_state["current_post"] = None
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["completed_at"] = None
    _log(f"Pipeline started" + (f" for post {post_id}" if post_id else ""))
    asyncio.create_task(_run_pipeline_async(post_id, selected_comments=selected_comments, max_comment_chars=max_comment_chars))
    return {"started": True}


@app.post("/api/pipeline/run-url")
async def run_pipeline_from_url(req: dict = {}):
    """Run the pipeline from a specific Reddit URL with custom preferences."""
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Pipeline is already running")
    
    url = req.get("url", "").strip()
    if not url:
        raise HTTPException(400, "URL is required")
    
    post_id = None
    match = re.search(r'/comments/([a-z0-9]+)', url)
    if match:
        post_id = match.group(1)
    else:
        match = re.search(r'redd\.it/([a-z0-9]+)', url)
        if match:
            post_id = match.group(1)
    
    if not post_id:
        raise HTTPException(400, "Could not extract post ID from URL. Use a valid Reddit post URL.")
    
    video_mode = req.get("video_mode")
    format_mode = req.get("format_mode")
    tts_enabled = req.get("tts_enabled")
    selected_comments = req.get("selected_comments")  # list of indices
    max_comment_chars = req.get("max_comment_chars", 0)
    
    config = _load_config()
    if video_mode:
        config.setdefault("video", {})["mode"] = video_mode
    if format_mode:
        config.setdefault("formatting", {})["default_mode"] = format_mode
    if tts_enabled is not None:
        config.setdefault("tts", {})["enabled"] = tts_enabled
    _save_config(config)
    
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)
    _set_step("ai_generate", "done", "Reddit URL mode — skipped")
    pipeline_state["is_running"] = True
    pipeline_state["error"] = None
    pipeline_state["current_post"] = None
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["completed_at"] = None
    _log(f"Pipeline started from URL for post {post_id} (mode={video_mode}, format={format_mode})")
    asyncio.create_task(_run_pipeline_async(post_id, selected_comments=selected_comments, max_comment_chars=max_comment_chars))
    return {"started": True}


@app.post("/api/pipeline/run-custom")
async def run_pipeline_custom(req: dict = {}):
    """Run the pipeline from user-provided custom story or Q&A content."""
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Pipeline is already running")

    title = req.get("title", "").strip()
    content = req.get("content", "").strip()
    format_mode = req.get("format_mode", "story")
    video_mode = req.get("video_mode", "short_reel")
    tts_enabled = req.get("tts_enabled", True)
    comments = req.get("comments", [])  # list of {author, body} for Q&A

    if not title:
        raise HTTPException(400, "Title is required")
    if not content:
        raise HTTPException(400, "Content is required")

    # Create a synthetic post directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    post_id = f"custom_{timestamp}"
    post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
    os.makedirs(post_dir, exist_ok=True)

    # Write summary.json (same structure the pipeline expects)
    summary = {
        "id": post_id,
        "title": title,
        "author": "custom",
        "subreddit": "Custom",
        "score": 0,
        "upvote_ratio": 1.0,
        "url": "",
        "permalink": "",
        "selftext": content,
        "num_comments": len(comments),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(post_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write full_data.json for the formatter
    full_children = []
    for i, c in enumerate(comments):
        full_children.append({
            "kind": "t1",
            "data": {
                "author": c.get("author", f"User{i+1}"),
                "body": c.get("body", ""),
                "score": c.get("score", 1),
                "stickied": False,
            }
        })

    full_data = [
        {
            "kind": "Listing",
            "data": {
                "children": [{
                    "kind": "t3",
                    "data": {
                        "id": post_id, "title": title, "author": "custom",
                        "subreddit": "Custom", "score": 0, "upvote_ratio": 1.0,
                        "url": "", "permalink": "", "selftext": content,
                        "num_comments": len(comments),
                    }
                }]
            }
        },
        {
            "kind": "Listing",
            "data": {"children": full_children}
        },
    ]
    with open(os.path.join(post_dir, "full_data.json"), "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2)

    # Update config for this run
    config = _load_config()
    if video_mode:
        config.setdefault("video", {})["mode"] = video_mode
    if format_mode:
        config.setdefault("formatting", {})["default_mode"] = format_mode
    if tts_enabled is not None:
        config.setdefault("tts", {})["enabled"] = tts_enabled
    _save_config(config)

    # Start pipeline
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)
    _set_step("ai_generate", "done", "Custom content — skipped")
    pipeline_state["is_running"] = True
    pipeline_state["error"] = None
    pipeline_state["current_post"] = {"id": post_id, "title": title, "subreddit": "Custom", "score": 0}
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["completed_at"] = None
    _log(f"Pipeline started from custom content: {title[:60]} (mode={format_mode})")

    # Run pipeline — the fetch step will find summary.json on disk and skip Reddit fetch
    asyncio.create_task(_run_pipeline_async(post_id))
    return {"started": True}


@app.post("/api/pipeline/run-ai")
async def run_pipeline_ai(req: dict = {}):
    """Run the pipeline using AI-generated content (story, Q&A, interactive, hot take)."""
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Pipeline is already running")

    content_style = req.get("content_style", "story")
    niche = req.get("niche", "relationship_drama")
    custom_topic = req.get("custom_topic")
    interactive_format = req.get("interactive_format", "put_a_finger_down")
    video_mode = req.get("video_mode", "short_reel")
    tts_enabled = req.get("tts_enabled", True)

    config = _load_config()
    gemini_cfg = config.get("gemini", {})
    if not gemini_cfg.get("enabled", False):
        raise HTTPException(400, "AI is not enabled. Enable it in Config → AI Hooks first.")

    # Start pipeline steps and mark AI generation as running
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)
    pipeline_state["is_running"] = True
    pipeline_state["error"] = None
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["completed_at"] = None

    provider_name = gemini_cfg.get("provider", "gemini")
    model_name = gemini_cfg.get("model", "")
    _set_step("ai_generate", "running", f"Generating {content_style} content...", [
        {"label": f"Style: {content_style}", "status": "running", "detail": ""},
        {"label": f"Niche: {niche}", "status": "pending", "detail": ""},
        {"label": f"Provider: {provider_name} / {model_name}", "status": "pending", "detail": ""},
    ])

    # Generate content using AI
    try:
        from ai_content_generator import AIContentGenerator
        generator = AIContentGenerator(config)
        _log(f"Generating AI content: style={content_style}, niche={niche}")

        content_data = await asyncio.to_thread(
            generator.generate, content_style, niche, custom_topic, interactive_format
        )
        if not content_data:
            _set_step("ai_generate", "error", "AI returned empty content after retries")
            pipeline_state["is_running"] = False
            pipeline_state["error"] = "AI failed to generate content after retries"
            pipeline_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            return {"started": False, "error": "AI failed to generate content"}
    except Exception as e:
        _set_step("ai_generate", "error", f"AI generation failed: {str(e)[:80]}")
        pipeline_state["is_running"] = False
        pipeline_state["error"] = str(e)
        pipeline_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        _log(f"AI content generation error: {e}")
        raise HTTPException(502, f"AI content generation failed: {str(e)}")

    _set_step("ai_generate", "done", f"Generated: {content_data.get('title', '')[:60]}", [
        {"label": f"Style: {content_style}", "status": "done", "detail": ""},
        {"label": f"Niche: {niche}", "status": "done", "detail": ""},
        {"label": f"Provider: {provider_name}", "status": "done", "detail": "✓ content ready"},
    ])

    # Create synthetic post directory (same structure as custom pipeline)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    post_id = f"ai_{content_style}_{timestamp}"
    post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
    os.makedirs(post_dir, exist_ok=True)

    title = content_data.get("title", "AI Generated Content")

    # Build selftext based on content style
    if content_style == "interactive":
        segments = content_data.get("segments", [])
        body_parts = []
        for seg in segments:
            body_parts.append(seg.get("text", ""))
            pause = seg.get("pause_seconds", 0)
            if pause > 0:
                body_parts.append(f"[PAUSE:{pause}]")
        selftext = "\n\n".join(body_parts)
        format_mode = "story"
    elif content_style == "qa":
        selftext = content_data.get("question", content_data.get("title", ""))
        format_mode = "qa"
    else:
        selftext = content_data.get("body", "")
        format_mode = "story"

    # Write summary.json
    summary = {
        "id": post_id, "title": title, "author": "AI",
        "subreddit": f"AI/{niche}", "score": 0, "upvote_ratio": 1.0,
        "url": "", "permalink": "", "selftext": selftext,
        "num_comments": len(content_data.get("comments", [])),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "ai_generated": True, "content_style": content_style, "niche": niche,
    }
    with open(os.path.join(post_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write full_data.json
    comments_children = []
    for i, c in enumerate(content_data.get("comments", [])):
        comments_children.append({
            "kind": "t1",
            "data": {
                "author": c.get("author", f"user_{i+1}"),
                "body": c.get("body", ""), "score": c.get("score", 1), "stickied": False,
            }
        })

    full_data = [
        {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": {
            "id": post_id, "title": title, "author": "AI",
            "subreddit": f"AI/{niche}", "score": 0, "upvote_ratio": 1.0,
            "url": "", "permalink": "", "selftext": selftext,
            "num_comments": len(comments_children),
        }}]}},
        {"kind": "Listing", "data": {"children": comments_children}},
    ]
    with open(os.path.join(post_dir, "full_data.json"), "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2)

    # Update config for this run
    if video_mode:
        config.setdefault("video", {})["mode"] = video_mode
    config.setdefault("formatting", {})["default_mode"] = format_mode
    if tts_enabled is not None:
        config.setdefault("tts", {})["enabled"] = tts_enabled
    _save_config(config)

    pipeline_state["current_post"] = {"id": post_id, "title": title, "subreddit": f"AI/{niche}", "score": 0}
    _log(f"AI pipeline started: {content_style} / {niche} — {title[:60]}")

    asyncio.create_task(_run_pipeline_async(post_id))
    return {"started": True}


async def reset_pipeline():
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Cannot reset while running")
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)
    pipeline_state["current_post"] = None
    pipeline_state["error"] = None
    pipeline_state["started_at"] = None
    pipeline_state["completed_at"] = None
    _log("Pipeline reset")
    return {"success": True}


@app.post("/api/pipeline/cancel")
async def cancel_pipeline():
    global _cancel_requested
    if not pipeline_state["is_running"]:
        raise HTTPException(400, "Pipeline is not running")
    _cancel_requested = True
    _log("Pipeline cancellation requested")
    return {"success": True}


@app.post("/api/pipeline/resume-video")
async def resume_video_from_audio(req: dict = {}):
    """Resume video generation from an existing post that has audio but no video."""
    if pipeline_state["is_running"]:
        raise HTTPException(409, "Pipeline is already running")

    post_id = req.get("post_id", "").strip()
    if not post_id:
        raise HTTPException(400, "post_id is required")

    post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
    audio_dir = os.path.join(post_dir, "audio")
    summary_path = os.path.join(post_dir, "summary.json")

    if not os.path.isdir(audio_dir):
        raise HTTPException(404, f"No audio directory found for post {post_id}")
    if not os.path.exists(summary_path):
        raise HTTPException(404, f"No summary.json found for post {post_id}")

    # Read summary
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    title = summary.get("title", post_id)

    # Rebuild timeline from audio files
    audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith(('.mp3', '.wav', '.m4a'))])
    if not audio_files:
        raise HTTPException(404, "No audio files found in audio directory")

    timeline = []
    for af in audio_files:
        timeline.append({
            "text": "",  # Text not needed for video, just audio
            "audio_path": os.path.join(audio_dir, af),
            "author": summary.get("author", "Anonymous"),
        })

    # Try to load formatted text to populate segment texts
    for mode_file in ["story_mode.txt", "qa_mode.txt"]:
        txt_path = os.path.join(post_dir, mode_file)
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            for i, seg in enumerate(timeline):
                if i < len(lines):
                    seg["text"] = lines[i]
            break

    # Reset pipeline state
    for step in pipeline_state["steps"]:
        step["status"] = "idle"
        step["detail"] = ""
        step.pop("sub_steps", None)

    # Mark completed steps
    _set_step("ai_generate", "done", "Resumed — skipped")
    _set_step("fetch", "done", f"Resumed: {title[:60]}")
    _set_step("format", "done", "Using existing formatted text")
    _set_step("tts", "done", f"Using {len(timeline)} existing audio segments")

    pipeline_state["is_running"] = True
    pipeline_state["error"] = None
    pipeline_state["current_post"] = {
        "id": post_id, "title": title,
        "subreddit": summary.get("subreddit", ""),
        "score": summary.get("score", 0),
    }
    pipeline_state["started_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_state["completed_at"] = None
    _log(f"Resuming video from audio: {post_id} — {title[:60]} ({len(timeline)} segments)")

    asyncio.create_task(_resume_video_async(post_id, title, timeline))
    return {"started": True}


async def _resume_video_async(post_id: str, title: str, timeline: list):
    """Resume pipeline from video step using existing audio timeline."""
    start_time = time.time()
    config = _load_config()
    generated_video_paths = []

    try:
        video_config = config.get("video", {})
        video_mode = video_config.get("mode", "reel")
        use_gpu = video_config.get("use_gpu", False)
        hw_accel = video_config.get("hw_accel", "nvenc" if use_gpu else "none")
        engine = video_config.get("engine", "moviepy")
        threads = video_config.get("threads", 0)
        branding = video_config.get("branding", "")

        # ── Video Step ──────────────────────────────────────────────
        _set_step("video", "running", "Rendering video from existing audio...")
        _log("Rendering video (resumed)...")

        from video_generator import VideoGenerator
        video_gen = VideoGenerator(mode=video_mode, use_gpu=use_gpu, threads=threads, hw_accel=hw_accel)
        output_base = os.path.join(PROJECT_ROOT, "posts", post_id)

        if video_mode == "short_reel":
            from moviepy.editor import AudioFileClip
            split_duration = video_config.get("split_duration", 30.0)
            outro_text_template = video_config.get("outro_text", "Follow for Part {next_part}")
            max_total = float(split_duration)
            tail_dur = 2.0

            parts, current, accum = [], [], 0.0
            for seg in timeline:
                try:
                    ac = AudioFileClip(seg["audio_path"])
                    dur = ac.duration
                    ac.close()
                except Exception:
                    dur = 0.0
                if accum + dur + tail_dur <= max_total:
                    current.append(seg)
                    accum += dur
                else:
                    if current:
                        parts.append(current)
                    current = [seg]
                    accum = dur
            if current:
                parts.append(current)

            video_sub_steps = [
                {"label": f"Part {idx}", "status": "pending", "detail": f"{len(ps)} segments"}
                for idx, ps in enumerate(parts, 1)
            ]
            _set_step("video", "running", f"Rendering {len(parts)} parts · engine: {engine}", video_sub_steps)

            for idx, part_segs in enumerate(parts, start=1):
                video_sub_steps[idx - 1]["status"] = "running"
                _set_step("video", "running", f"Rendering part {idx}/{len(parts)}...", video_sub_steps)
                _check_cancelled()
                part_out = os.path.join(output_base, f"video_part{idx}.mp4")
                tail_text = outro_text_template.replace("{next_part}", str(idx + 1)) if idx < len(parts) else None

                if engine == "ffmpeg":
                    vp = await asyncio.to_thread(video_gen.generate_video_ffmpeg, part_segs, part_out, tail_text, tail_dur, branding)
                else:
                    vp = await asyncio.to_thread(video_gen.generate_video, part_segs, part_out, tail_text, tail_dur, branding)

                if vp:
                    generated_video_paths.append(vp)
                    video_sub_steps[idx - 1]["status"] = "done"
                else:
                    video_sub_steps[idx - 1]["status"] = "error"
                _set_step("video", "running", f"Rendering part {idx}/{len(parts)}...", video_sub_steps)
        else:
            output_video = os.path.join(output_base, "video.mp4")
            video_sub_steps = [{"label": "Full video", "status": "running", "detail": f"{engine} engine"}]
            _set_step("video", "running", f"Rendering single video · engine: {engine}", video_sub_steps)
            if engine == "ffmpeg":
                vp = await asyncio.to_thread(video_gen.generate_video_ffmpeg, timeline, output_video, None, 0.0, branding)
            else:
                vp = await asyncio.to_thread(video_gen.generate_video, timeline, output_video, None, 0.0, branding)
            if vp:
                generated_video_paths.append(vp)
                video_sub_steps[0]["status"] = "done"
            else:
                video_sub_steps[0]["status"] = "error"

        if generated_video_paths:
            # Move to videos/
            videos_dir = os.path.join(PROJECT_ROOT, "videos")
            os.makedirs(videos_dir, exist_ok=True)
            safe_title = re.sub(r"[^\w\-_]", "_", title)
            safe_title = re.sub(r"_+", "_", safe_title)[:50].strip("_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{safe_title}_{video_mode}_{ts}"

            if len(generated_video_paths) > 1:
                series_dir = os.path.join(videos_dir, base_name)
                os.makedirs(series_dir, exist_ok=True)
                final_paths = []
                for idx, src in enumerate(generated_video_paths, 1):
                    dest = os.path.join(series_dir, f"{base_name}_part{idx}.mp4")
                    try:
                        shutil.move(src, dest)
                        final_paths.append(dest)
                    except Exception:
                        final_paths.append(src)
                generated_video_paths = final_paths
            else:
                final_dest = os.path.join(videos_dir, f"{base_name}.mp4")
                try:
                    shutil.move(generated_video_paths[0], final_dest)
                    generated_video_paths = [final_dest]
                except Exception:
                    pass

            _set_step("video", "done", f"Rendered {len(generated_video_paths)} video(s)")

            # Thumbnails
            _set_step("thumbnail", "running", "Generating thumbnails...")
            p_title = title
            p_sub = pipeline_state.get("current_post", {}).get("subreddit", "")
            p_score = pipeline_state.get("current_post", {}).get("score", 0)
            num_thumbs = len(generated_video_paths)

            try:
                if num_thumbs > 1:
                    series_dir = os.path.dirname(generated_video_paths[0])
                    for idx in range(1, num_thumbs + 1):
                        thumb_path = os.path.join(series_dir, f"thumbnail_part{idx}.png")
                        await asyncio.to_thread(video_gen.generate_thumbnail, p_title, p_sub, idx, num_thumbs, thumb_path, p_score, branding)
                elif video_mode in ("reel", "short_reel"):
                    vdir = os.path.dirname(generated_video_paths[0])
                    vbase = os.path.splitext(os.path.basename(generated_video_paths[0]))[0]
                    thumb_path = os.path.join(vdir, f"{vbase}_thumbnail.png")
                    await asyncio.to_thread(video_gen.generate_thumbnail, p_title, p_sub, 1, 1, thumb_path, p_score, branding)
                _set_step("thumbnail", "done", f"Generated {num_thumbs} thumbnail(s)")
            except Exception as e:
                _set_step("thumbnail", "error", f"Thumbnail failed: {str(e)[:80]}")
        else:
            _set_step("video", "error", "No video output")
            _set_step("thumbnail", "done", "Skipped — no video")

        # Notify
        _set_step("notify", "done", "Resume complete — notify skipped")

        # Record
        elapsed = time.time() - start_time
        stats["videos_today"] += 1
        stats["total_runs"] += 1
        stats["successful_runs"] += 1
        stats["total_render_time_s"] += elapsed

        total_size = sum(os.path.getsize(p) for p in generated_video_paths if os.path.exists(p))
        videos_db.insert(0, {
            "id": post_id,
            "title": title, "subreddit": pipeline_state["current_post"].get("subreddit", ""),
            "score": pipeline_state["current_post"].get("score", 0),
            "num_comments": 0, "status": "published" if generated_video_paths else "failed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "has_video": bool(generated_video_paths), "has_audio": True,
            "render_time_s": round(elapsed, 1),
            "parts": len(generated_video_paths) if len(generated_video_paths) > 1 else None,
            "file_size_bytes": total_size or None,
            "video_paths": list(generated_video_paths),
        })
        _log(f"Resume pipeline completed in {elapsed:.1f}s")

    except Exception as e:
        pipeline_state["error"] = str(e)
        for step in pipeline_state["steps"]:
            if step["status"] == "running":
                step["status"] = "error"
                step["detail"] = str(e)[:100]
        stats["total_runs"] += 1
        _log(f"Resume pipeline error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline_state["is_running"] = False
        pipeline_state["completed_at"] = datetime.now(timezone.utc).isoformat()


def _check_cancelled():
    """Check if cancellation was requested and raise if so."""
    global _cancel_requested
    if _cancel_requested:
        _cancel_requested = False
        raise Exception("Pipeline cancelled by user")


async def _run_pipeline_async(specific_post_id: Optional[str] = None, selected_comments: Optional[List[int]] = None, max_comment_chars: int = 0):
    """Execute the full pipeline matching main.py run_pipeline() flow."""
    global _cancel_requested
    _cancel_requested = False
    start_time = time.time()
    config = _load_config()
    mode = config.get("formatting", {}).get("default_mode", "qa")

    try:
        maker = RedditStoryMaker()

        # ── Step 1: Fetch ────────────────────────────────────────────
        _set_step("fetch", "running", "Scanning subreddits...")
        _log("Step 1: Fetching posts...")
        await asyncio.sleep(0.3)

        if specific_post_id:
            # Check if post already exists on disk
            post_dir = os.path.join(PROJECT_ROOT, "posts", specific_post_id)
            if os.path.exists(post_dir) and os.path.exists(os.path.join(post_dir, "summary.json")):
                _log(f"Using existing post: {specific_post_id}")
                try:
                    with open(os.path.join(post_dir, "summary.json"), "r", encoding="utf-8") as f:
                        summary = json.load(f)
                    pipeline_state["current_post"] = {
                        "id": specific_post_id,
                        "title": summary.get("title", ""),
                        "subreddit": summary.get("subreddit", ""),
                        "score": summary.get("score", 0),
                    }
                    post_id = specific_post_id
                    _set_step("fetch", "done", f"Using existing: {summary.get('title', '')[:60]}")
                except Exception:
                    _set_step("fetch", "error", "Could not load existing post data")
                    pipeline_state["is_running"] = False
                    return
            else:
                # Post not on disk — fetch it from Reddit
                _log(f"Post {specific_post_id} not on disk, fetching from Reddit...")
                _set_step("fetch", "running", f"Fetching post {specific_post_id} from Reddit...")
                try:
                    post_url = f"https://www.reddit.com/comments/{specific_post_id}"
                    full_data = await asyncio.to_thread(maker.fetch_post_details, post_url)

                    if not full_data:
                        _set_step("fetch", "error", f"Could not fetch post {specific_post_id} from Reddit")
                        pipeline_state["error"] = f"Post {specific_post_id} not found"
                        pipeline_state["is_running"] = False
                        return

                    # Extract post data from Reddit's response format
                    post_data = full_data[0]["data"]["children"][0]["data"] if isinstance(full_data, list) else full_data
                    post_obj = {
                        "id": specific_post_id,
                        "title": post_data.get("title", ""),
                        "author": post_data.get("author", "Anonymous"),
                        "subreddit": post_data.get("subreddit", ""),
                        "score": post_data.get("score", 0),
                        "upvote_ratio": post_data.get("upvote_ratio", 0),
                        "url": post_data.get("url", ""),
                        "permalink": post_data.get("permalink", ""),
                        "selftext": post_data.get("selftext", ""),
                        "num_comments": post_data.get("num_comments", 0),
                        "over_18": post_data.get("over_18", False),
                        "is_video": post_data.get("is_video", False),
                        "created_utc": post_data.get("created_utc", 0),
                    }
                    await asyncio.to_thread(maker.save_post_data, specific_post_id, post_obj, full_data)
                    pipeline_state["current_post"] = {
                        "id": specific_post_id,
                        "title": post_obj["title"],
                        "subreddit": post_obj["subreddit"],
                        "score": post_obj["score"],
                    }
                    post_id = specific_post_id
                    _set_step("fetch", "done", f"Fetched: {post_obj['title'][:60]}")
                    _log(f"Fetched post from Reddit: {post_obj['title'][:80]}")

                    # Mark as used
                    maker.used_posts.append(specific_post_id)
                    maker._save_used_posts()
                except Exception as e:
                    _set_step("fetch", "error", f"Fetch failed: {str(e)[:80]}")
                    _log(f"Failed to fetch post {specific_post_id}: {e}")
                    pipeline_state["error"] = str(e)
                    pipeline_state["is_running"] = False
                    return
        else:
            # Full fetch flow: find_suitable_post → fetch_post_details → save_post_data
            post = await asyncio.to_thread(maker.find_suitable_post)
            if not post:
                _set_step("fetch", "error", "No suitable posts found")
                pipeline_state["is_running"] = False
                pipeline_state["error"] = "No suitable posts found"
                _log("No suitable post found")
                return

            post_id = post.get("id")
            post_url = post.get("url")
            pipeline_state["current_post"] = {
                "id": post_id,
                "title": post.get("title"),
                "subreddit": post.get("subreddit"),
                "score": post.get("score"),
            }
            _set_step("fetch", "done", f"Found: {post.get('title', '')[:60]}...")
            _log(f"Selected post: {post.get('title', '')[:80]}")

            # Fetch full details and save
            _log("Fetching post details and comments...")
            full_data = await asyncio.to_thread(maker.fetch_post_details, post_url)
            if full_data:
                await asyncio.to_thread(maker.save_post_data, post_id, post, full_data)
            else:
                _log("Warning: Could not fetch full post details")

            # Mark as used
            maker.used_posts.append(post_id)
            maker._save_used_posts()

        _check_cancelled()

        # ── Step 2: Format ───────────────────────────────────────────
        _set_step("format", "running", "Formatting story for narration...")
        _log("Step 2: Formatting story...")
        try:
            formatter = await asyncio.to_thread(StoryFormatter, post_id)
            # Save both formatted text files
            await asyncio.to_thread(formatter.save_formatted_story, "story")
            await asyncio.to_thread(formatter.save_formatted_story, "qa")
            title = formatter.summary.get("title", "")
            selftext = formatter.summary.get("selftext", "")
            author = formatter.summary.get("author", "Anonymous")
            _set_step("format", "done", "Story & Q&A text formatted")
            _log("Story formatted (story_mode.txt + qa_mode.txt)")
        except Exception as e:
            _set_step("format", "error", f"Format failed: {str(e)[:80]}")
            _log(f"Format error: {e}")
            pipeline_state["error"] = str(e)
            pipeline_state["is_running"] = False
            pipeline_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            return

        _check_cancelled()

        # ── Step 2.5: Gemini Hooks (between format and TTS) ──────────
        gemini_hook_text = None
        gemini_thumbnail_text = None
        gemini_cfg = config.get("gemini", {})
        if gemini_cfg.get("enabled", False) and gemini_cfg.get("api_key", ""):
            _log("Step 2.5: Generating Gemini hooks...")
            try:
                from gemini_hooks import generate_hooks
                # Build comments context for hook generation
                comments_ctx = ""
                if mode == "qa":
                    max_c = config.get("formatting", {}).get("max_comments", 10)
                    min_s = config.get("formatting", {}).get("min_comment_score", 10)
                    top_comments = formatter._extract_top_comments(max_c, min_s)
                    comments_ctx = "\n".join(c.get("body", "")[:200] for c in top_comments[:5])

                gemini_hook_text, gemini_thumbnail_text = await asyncio.to_thread(
                    generate_hooks, config, title, selftext, comments_ctx
                )
                if gemini_hook_text:
                    _log(f"Gemini hook: \"{gemini_hook_text[:80]}\"")
                if gemini_thumbnail_text:
                    _log(f"Gemini thumbnail: \"{gemini_thumbnail_text[:60]}\"")
            except Exception as e:
                _log(f"Gemini hooks failed (non-fatal): {e}")

        _check_cancelled()

        # ── Step 3: TTS ──────────────────────────────────────────────
        _set_step("tts", "running", "Generating speech audio...")
        _log("Step 3: Generating TTS audio...")
        timeline = []
        try:
            tts_manager = TTSManager()
            if not tts_manager.enabled:
                _set_step("tts", "done", "TTS disabled in config — skipped")
                _log("TTS is disabled in config, skipping")
            else:
                tts_config = config.get("tts", {})
                main_voice = tts_config.get("main_voice", "Matthew")
                multi_voice = tts_config.get("use_multiple_voices", True)
                comment_voices = tts_config.get("comment_voices", [])
                provider = tts_config.get("provider", "streamlabs_polly")
                model_size = tts_config.get("model_size", "")

                # Get comments for Q&A mode only
                if mode == "story":
                    comments = []
                else:
                    max_comments_cfg = config.get("formatting", {}).get("max_comments", 10)
                    min_score = config.get("formatting", {}).get("min_comment_score", 10)
                    all_comments = formatter._extract_top_comments(max_comments_cfg, min_score)
                    # Apply char limit filter
                    if max_comment_chars and max_comment_chars > 0:
                        all_comments = [c for c in all_comments if len(c.get("body", "")) <= max_comment_chars]
                    # Apply selection filter
                    if selected_comments is not None:
                        comments = [all_comments[i] for i in selected_comments if 0 <= i < len(all_comments)]
                    else:
                        comments = all_comments

                post_body = selftext if mode == "story" or selftext else ""

                # Initial sub-steps (will be replaced with real-time progress)
                _set_step("tts", "running", f"Calculating segments · provider: {provider}", [
                    {"label": "Analyzing text...", "status": "running", "detail": ""}
                ])
                _log(f"Generating full narrative: {len(comments)} comments, mode={mode}, provider={provider}")

                # For local TTS providers, use different engine classes
                if provider == "vibevoice":
                    audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
                    vv_model = model_size if model_size and model_size.startswith("vibevoice") else "vibevoice-0.5b"
                    tts_instance = VibeVoiceTTS(voice=main_voice, model_size=vv_model, output_dir=audio_dir, cancel_check=_check_cancelled)
                    _log(f"Using VibeVoice local TTS engine (model={vv_model})")
                elif provider == "qwen3_tts":
                    audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
                    q_model = model_size if model_size and model_size.startswith("qwen3") else "qwen3-tts-1.7b"
                    tts_instance = Qwen3TTS(voice=main_voice, model_size=q_model, output_dir=audio_dir, cancel_check=_check_cancelled)
                    _log(f"Using Qwen3-TTS local engine (model={q_model})")
                elif provider == "lazypy_tiktok":
                    audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
                    tts_instance = LazyPyTikTokTTS(voice=main_voice, output_dir=audio_dir, cancel_check=_check_cancelled)
                    _log(f"Using TikTok TTS via LazyPy (voice={main_voice})")

                # Real-time progress tracking
                tts_sub_steps_live = []
                last_phase = [None]

                def _tts_progress(phase, current, total, detail):
                    """Called from TTS thread after each segment."""
                    if phase != last_phase[0]:
                        # New phase: mark previous as done, add new
                        if tts_sub_steps_live:
                            tts_sub_steps_live[-1]["status"] = "done"
                        voice_label = main_voice
                        if phase.startswith("Comment"):
                            ci = int(phase.split(" ")[1]) - 1
                            if multi_voice and comment_voices:
                                author = comments[ci].get("author", "Anon") if ci < len(comments) else "Anon"
                                voice_label = comment_voices[hash(author) % len(comment_voices)]
                        tts_sub_steps_live.append({
                            "label": f"{phase} — voice: {voice_label}",
                            "status": "running",
                            "detail": f"seg {current}/{total}"
                        })
                        last_phase[0] = phase
                    else:
                        # Update current phase progress
                        if tts_sub_steps_live:
                            tts_sub_steps_live[-1]["detail"] = f"seg {current}/{total} — {detail}"
                    _set_step("tts", "running", f"Segment {current}/{total} · {phase}", list(tts_sub_steps_live))

                # Use the appropriate TTS engine
                if provider in ("vibevoice", "qwen3_tts", "lazypy_tiktok"):
                    # Local TTS or LazyPy TikTok: generate segments directly
                    timeline = await asyncio.to_thread(
                        _generate_local_tts_narrative,
                        tts_instance, post_id, title, post_body, author, comments,
                        _tts_progress, _check_cancelled
                    )
                else:
                    # Streamlabs or other TTSManager-based providers
                    timeline = await asyncio.to_thread(
                        tts_manager.generate_full_narrative,
                        post_id, title, post_body, author, comments,
                        progress_callback=_tts_progress,
                        cancel_check=_check_cancelled
                    )

                # Prepend Gemini hook to the start of the timeline
                if gemini_hook_text and timeline:
                    _log("Prepending Gemini hook to audio timeline...")
                    hook_audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
                    os.makedirs(hook_audio_dir, exist_ok=True)

                    # Generate TTS for the hook using the same provider
                    hook_seg = None
                    if provider in ("vibevoice", "qwen3_tts", "lazypy_tiktok"):
                        hook_seg_list = await asyncio.to_thread(
                            tts_instance.generate_segments, gemini_hook_text, None, _check_cancelled
                        )
                        if hook_seg_list:
                            for s in hook_seg_list:
                                s["author"] = author
                            hook_seg = hook_seg_list
                    else:
                        from tts_engine import StreamlabsTTS
                        hook_tts = StreamlabsTTS(voice=main_voice, output_dir=hook_audio_dir, cancel_check=_check_cancelled)
                        hook_seg_list = await asyncio.to_thread(
                            hook_tts.generate_segments, gemini_hook_text, None, _check_cancelled
                        )
                        if hook_seg_list:
                            for s in hook_seg_list:
                                s["author"] = author
                            hook_seg = hook_seg_list

                    if hook_seg:
                        timeline = hook_seg + timeline
                        _log(f"Hook prepended ({len(hook_seg)} segments)")

                if timeline:
                    for ss in tts_sub_steps_live:
                        ss["status"] = "done"
                    _set_step("tts", "done", f"Generated {len(timeline)} audio segments", tts_sub_steps_live)
                    _log(f"TTS complete: {len(timeline)} segments")
                else:
                    for ss in tts_sub_steps_live:
                        ss["status"] = "error"
                    _set_step("tts", "error", "No audio segments generated", tts_sub_steps_live)
                    _log("TTS produced no segments")
        except Exception as e:
            if "cancelled" in str(e).lower():
                _set_step("tts", "error", "Cancelled by user")
                _log("TTS cancelled by user")
                raise  # Re-raise to stop pipeline
            _set_step("tts", "error", f"TTS failed: {str(e)[:80]}")
            _log(f"TTS error: {e}")

        _check_cancelled()

        # ── Step 4: Video ────────────────────────────────────────────
        _set_step("video", "running", "Rendering video...")
        _log("Step 4: Rendering video...")
        video_config = config.get("video", {})
        video_mode = video_config.get("mode", "reel")
        use_gpu = video_config.get("use_gpu", False)
        hw_accel = video_config.get("hw_accel", "nvenc" if use_gpu else "none")
        engine = video_config.get("engine", "moviepy")
        threads = video_config.get("threads", 0)
        auto_cleanup = video_config.get("auto_cleanup", False)

        generated_video_paths = []

        if not timeline:
            _set_step("video", "error", "No audio timeline — cannot render video")
            _log("Video skipped: no audio timeline available")
        else:
            try:
                from video_generator import VideoGenerator
                video_gen = VideoGenerator(mode=video_mode, use_gpu=use_gpu, threads=threads, hw_accel=hw_accel)
                output_base = os.path.join(PROJECT_ROOT, "posts", post_id)

                if video_mode == "short_reel":
                    # Split into parts based on split_duration
                    from moviepy.editor import AudioFileClip
                    split_duration = video_config.get("split_duration", 30.0)
                    outro_text_template = video_config.get("outro_text", "Follow for Part {next_part}")
                    max_total = float(split_duration)
                    tail_dur = 2.0

                    parts, current, accum = [], [], 0.0
                    for seg in timeline:
                        try:
                            ac = AudioFileClip(seg["audio_path"])
                            dur = ac.duration
                            ac.close()
                        except Exception:
                            dur = 0.0
                        if accum + dur + tail_dur <= max_total:
                            current.append(seg)
                            accum += dur
                        else:
                            if current:
                                parts.append(current)
                            current = [seg]
                            accum = dur
                    if current:
                        parts.append(current)

                    _log(f"Split into {len(parts)} video parts (max {split_duration}s each)")
                    video_sub_steps = [
                        {"label": f"Part {idx}", "status": "pending", "detail": f"{len(ps)} segments"}
                        for idx, ps in enumerate(parts, 1)
                    ]
                    _set_step("video", "running", f"Rendering {len(parts)} parts · engine: {engine}", video_sub_steps)

                    branding = config.get("video", {}).get("branding", "")

                    for idx, part_segs in enumerate(parts, start=1):
                        video_sub_steps[idx - 1]["status"] = "running"
                        _set_step("video", "running", f"Rendering part {idx}/{len(parts)}...", video_sub_steps)
                        _log(f"Rendering part {idx}/{len(parts)}...")
                        _check_cancelled()
                        part_out = os.path.join(output_base, f"video_part{idx}.mp4")
                        tail_text = None
                        if idx < len(parts):
                            tail_text = outro_text_template.replace("{next_part}", str(idx + 1))

                        if engine == "ffmpeg":
                            vp = await asyncio.to_thread(video_gen.generate_video_ffmpeg, part_segs, part_out, tail_text, tail_dur, branding)
                        else:
                            vp = await asyncio.to_thread(video_gen.generate_video, part_segs, part_out, tail_text, tail_dur, branding)

                        if vp:
                            generated_video_paths.append(vp)
                            video_sub_steps[idx - 1]["status"] = "done"
                        else:
                            video_sub_steps[idx - 1]["status"] = "error"
                        _set_step("video", "running", f"Rendering part {idx}/{len(parts)}...", video_sub_steps)
                else:
                    # Single video output
                    branding = config.get("video", {}).get("branding", "")
                    output_video = os.path.join(output_base, "video.mp4")
                    video_sub_steps = [{"label": "Full video", "status": "running", "detail": f"{engine} engine · {len(timeline)} segments"}]
                    _set_step("video", "running", f"Rendering single video · engine: {engine}", video_sub_steps)
                    _log(f"Rendering single video ({engine} engine)...")
                    if engine == "ffmpeg":
                        vp = await asyncio.to_thread(video_gen.generate_video_ffmpeg, timeline, output_video, None, 0.0, branding)
                    else:
                        vp = await asyncio.to_thread(video_gen.generate_video, timeline, output_video, None, 0.0, branding)
                    if vp:
                        generated_video_paths.append(vp)
                        video_sub_steps[0]["status"] = "done"
                    else:
                        video_sub_steps[0]["status"] = "error"

                if generated_video_paths:
                    # Move to videos/ directory (matching main.py behavior)
                    videos_dir = os.path.join(PROJECT_ROOT, "videos")
                    os.makedirs(videos_dir, exist_ok=True)
                    safe_title = re.sub(r"[^\w\-_]", "_", title)
                    safe_title = re.sub(r"_+", "_", safe_title)[:50].strip("_")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base_name = f"{safe_title}_{video_mode}_{timestamp}"

                    if len(generated_video_paths) > 1:
                        series_dir = os.path.join(videos_dir, base_name)
                        os.makedirs(series_dir, exist_ok=True)
                        final_paths = []
                        for idx, src in enumerate(generated_video_paths, 1):
                            dest = os.path.join(series_dir, f"{base_name}_part{idx}.mp4")
                            try:
                                shutil.move(src, dest)
                                final_paths.append(dest)
                            except Exception:
                                final_paths.append(src)
                        generated_video_paths = final_paths
                    else:
                        final_dest = os.path.join(videos_dir, f"{base_name}.mp4")
                        try:
                            shutil.move(generated_video_paths[0], final_dest)
                            generated_video_paths = [final_dest]
                        except Exception:
                            pass

                    _set_step("video", "done", f"Rendered {len(generated_video_paths)} video(s)")
                    _log(f"Video complete: {len(generated_video_paths)} file(s)")

                    # Auto cleanup
                    if auto_cleanup:
                        post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
                        try:
                            shutil.rmtree(post_dir)
                            _log(f"Cleaned up post workspace: {post_dir}")
                        except Exception as e:
                            _log(f"Cleanup warning: {e}")
                else:
                    _set_step("video", "error", "Video generation produced no output")
                    _log("Video generation failed — no output files")

            except ImportError as e:
                _set_step("video", "done", f"Video module not available — skipped ({e})")
                _log(f"Video skipped (import error): {e}")
            except Exception as e:
                _set_step("video", "error", f"Render failed: {str(e)[:80]}")
                _log(f"Video error: {e}")
                import traceback
                traceback.print_exc()

        _check_cancelled()

        # ── Step 5: Thumbnails ───────────────────────────────────────
        _set_step("thumbnail", "running", "Generating thumbnails...")
        _log("Step 5: Generating thumbnails...")
        if not generated_video_paths:
            _set_step("thumbnail", "done", "No videos — skipped")
            _log("Thumbnails skipped: no video output")
        else:
            try:
                from video_generator import VideoGenerator
                if 'video_gen' not in dir():
                    video_gen = VideoGenerator(mode=video_mode, use_gpu=use_gpu, threads=threads, hw_accel=hw_accel)
                branding = config.get("video", {}).get("branding", "")
                p_title = pipeline_state.get("current_post", {}).get("title", title) if pipeline_state.get("current_post") else title
                p_sub = pipeline_state.get("current_post", {}).get("subreddit", "") if pipeline_state.get("current_post") else ""
                p_score = pipeline_state.get("current_post", {}).get("score", 0) if pipeline_state.get("current_post") else 0
                thumb_title_override = gemini_thumbnail_text if gemini_thumbnail_text else None

                thumb_sub_steps = []
                num_thumbs = len(generated_video_paths)

                if num_thumbs > 1:
                    series_dir = os.path.dirname(generated_video_paths[0])
                    for idx in range(1, num_thumbs + 1):
                        thumb_sub_steps.append({"label": f"Part {idx}", "status": "pending", "detail": ""})
                    _set_step("thumbnail", "running", f"Generating {num_thumbs} thumbnails...", thumb_sub_steps)
                    for idx in range(1, num_thumbs + 1):
                        thumb_sub_steps[idx - 1]["status"] = "running"
                        _set_step("thumbnail", "running", f"Thumbnail {idx}/{num_thumbs}...", thumb_sub_steps)
                        thumb_path = os.path.join(series_dir, f"thumbnail_part{idx}.png")
                        await asyncio.to_thread(
                            video_gen.generate_thumbnail,
                            p_title, p_sub, idx, num_thumbs, thumb_path, p_score, branding,
                            thumb_title_override
                        )
                        thumb_sub_steps[idx - 1]["status"] = "done"
                        _set_step("thumbnail", "running", f"Thumbnail {idx}/{num_thumbs}...", thumb_sub_steps)
                else:
                    if video_mode in ("reel", "short_reel"):
                        thumb_sub_steps = [{"label": "Single thumbnail", "status": "running", "detail": ""}]
                        _set_step("thumbnail", "running", "Generating thumbnail...", thumb_sub_steps)
                        # Determine path
                        vdir = os.path.dirname(generated_video_paths[0])
                        vbase = os.path.splitext(os.path.basename(generated_video_paths[0]))[0]
                        thumb_path = os.path.join(vdir, f"{vbase}_thumbnail.png")
                        await asyncio.to_thread(
                            video_gen.generate_thumbnail,
                            p_title, p_sub, 1, 1, thumb_path, p_score, branding,
                            thumb_title_override
                        )
                        thumb_sub_steps[0]["status"] = "done"
                    else:
                        thumb_sub_steps = [{"label": "Full mode — skipped", "status": "done", "detail": ""}]

                _set_step("thumbnail", "done", f"Generated {num_thumbs} thumbnail(s)", thumb_sub_steps)
                _log(f"Thumbnails complete: {num_thumbs}")
            except Exception as e:
                _set_step("thumbnail", "error", f"Thumbnail failed: {str(e)[:80]}")
                _log(f"Thumbnail error: {e}")

        _check_cancelled()

        # ── Step 6: Discord Notify ───────────────────────────────────
        _set_step("notify", "running", "Sending notification...")
        _log("Step 6: Discord notification...")
        discord_conf = config.get("discord", {})
        if not discord_conf.get("enabled"):
            _set_step("notify", "done", "Discord disabled — skipped")
            _log("Discord notifications disabled")
        elif not discord_conf.get("webhook_url"):
            _set_step("notify", "done", "No webhook URL configured — skipped")
            _log("No Discord webhook URL")
        else:
            try:
                from discord_notifier import DiscordNotifier
                notifier = DiscordNotifier(discord_conf["webhook_url"])
                upload_media = discord_conf.get("upload_media", True)

                fields = [
                    {"name": "Mode", "value": video_mode, "inline": True},
                    {"name": "Parts", "value": str(len(generated_video_paths)), "inline": True},
                    {"name": "Engine", "value": engine, "inline": True},
                ]
                await asyncio.to_thread(
                    notifier.send_embed,
                    "🎬 New Video Ready",
                    f"**{title}**\n\nVideo generation complete.",
                    fields,
                )

                if upload_media and generated_video_paths:
                    for vp in generated_video_paths:
                        await asyncio.to_thread(notifier.send_file, vp)

                _set_step("notify", "done", "Discord notified")
                _log("Discord notification sent")
            except Exception as e:
                _set_step("notify", "error", f"Notify failed: {str(e)[:80]}")
                _log(f"Discord error: {e}")

        # ── Done ─────────────────────────────────────────────────────
        elapsed = time.time() - start_time
        stats["videos_today"] += 1
        stats["total_runs"] += 1
        stats["successful_runs"] += 1
        stats["total_render_time_s"] += elapsed

        # Use actual generated paths (not _get_video_file_info which can't find moved files)
        total_size = sum(os.path.getsize(p) for p in generated_video_paths if os.path.exists(p))
        videos_db.insert(0, {
            "id": post_id,
            "title": title or post_id,
            "subreddit": pipeline_state["current_post"].get("subreddit", "") if pipeline_state["current_post"] else "",
            "score": pipeline_state["current_post"].get("score", 0) if pipeline_state["current_post"] else 0,
            "num_comments": 0,
            "status": "published" if generated_video_paths else "audio_only" if timeline else "fetched",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "has_video": bool(generated_video_paths),
            "has_audio": bool(timeline),
            "render_time_s": round(elapsed, 1),
            "parts": len(generated_video_paths) if len(generated_video_paths) > 1 else None,
            "file_size_bytes": total_size or None,
            "video_paths": list(generated_video_paths),
        })
        _log(f"Pipeline completed in {elapsed:.1f}s")

    except Exception as e:
        pipeline_state["error"] = str(e)
        for step in pipeline_state["steps"]:
            if step["status"] == "running":
                step["status"] = "error"
                step["detail"] = str(e)[:100]
        stats["total_runs"] += 1
        _log(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline_state["is_running"] = False
        pipeline_state["completed_at"] = datetime.now(timezone.utc).isoformat()


def _set_step(step_id: str, status: str, detail: str = "", sub_steps: Optional[List[Dict]] = None):
    for step in pipeline_state["steps"]:
        if step["id"] == step_id:
            step["status"] = status
            step["detail"] = detail
            if sub_steps is not None:
                step["sub_steps"] = sub_steps
            break


def _generate_local_tts_narrative(tts_instance, post_id, title, body, author, comments, progress_callback, cancel_check):
    """Generate full narrative using a local TTS engine (VibeVoice or Qwen3)."""
    timeline = []
    total_segments = 0
    current_segment = 0

    # Pre-calculate total segments
    title_segs = tts_instance.segment_text(title)
    body_segs = tts_instance.segment_text(body) if body and body.strip() else []
    comment_seg_counts = [len(tts_instance.segment_text(c.get("body", ""))) for c in comments]
    total_segments = len(title_segs) + len(body_segs) + sum(comment_seg_counts)

    def _make_progress(phase):
        def _cb(current_in_phase, total_in_phase, seg_text):
            nonlocal current_segment
            current_segment += 1
            if progress_callback:
                progress_callback(phase, current_segment, total_segments, f"({current_in_phase}/{total_in_phase}) {seg_text[:40]}")
        return _cb

    # Title
    title_segments = tts_instance.generate_segments(title, progress_callback=_make_progress("Title"), cancel_check=cancel_check)
    for seg in title_segments:
        seg["author"] = author
        timeline.append(seg)

    # Body
    if body and body.strip():
        body_segments = tts_instance.generate_segments(body, progress_callback=_make_progress("Body"), cancel_check=cancel_check)
        for seg in body_segments:
            seg["author"] = author
            timeline.append(seg)

    # Comments
    for i, comment in enumerate(comments):
        if cancel_check:
            cancel_check()
        comment_body = comment.get("body", "")
        comment_author = comment.get("author", "Anonymous")
        comment_segments = tts_instance.generate_segments(comment_body, progress_callback=_make_progress(f"Comment {i+1}"), cancel_check=cancel_check)
        for seg in comment_segments:
            seg["author"] = comment_author
            timeline.append(seg)

    return timeline


# ── Videos ────────────────────────────────────────────────────────────

@app.get("/api/videos")
async def list_videos():
    safe = []
    for v in videos_db:
        entry = {k: val for k, val in v.items() if k != "video_paths"}
        # Add a list of part filenames so the frontend knows what's available
        paths = v.get("video_paths", [])
        entry["part_files"] = [os.path.basename(p) for p in paths if os.path.exists(p)]
        # Check for thumbnails alongside video files
        entry["has_thumbnails"] = False
        if paths:
            first_dir = os.path.dirname(paths[0]) if paths[0] else None
            if first_dir and os.path.isdir(first_dir):
                entry["has_thumbnails"] = any(f.endswith(".png") and "thumbnail" in f for f in os.listdir(first_dir))
        safe.append(entry)
    return {"videos": safe}


def _find_thumbnail_files(video_id: str) -> List[str]:
    """Return all thumbnail PNG paths for a video, sorted by name."""
    paths = []
    entry = _find_video_entry(video_id)
    if entry and entry.get("video_paths"):
        # Thumbnails live alongside videos
        dirs_checked = set()
        for vp in entry["video_paths"]:
            d = os.path.dirname(vp)
            if d and d not in dirs_checked and os.path.isdir(d):
                dirs_checked.add(d)
                for f in sorted(os.listdir(d)):
                    if f.endswith(".png") and "thumbnail" in f:
                        paths.append(os.path.join(d, f))
    # Also check videos/ root for single-video thumbnails
    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    if os.path.isdir(videos_dir):
        for f in sorted(os.listdir(videos_dir)):
            if f.endswith(".png") and "thumbnail" in f and video_id in f:
                fp = os.path.join(videos_dir, f)
                if fp not in paths:
                    paths.append(fp)
    return sorted(paths)


@app.get("/api/videos/{video_id}/thumbnail")
async def get_thumbnail(video_id: str, part: int = 0):
    """Serve a thumbnail image for a video part (0-indexed)."""
    thumbs = _find_thumbnail_files(video_id)
    if not thumbs:
        raise HTTPException(404, "No thumbnails found")
    if part < 0 or part >= len(thumbs):
        raise HTTPException(404, f"Thumbnail part {part} not found. Available: 0-{len(thumbs)-1}")
    return FileResponse(thumbs[part], media_type="image/png")


def _find_video_entry(video_id: str):
    for v in videos_db:
        if v["id"] == video_id:
            return v
    return None


def _find_all_video_files(video_id: str) -> List[str]:
    """Return all mp4 paths for a video, sorted by name."""
    paths = set()
    entry = _find_video_entry(video_id)
    if entry and entry.get("video_paths"):
        for p in entry["video_paths"]:
            if os.path.exists(p):
                paths.add(p)

    # Fallback: search posts and videos dirs
    search_dirs = [os.path.join(PROJECT_ROOT, "posts", video_id)]
    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    if os.path.isdir(videos_dir):
        search_dirs.append(videos_dir)
        for sub in os.listdir(videos_dir):
            sub_path = os.path.join(videos_dir, sub)
            if os.path.isdir(sub_path) and video_id in sub:
                search_dirs.append(sub_path)

    for d in search_dirs:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".mp4"):
                    paths.add(os.path.join(d, f))

    return sorted(paths)


@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str, part: int = 0):
    """Stream a specific part (0-indexed). Defaults to first part."""
    all_files = _find_all_video_files(video_id)
    if not all_files:
        raise HTTPException(404, "Video file not found")
    if part < 0 or part >= len(all_files):
        raise HTTPException(404, f"Part {part} not found. Available: 0-{len(all_files)-1}")
    return FileResponse(all_files[part], media_type="video/mp4")


@app.get("/api/videos/{video_id}/download")
async def download_video(video_id: str, part: int = 0):
    """Download a specific part (0-indexed). Defaults to first part."""
    all_files = _find_all_video_files(video_id)
    if not all_files:
        raise HTTPException(404, "Video file not found")
    if part < 0 or part >= len(all_files):
        raise HTTPException(404, f"Part {part} not found. Available: 0-{len(all_files)-1}")
    path = all_files[part]
    filename = os.path.basename(path)
    return FileResponse(path, media_type="video/mp4", filename=filename)


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    # Remove from in-memory db
    global videos_db
    videos_db = [v for v in videos_db if v["id"] != video_id]

    # Remove files from disk
    deleted = False
    post_dir = os.path.join(PROJECT_ROOT, "posts", video_id)
    if os.path.isdir(post_dir):
        shutil.rmtree(post_dir)
        deleted = True
        _log(f"Deleted post dir: {post_dir}")

    videos_dir = os.path.join(PROJECT_ROOT, "videos")
    if os.path.isdir(videos_dir):
        for item in os.listdir(videos_dir):
            item_path = os.path.join(videos_dir, item)
            if video_id in item:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                deleted = True
                _log(f"Deleted video: {item_path}")

    if not deleted:
        _log(f"No files found for video {video_id}")

    return {"success": True}


@app.get("/api/used-posts")
async def get_used_posts():
    return {"used_posts": _load_used_posts()}


@app.get("/api/logs")
async def get_logs():
    return {"logs": run_logs[-100:]}


@app.get("/api/stats")
async def get_stats():
    avg_render = round(stats["total_render_time_s"] / stats["total_runs"]) if stats["total_runs"] > 0 else 0
    success_rate = round(stats["successful_runs"] / stats["total_runs"] * 100) if stats["total_runs"] > 0 else 0
    return {
        "videos_today": stats["videos_today"],
        "posts_scanned": stats["posts_scanned"],
        "avg_render_time_s": avg_render,
        "success_rate": success_rate,
        "total_runs": stats["total_runs"],
    }


# ── TTS Provider Management ─────────────────────────────────────────

@app.get("/api/tts/providers")
async def tts_providers():
    """List available TTS providers and their install status."""
    return {
        "providers": [
            {
                "id": "streamlabs_polly",
                "name": "Streamlabs Polly",
                "type": "cloud",
                "installed": True,
                "details": "Free, no setup required",
                "voices": ["Brian", "Amy", "Emma", "Joanna", "Matthew", "Joey", "Justin", "Kendra", "Kimberly", "Salli"],
            },
            {
                "id": "lazypy_tiktok",
                "name": "TikTok (LazyPy)",
                "type": "cloud",
                "installed": True,
                "details": "Free TikTok voices via lazypy.ro, no setup required",
                "voices": LazyPyTikTokTTS.AVAILABLE_VOICES,
            },
            {
                "id": "vibevoice",
                "name": "Microsoft VibeVoice",
                "type": "local",
                **check_vibevoice(),
                "voices": VibeVoiceTTS.get_available_voices(),
                "voices_detailed": discover_vibevoice_voices(),
                "models": [
                    {"id": k, **{mk: mv for mk, mv in v.items() if mk != "hf_id"}}
                    for k, v in VIBEVOICE_MODELS.items()
                ],
            },
            {
                "id": "qwen3_tts",
                "name": "Qwen3 TTS",
                "type": "local",
                **check_qwen3tts(),
                "voices": Qwen3TTS.AVAILABLE_VOICES,
                "models": [
                    {"id": k, **{mk: mv for mk, mv in v.items() if mk != "hf_id"}}
                    for k, v in QWEN3_TTS_MODELS.items()
                ],
            },
        ]
    }


@app.get("/", include_in_schema=False)
async def frontend_index():
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(404, "Frontend build not found. Run pnpm build to create dist or place frontend_dist next to the executable.")


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_catch_all(full_path: str):
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(404, "Frontend build not found. Run pnpm build to create dist or place frontend_dist next to the executable.")


if __name__ == "__main__":
    import uvicorn
    import webbrowser

    url = "http://127.0.0.1:8000"
    webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=8000)


@app.post("/api/tts/install/{provider_id}")
async def install_tts_provider(provider_id: str):
    """Install a local TTS provider."""
    _log(f"Installing TTS provider: {provider_id}")
    if provider_id == "vibevoice":
        result = await asyncio.to_thread(install_vibevoice)
    elif provider_id == "qwen3_tts":
        result = await asyncio.to_thread(install_qwen3tts)
    else:
        raise HTTPException(400, f"Unknown provider: {provider_id}")
    
    if result["success"]:
        _log(f"TTS provider {provider_id} installed successfully")
    else:
        _log(f"TTS provider {provider_id} install failed: {result.get('error', 'unknown')}")
    return result


@app.get("/api/tts/check/{provider_id}")
async def check_tts_provider(provider_id: str):
    """Check install status of a specific TTS provider."""
    if provider_id == "vibevoice":
        return check_vibevoice()
    elif provider_id == "qwen3_tts":
        return check_qwen3tts()
    elif provider_id == "streamlabs_polly":
        return {"installed": True, "details": "Always available"}
    elif provider_id == "lazypy_tiktok":
        return {"installed": True, "details": "Free TikTok voices via lazypy.ro"}
    else:
        raise HTTPException(400, f"Unknown provider: {provider_id}")
