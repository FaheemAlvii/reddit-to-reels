"""
Reddit Story Maker - Main Orchestrator

This script coordinates the entire pipeline:
1. Fetching a suitable post from Reddit
2. Formatting it for narration
3. Generating TTS audio

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import os
import sys
import json
import argparse
import time
from typing import Optional

# Import modules from the same directory
try:
    from reddit_story_maker import RedditStoryMaker
    from story_formatter import StoryFormatter
    from generate_tts import generate_audio_for_post
except ImportError:
    # Handle running from root
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from reddit_story_maker import RedditStoryMaker
    from story_formatter import StoryFormatter
    from generate_tts import generate_audio_for_post

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(filename: str = "config.json") -> dict:
    config_path = os.path.join(PROJECT_ROOT, filename)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def run_pipeline(mode: Optional[str] = None, target_post_id: Optional[str] = None):
    """
    Run the complete story making pipeline.
    """
    print("=" * 60)
    print("Reddit Story Maker - Pipeline")
    print("=" * 60)
    
    # 1. Load config to check defaults
    config = load_config()
    if not mode:
        mode = config.get('formatting', {}).get('default_mode', 'qa')
    
    print(f"\nMode: {mode.upper()}")
    
    # 2. Fetch a new post (or use existing)
    post_id = target_post_id
    
    if post_id:
        print(f"\n[Step 1] Using existing post: {post_id}")
        # Verify it exists
        post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
        if not os.path.exists(post_dir):
            print(f"❌ Post directory not found: {post_dir}")
            return False
    else:
        print(f"\n[Step 1] Fetching new post...")
        try:
            maker = RedditStoryMaker()
            post_id = maker.process_new_post()
            
            if not post_id:
                print("❌ Pipeline stopped: No suitable post found.")
                return False
                
        except Exception as e:
            print(f"❌ Error fetching post: {e}")
            return False

    # 3. Format the post
    print(f"\n[Step 2] Formatting post...")
    try:
        formatter = StoryFormatter(post_id)
        
        # Save formatted text files (useful reference even if TTS reads direct)
        story_path = formatter.save_formatted_story('story')
        qa_path = formatter.save_formatted_story('qa')
        
        print(f"✓ Formatted files saved for inspection")
        
    except Exception as e:
        print(f"❌ Error formatting post: {e}")
        # Continue anyway, maybe TTS can still work if it was just a saving error
    
    # 4. Generate Audio & Video
    print(f"\n[Step 3] Generating Audio & Video ({mode.upper()} mode)...")
    try:
        # Import VideoGenerator here to avoid potential import errors if libs missing
        try:
            from tts_engine import TTSManager
            from video_generator import VideoGenerator
        except ImportError as e:
            print(f"⚠️  Missing libraries: {e}")
            from generate_tts import generate_audio_for_post
            return generate_audio_for_post(post_id, mode)
            
        # Initialize managers
        # Reload config in case it changed
        config = load_config()

        # ── Gemini Hooks (before TTS) ──
        gemini_hook_text = None
        gemini_thumbnail_text = None
        gemini_cfg = config.get("gemini", {})
        if gemini_cfg.get("enabled", False) and gemini_cfg.get("api_key", ""):
            try:
                from gemini_hooks import generate_hooks
                comments_ctx = ""
                if mode == "qa":
                    max_c = config.get("formatting", {}).get("max_comments", 10)
                    min_s = config.get("formatting", {}).get("min_comment_score", 10)
                    top_coms = formatter._extract_top_comments(max_c, min_s)
                    comments_ctx = "\n".join(c.get("body", "")[:200] for c in top_coms[:5])
                gemini_hook_text, gemini_thumbnail_text = generate_hooks(config, title, selftext, comments_ctx)
            except Exception as e:
                print(f"⚠️  Gemini hooks failed (non-fatal): {e}")

        tts_manager = TTSManager()
        
        if not tts_manager.enabled:
            print("⚠️ TTS is disabled. Skipping.")
            return True
        
        # Gather data
        title = formatter.summary.get('title', '')
        selftext = formatter.summary.get('selftext', '')
        author = formatter.summary.get('author', 'Anonymous')
        
        # Get comments/story content
        if mode == 'qa':
            max_comments = config.get('formatting', {}).get('max_comments', 10)
            min_score = config.get('formatting', {}).get('min_comment_score', 10)
            comments = formatter._extract_top_comments(max_comments, min_score)
        else:
            comments = []
            
        # Generate Audio Timeline
        timeline = tts_manager.generate_full_narrative(
            post_id=post_id,
            post_title=title,
            post_body=selftext if mode=='story' or selftext else '',
            post_author=author,
            comments=comments
        )

        # Prepend Gemini hook
        if gemini_hook_text and timeline:
            from tts_engine import StreamlabsTTS
            hook_audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
            hook_tts = StreamlabsTTS(voice=tts_manager.main_voice, output_dir=hook_audio_dir)
            hook_segs = hook_tts.generate_segments(gemini_hook_text)
            if hook_segs:
                for s in hook_segs:
                    s["author"] = author
                timeline = hook_segs + timeline
        
        if not timeline:
            print("❌ Failed to generate audio timeline.")
            return False
            
        # Generate Video
        video_config = config.get('video', {})
        video_mode = video_config.get('mode', 'reel')
        use_gpu = video_config.get('use_gpu', False)
        auto_cleanup = video_config.get('auto_cleanup', False)
        threads = video_config.get('threads', 0)
        engine = video_config.get('engine', 'moviepy')
            
        try:
            video_gen = VideoGenerator(mode=video_mode, use_gpu=use_gpu, threads=threads)
            output_base = os.path.join(PROJECT_ROOT, "posts", post_id)
            
            if video_mode == 'short_reel':
                try:
                    from moviepy.editor import AudioFileClip, VideoFileClip
                except Exception as e:
                    print(f"⚠️  Missing MoviePy components: {e}")
                    return False
                
                # Configurable parameters
                split_duration = video_config.get('split_duration', 30.0)
                outro_text_template = video_config.get('outro_text', "Follow for Part {next_part}")
                
                max_total = float(split_duration)
                tail_dur = 2.0
                parts = []
                current = []
                accum = 0.0
                for seg in timeline:
                    try:
                        ac = AudioFileClip(seg['audio_path'])
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
                generated_paths = []
                for idx, part_segs in enumerate(parts, start=1):
                    part_out = os.path.join(output_base, f"video_part{idx}.mp4")
                    tail_text = None
                    if idx < len(parts):
                        tail_text = outro_text_template.replace("{next_part}", str(idx+1))
                    if engine == 'ffmpeg':
                        vp = video_gen.generate_video_ffmpeg(part_segs, part_out, tail_text=tail_text, tail_duration=tail_dur)
                    else:
                        vp = video_gen.generate_video(part_segs, part_out, tail_text=tail_text, tail_duration=tail_dur)
                    if vp:
                        generated_paths.append(vp)
                if not generated_paths:
                    print("\n❌ Video Generation failed.")
                    return False
                print(f"\n✅ PIPELINE COMPLETE!")
                videos_dir = os.path.join(PROJECT_ROOT, "videos")
                if not os.path.exists(videos_dir):
                    os.makedirs(videos_dir)
                import re
                from datetime import datetime
                safe_title = re.sub(r'[^\w\-_]', '_', title)
                safe_title = re.sub(r'_+', '_', safe_title)
                safe_title = safe_title[:50].strip('_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = f"{safe_title}_{video_mode}_{timestamp}"
                series_dir = os.path.join(videos_dir, base_name)
                if not os.path.exists(series_dir):
                    os.makedirs(series_dir)
                import shutil
                from PIL import Image, ImageDraw, ImageFont
                final_video_paths = []
                for idx, src_path in enumerate(generated_paths, start=1):
                    dest_name = f"{base_name}_part{idx}.mp4"
                    dest_path = os.path.join(series_dir, dest_name)
                    try:
                        shutil.move(src_path, dest_path)
                    except Exception as e:
                        print(f"   ⚠️ Error moving part {idx}: {e}")
                        dest_path = src_path
                    
                    final_video_paths.append(dest_path)

                    try:
                        # Create consistent text overlay image using VideoGenerator
                        text_overlay_path = video_gen.create_text_image(
                            f"Part {idx}",
                            fontsize=100,  # Bigger font
                            color='white',
                            max_width=800,
                            use_bg_box=True,
                            bg_color='black',
                            bg_opacity=160,
                            padding=40
                        )
                        
                        clip = VideoFileClip(dest_path)
                        thumb_path = os.path.join(series_dir, f"{base_name}_part{idx}.jpg")
                        clip.save_frame(thumb_path, t=min(0.5, clip.duration/2))
                        clip.close()
                        
                        # Composite overlay onto thumbnail
                        img = Image.open(thumb_path).convert('RGBA')
                        overlay = Image.open(text_overlay_path).convert('RGBA')
                        
                        # Center overlay
                        w, h = img.size
                        ow, oh = overlay.size
                        x = (w - ow) // 2
                        y = (h - oh) // 2
                        
                        img.alpha_composite(overlay, (x, y))
                        img.convert('RGB').save(thumb_path)
                        
                        # Cleanup temp overlay
                        try:
                            os.remove(text_overlay_path)
                        except:
                            pass
                            
                    except Exception as e:
                        print(f"   ⚠️ Thumbnail error for part {idx}: {e}")
                if auto_cleanup:
                    try:
                        post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
                        shutil.rmtree(post_dir)
                        print(f"   Deleted temp folder: {post_dir}")
                    except Exception as e:
                        print(f"   ⚠️ Cleanup warning: {e}")
                print(f"   Video series: {series_dir}")
                
                # Discord Notification
                discord_conf = config.get('discord', {})
                if discord_conf.get('enabled'):
                    try:
                        print("\n📨 Sending to Discord...")
                        from discord_notifier import DiscordNotifier
                        notifier = DiscordNotifier(discord_conf.get('webhook_url'))
                        upload_media = bool(discord_conf.get('upload_media', True))
                        
                        fields = [
                            {"name": "Mode", "value": video_mode, "inline": True},
                            {"name": "Parts", "value": str(len(final_video_paths)), "inline": True},
                            {"name": "Engine", "value": engine, "inline": True}
                        ]
                        notifier.send_embed(
                            title="🎬 New Video Series Ready",
                            description=f"**{title}**\n\nVideo series generation complete.",
                            fields=fields
                        )
                        
                        if upload_media:
                            for vp in final_video_paths:
                                notifier.send_file(vp)
                    except Exception as e:
                        print(f"   ⚠️ Discord notification failed: {e}")

            else:
                output_video = os.path.join(output_base, "video.mp4")
                if engine == 'ffmpeg':
                    video_path = video_gen.generate_video_ffmpeg(timeline, output_video)
                else:
                    video_path = video_gen.generate_video(timeline, output_video)
                if video_path:
                    print(f"\n✅ PIPELINE COMPLETE!")
                if video_path:
                    print(f"\n✅ PIPELINE COMPLETE!")
                    videos_dir = os.path.join(PROJECT_ROOT, "videos")
                    if not os.path.exists(videos_dir):
                        os.makedirs(videos_dir)
                    import re
                    from datetime import datetime
                    safe_title = re.sub(r'[^\w\-_]', '_', title)
                    safe_title = re.sub(r'_+', '_', safe_title)
                    safe_title = safe_title[:50].strip('_')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    final_filename = f"{safe_title}_{video_mode}_{timestamp}.mp4"
                    final_dest = os.path.join(videos_dir, final_filename)
                    import shutil
                    try:
                        shutil.move(video_path, final_dest)
                        print(f"   Video moved to: {final_dest}")
                        video_path = final_dest
                    except Exception as e:
                        print(f"   ⚠️ Error moving video: {e}")
                    if auto_cleanup:
                        print("🧹 Cleaning up workspace...")
                        try:
                            post_dir = os.path.join(PROJECT_ROOT, "posts", post_id)
                            if os.path.exists(final_dest):
                                shutil.rmtree(post_dir)
                                print(f"   Deleted temp folder: {post_dir}")
                        except Exception as e:
                            print(f"   ⚠️ Cleanup warning: {e}")
                    print(f"   Video: {video_path}")
                    
                    # Discord Notification
                    discord_conf = config.get('discord', {})
                    if discord_conf.get('enabled'):
                        try:
                            print("\n📨 Sending to Discord...")
                            from discord_notifier import DiscordNotifier
                            notifier = DiscordNotifier(discord_conf.get('webhook_url'))
                            upload_media = bool(discord_conf.get('upload_media', True))
                            
                            fields = [
                                {"name": "Mode", "value": video_mode, "inline": True},
                                {"name": "Engine", "value": engine, "inline": True}
                            ]
                            notifier.send_embed(
                                title="🎬 New Video Ready",
                                description=f"**{title}**\n\nVideo generation complete.",
                                fields=fields
                            )
                            
                            if upload_media:
                                notifier.send_file(video_path)
                        except Exception as e:
                            print(f"   ⚠️ Discord notification failed: {e}")

                else:
                    print("\n❌ Video Generation failed.")
                    return False
                
        except Exception as e:
            print(f"❌ Error generating video: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error in media generation: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    return True


if __name__ == "__main__":
    if len(sys.argv) == 1:
        import webbrowser
        import uvicorn
        from api_server import app

        url = "http://127.0.0.1:8000"
        webbrowser.open(url)
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        parser = argparse.ArgumentParser(description="Reddit Story Maker Pipeline")
        parser.add_argument("--mode", choices=["story", "qa"], help="Override default formatting mode")
        parser.add_argument("--id", help="Process specific existing Post ID (skips fetching)")
        args = parser.parse_args()
        run_pipeline(args.mode, args.id)
