"""
Video Generator for Reddit Story Maker.
Combines audio segments with background video and synchronized subtitles.

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import os
import sys
import random
import textwrap
from typing import List, Optional

# --- Graceful moviepy / PIL imports for A-Shell / iOS compatibility ---
MOVIEPY_AVAILABLE = False
try:
    import numpy as np
    import PIL.Image
    # Monkey patch ANTIALIAS replacement for MoviePy 1.0.3 compatibility with Pillow 10+
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip,
        concatenate_audioclips, TextClip, ColorClip, vfx
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    pass  # moviepy/numpy not available – FFmpeg-only mode

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class VideoGenerator:
    """
    Generates videos from audio segments and background footage.
    """
    
    def __init__(self, mode: str = 'reel', use_gpu: bool = False, threads: int = 0, hw_accel: str = 'none'):
        """
        Initialize video generator.
        mode: 'reel' (9:16) or 'full' (16:9)
        use_gpu: Whether to use hardware encoding (legacy, overridden by hw_accel)
        threads: Number of threads for writing video (0 = auto/max)
        hw_accel: Hardware acceleration type: 'none' (CPU), 'nvenc' (NVIDIA), 'amf' (AMD)
        """
        self.mode = mode.lower()
        self.hw_accel = hw_accel if hw_accel in ('none', 'nvenc', 'amf') else ('nvenc' if use_gpu else 'none')
        self.use_gpu = self.hw_accel != 'none'
        self.threads = threads if threads and threads > 0 else os.cpu_count() or 4
        
        print(f"   ⚙️  Video Processor configured with {self.threads} threads.")
        
        if self.mode == 'reel' or self.mode == 'short_reel':
            self.width = 1080
            self.height = 1920
            self.aspect_ratio = 9/16
        else:
            self.width = 1920
            self.height = 1080
            self.aspect_ratio = 16/9
            
        self.backgrounds_dir = os.path.join(PROJECT_ROOT, "backgrounds")
        if not os.path.exists(self.backgrounds_dir):
            os.makedirs(self.backgrounds_dir)
            
    def create_text_image(self, text: str, fontsize: int = 60, color: str = 'white', 
                         bg_color: Optional[str] = None, max_width: int = 800,
                         use_bg_box: bool = False, bg_opacity: int = 255, padding: int = 40) -> str:
        """
        Create an image with text using Pillow.
        Returns path to temporary image file.
        """
        # Create a dummy image to calculate text size
        # Try to load a nicer font if available, else default
        try:
            # Arial usually exists on Windows
            font = ImageFont.truetype("arial.ttf", fontsize)
        except OSError:
            font = ImageFont.load_default()
            
        # Wrap text
        avg_char_width = fontsize * 0.5  # Rough estimate
        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        wrapped_text = "\n".join(lines)
        
        # Calculate size
        dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        bbox = dummy_draw.multiline_textbbox((0, 0), wrapped_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Add padding
        # Add padding
        # If using a background box, we might want different padding
        
        img_width = text_width + padding * 2
        img_height = text_height + padding * 2
        
        # Create image
        if use_bg_box and bg_color:
            # Create a transparent base image first
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw the semitransparent box
            # Parse hex colors if needed or assume standard names
            # Pillow doesn't handle hex with alpha well in all versions, so let's convert simple names or leave as is
            # Ideally we draw a rectangle with RGBA color
            
            box_color = None
            if bg_color.startswith('#'):
                 # Convert hex to RGB
                h = bg_color.lstrip('#')
                rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                box_color = rgb + (bg_opacity,)
            else:
                # Basic color name map or fallback
                # For simplicity, if it's 'black' or 'white'
                if bg_color.lower() == 'black':
                    box_color = (0, 0, 0, bg_opacity)
                elif bg_color.lower() == 'white':
                    box_color = (255, 255, 255, bg_opacity)
                else: 
                     # Allow Pillow to handle it, but opacity won't work easily on string names without conversion
                     # Default to black with opacity if logic fails
                     box_color = (0, 0, 0, bg_opacity)
            
            # Draw rounded rectangle (pill shape-ish)
            draw.rounded_rectangle(
                [(0, 0), (img_width, img_height)], 
                radius=20, 
                fill=box_color
            )
            
        elif bg_color:
             # Standard solid background (old behavior mostly)
             img = Image.new('RGBA', (img_width, img_height), bg_color)
             draw = ImageDraw.Draw(img)
        else:
            # Transparent background
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
        
        # Draw text (with outline/stroke for better visibility)
        stroke_width = 3 if not use_bg_box else 0 # No stroke needed if we have a box usually, but let's see
        if use_bg_box:
             stroke_width = 0 # Clean look on box
             
        stroke_color = 'black'
        
        draw.multiline_text(
            (padding, padding), 
            wrapped_text, 
            font=font, 
            fill=color, 
            align='center',
            stroke_width=stroke_width,
            stroke_fill=stroke_color
        )
        
        # Save temp file
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img.save(temp_file.name)
        temp_file.close()
        
        return temp_file.name

    def get_random_background(self, duration: float) -> VideoFileClip:
        """
        Get a random background clip of appropriate duration and aspect ratio.
        """
        video_files = [f for f in os.listdir(self.backgrounds_dir) 
                      if f.lower().endswith(('.mp4', '.mov', '.avi'))]
        
        if not video_files:
            # Create a simple color background if no videos found
            print("⚠️  No background videos found in 'backgrounds/'. Using solid color.")
            return ColorClip(size=(self.width, self.height), color=(20, 20, 30), duration=duration)
            
        bg_path = os.path.join(self.backgrounds_dir, random.choice(video_files))
        
        try:
            clip = VideoFileClip(bg_path)
            
            # Loop if shorter than duration
            if clip.duration < duration:
                clip = clip.loop(duration=duration)
            
            # Pick random start time if long enough
            if clip.duration > duration:
                max_start = clip.duration - duration
                start_time = random.uniform(0, max_start)
                clip = clip.subclip(start_time, start_time + duration)
            
            # Resize logic (Crop to fill)
            # Calculate target aspect ratio
            target_aspect = self.width / self.height
            clip_aspect = clip.w / clip.h
            
            if clip_aspect > target_aspect:
                # Clip is wider than target -> Resize by height, crop width
                new_height = self.height
                new_width = int(clip.w * (self.height / clip.h))
                clip = clip.resize(height=new_height)
                # Center crop width
                x_center = new_width / 2
                clip = clip.crop(x1=x_center - self.width/2, width=self.width, height=self.height)
            else:
                # Clip is taller than target -> Resize by width, crop height
                new_width = self.width
                new_height = int(clip.h * (self.width / clip.w))
                clip = clip.resize(width=new_width)
                # Center crop height
                y_center = new_height / 2
                clip = clip.crop(y1=y_center - self.height/2, width=self.width, height=self.height)
                
            return clip
            
        except Exception as e:
            print(f"❌ Error loading background {bg_path}: {e}")
            return ColorClip(size=(self.width, self.height), color=(20, 20, 30), duration=duration)

    def generate_video(self, audio_segments: List[dict], output_path: str, tail_text: Optional[str] = None, tail_duration: float = 0.0, branding: str = ""):
        """
        Generate final video from audio segments.
        audio_segments: List of dicts {'text': str, 'audio_path': str, 'author': str (opt)}
        """
        print(f"\n🎬 Generatiing video ({self.mode.upper()} mode)...")
        
        # 1. Prepare Audio
        audio_clips = []
        temp_images = [] # Keep track to delete later
        
        for segment in audio_segments:
            if os.path.exists(segment['audio_path']):
                ac = AudioFileClip(segment['audio_path'])
                audio_clips.append(ac)
            else:
                print(f"⚠️  Missing audio file: {segment['audio_path']}")
        
        if not audio_clips:
            print("❌ No valid audio clips found")
            return None
            
        final_audio = concatenate_audioclips(audio_clips)
        total_duration = final_audio.duration + (tail_duration if (tail_text and tail_duration and tail_duration > 0) else 0)
        
        # 2. Prepare Background
        background_clip = self.get_random_background(total_duration)
        
        # 3. Create Subtitles & Attribution
        subtitle_clips = []
        attribution_clips = []
        current_time = 0
        current_author = None
        
        total_segments = len(audio_segments)
        print(f"   Composing {total_segments} segments...")
        
        for i, segment in enumerate(audio_segments):
            # Print progress every 10 segments or for first/last
            if i % 10 == 0 or i == total_segments - 1:
                print(f"     Processing segment {i+1}/{total_segments}...")
            segment_duration = audio_clips[i].duration
            author = segment.get('author', 'Anonymous')
            
            # Subtitle
            text_img_path = self.create_text_image(
                segment['text'], 
                fontsize=70 if self.mode == 'reel' else 50,
                color='white',
                max_width=int(self.width * 0.8),
                use_bg_box=True,
                bg_color='black',
                bg_opacity=160, # Slightly more opaque
                padding=40      # Increased padding (was 20)
            )
            temp_images.append(text_img_path)
            
            # Create text clip first to get dimensions
            txt_clip = (ImageClip(text_img_path)
                       .set_start(current_time)
                       .set_duration(segment_duration)
                       .set_position(('center', 'center')))
            
            subtitle_clips.append(txt_clip)
            
            # Calculate absolute position of the centered subtitle clip
            # MoviePy uses (center, center) so top-left is:
            subtitle_w, subtitle_h = txt_clip.size
            subtitle_x = (self.width - subtitle_w) // 2
            subtitle_y = (self.height - subtitle_h) // 2
            
            # Attribution — show branding handle instead of OP for privacy
            attr_text = f"u/{branding.strip()}" if branding and branding.strip() else None
            if attr_text:
                attr_img_path = self.create_text_image(
                    attr_text,
                    fontsize=40 if self.mode == 'reel' else 30,
                    color='#FF4500',
                    max_width=int(self.width * 0.5),
                    use_bg_box=True,
                    bg_color='black',
                    bg_opacity=160,
                    padding=15
                )
                temp_images.append(attr_img_path)
                
                attr_clip_obj = ImageClip(attr_img_path)
                attr_w, attr_h = attr_clip_obj.size
                attr_pos = (subtitle_x, subtitle_y - attr_h - 10)
                attr_clip = (attr_clip_obj
                            .set_start(current_time)
                            .set_duration(segment_duration)
                            .set_position(attr_pos))
                attribution_clips.append(attr_clip)
            
            current_time += segment_duration

        if tail_text and tail_duration and tail_duration > 0:
            tail_img_path = self.create_text_image(
                tail_text,
                fontsize=70 if self.mode == 'reel' else 50,
                color='white',
                max_width=int(self.width * 0.8),
                use_bg_box=True,
                bg_color='black',
                bg_opacity=160,
                padding=40
            )
            temp_images.append(tail_img_path)
            tail_clip = (ImageClip(tail_img_path)
                        .set_start(current_time)
                        .set_duration(tail_duration)
                        .set_position(('center', 'center')))
            subtitle_clips.append(tail_clip)
        
        # 4. Branding watermark (persistent overlay)
        branding_clips = []
        if branding and branding.strip():
            brand_img_path = self.create_text_image(
                branding.strip(),
                fontsize=30,
                color='white',
                max_width=int(self.width * 0.4),
                use_bg_box=True,
                bg_color='black',
                bg_opacity=120,
                padding=12
            )
            temp_images.append(brand_img_path)
            brand_clip = (ImageClip(brand_img_path)
                         .set_duration(total_duration)
                         .set_position(('right', 'bottom'))
                         .margin(right=20, bottom=20, opacity=0))
            branding_clips.append(brand_clip)

        # 5. Composite
        final_video = CompositeVideoClip([background_clip] + subtitle_clips + attribution_clips + branding_clips)
        final_video = final_video.set_audio(final_audio)
        
        # 5. Write file
        print(f"   Writing video to: {output_path}")
        try:
            # Use unique temp audio filename in the output directory
            output_dir = os.path.dirname(output_path)
            temp_audio = os.path.join(output_dir, f"temp_audio_{random.randint(1000, 9999)}.m4a")
            
            print(f"   Writing video to: {output_path}")
            
            # Codec settings based on hw_accel
            if self.hw_accel == 'nvenc':
                print("   🚀 Using NVIDIA GPU acceleration (h264_nvenc)...")
                codec = 'h264_nvenc'
                ffmpeg_params = ['-rc', 'vbr', '-cq', '19', '-b:v', '8M', '-maxrate', '10M']
                preset = 'p4'
                bitrate = None
            elif self.hw_accel == 'amf':
                print("   🚀 Using AMD GPU acceleration (h264_amf)...")
                codec = 'h264_amf'
                ffmpeg_params = ['-rc', 'vbr_latency', '-qp_i', '19', '-qp_p', '19', '-b:v', '8M', '-maxrate', '10M']
                preset = 'speed'
                bitrate = None
            else:
                print("   Using CPU encoding (libx264)...")
                codec = 'libx264'
                ffmpeg_params = ['-crf', '18']
                preset = 'medium'
                bitrate = None
            
            final_video.write_videofile(
                output_path, 
                fps=30, # Smoother 30fps
                codec=codec, 
                audio_codec='aac',
                bitrate=bitrate,
                ffmpeg_params=ffmpeg_params,
                preset=preset,
                threads=self.threads,       # Use configured threads
                logger='bar',    # Show progress bar
                temp_audiofile=temp_audio,
                remove_temp=True
            )
            print("✓ Video generation complete!")
            
            # clean up temp images
            print("   Cleaning up temporary files...")
            for p in temp_images:
                try:
                    os.remove(p)
                except:
                    pass
            
            # Explicitly close clips to release file handles
            final_video.close()
            final_audio.close()
            background_clip.close()
            for ac in audio_clips:
                ac.close()
                    
            return output_path
            
        except Exception as e:
            print(f"❌ Error writing video: {e}")
            return None

    def create_full_frame_overlay(self, segment: dict, current_author: str, branding: str = "") -> str:
        """
        Create a single full-frame transparent PNG containing both subtitle and attribution.
        This is for the FFmpeg engine to overlay cleanly as a stream.
        """
        # 1. Create Subtitle Image
        text_img_path = self.create_text_image(
            segment['text'], 
            fontsize=70 if self.mode == 'reel' else 50,
            color='white',
            max_width=int(self.width * 0.8),
            use_bg_box=True,
            bg_color='black',
            bg_opacity=160,
            padding=40
        )
        
        # 2. Create Base Canvas
        canvas = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        
        # 3. Paste Subtitle (Center)
        sub_img = Image.open(text_img_path).convert("RGBA")
        sub_w, sub_h = sub_img.size
        sub_x = (self.width - sub_w) // 2
        sub_y = (self.height - sub_h) // 2
        canvas.alpha_composite(sub_img, (sub_x, sub_y))
        
        # 4. Create Attribution Image — use branding handle instead of OP
        include_attr = bool(branding and branding.strip())
        if include_attr:
            attr_text = f"u/{branding.strip()}"
            attr_img_path = self.create_text_image(
                attr_text,
                fontsize=40 if self.mode == 'reel' else 30,
                color='#FF4500',
                max_width=int(self.width * 0.5),
                use_bg_box=True,
                bg_color='black',
                bg_opacity=160,
                padding=15
            )
        
        # 5. Paste Attribution (Top-Left relative to subtitle)
        if include_attr:
            attr_img = Image.open(attr_img_path).convert("RGBA")
            attr_w, attr_h = attr_img.size
            attr_x = sub_x
            attr_y = sub_y - attr_h - 10
            canvas.alpha_composite(attr_img, (attr_x, attr_y))
        
        # 6. Branding watermark (bottom-right)
        if branding and branding.strip():
            brand_img_path = self.create_text_image(
                branding.strip(),
                fontsize=30,
                color='white',
                max_width=int(self.width * 0.4),
                use_bg_box=True,
                bg_color='black',
                bg_opacity=120,
                padding=12
            )
            brand_img = Image.open(brand_img_path).convert("RGBA")
            bw, bh = brand_img.size
            canvas.alpha_composite(brand_img, (self.width - bw - 20, self.height - bh - 20))
            try:
                os.remove(brand_img_path)
            except:
                pass

        # Save Full Frame
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        canvas.save(temp_file.name)
        temp_file.close()
        
        # Cleanup small parts
        try:
            os.remove(text_img_path)
            if include_attr:
                os.remove(attr_img_path)
        except:
            pass
            
        return temp_file.name

    def generate_thumbnail(self, title: str, subreddit: str, part_number: int = 1,
                           total_parts: int = 1, output_path: str = "thumbnail.png",
                           score: int = 0, branding: str = "", title_override: str = None) -> Optional[str]:
        """
        Generate a Reddit-style thumbnail for a video part.
        Card size adapts to content. Includes optional branding watermark.
        """
        print(f"   🖼️  Generating thumbnail for Part {part_number}...")
        try:
            w, h = self.width, self.height

            # 1. Background — grab a frame from a random background video or use solid
            bg_img = None
            video_files = [f for f in os.listdir(self.backgrounds_dir)
                          if f.lower().endswith(('.mp4', '.mov', '.avi'))]
            if video_files:
                bg_path = os.path.join(self.backgrounds_dir, random.choice(video_files))
                try:
                    clip = VideoFileClip(bg_path)
                    t = random.uniform(0, max(clip.duration - 1, 0))
                    frame = clip.get_frame(t)
                    clip.close()
                    bg_img = Image.fromarray(frame).resize((w, h), Image.LANCZOS)
                    from PIL import ImageFilter
                    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=12))
                    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 80))
                    bg_img = bg_img.convert('RGBA')
                    bg_img = Image.alpha_composite(bg_img, overlay)
                except Exception as e:
                    print(f"   ⚠️  Could not extract background frame: {e}")

            if bg_img is None:
                bg_img = Image.new('RGBA', (w, h), (20, 20, 30, 255))

            draw = ImageDraw.Draw(bg_img)

            # 2. Load fonts
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 52)
                font_sub = ImageFont.truetype("arial.ttf", 36)
                font_meta = ImageFont.truetype("arial.ttf", 30)
                font_brand = ImageFont.truetype("arial.ttf", 26)
            except OSError:
                try:
                    font_title = ImageFont.truetype("arial.ttf", 52)
                except OSError:
                    font_title = ImageFont.load_default()
                font_sub = font_title
                font_meta = font_title
                font_brand = font_title

            # 3. Measure content to determine dynamic card height
            card_margin_x = int(w * 0.08)
            card_w = w - card_margin_x * 2
            inner_pad = 30
            title_max_w = card_w - inner_pad * 2

            # Subreddit header height
            icon_r = 24
            header_h = icon_r * 2 + 10  # icon + gap

            # Title text measurement
            avg_char_w = 26
            chars_per_line = max(int(title_max_w / avg_char_w), 10)
            display_title = title_override if title_override else title
            if total_parts > 1 and not title_override:
                display_title = f"{title} (Part {part_number})"
            elif total_parts > 1 and title_override:
                display_title = f"{title_override} (Part {part_number})"
            lines = textwrap.wrap(display_title, width=chars_per_line)
            max_lines = 6
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = lines[-1][:len(lines[-1])-3] + "..."
            wrapped = "\n".join(lines)
            title_bbox = draw.multiline_textbbox((0, 0), wrapped, font=font_title, spacing=8)
            title_text_h = title_bbox[3] - title_bbox[1]

            # Bottom bar height
            bottom_bar_h = 40

            # Calculate total card height dynamically
            card_h = inner_pad + header_h + 20 + title_text_h + 25 + bottom_bar_h + inner_pad
            card_h = max(card_h, int(h * 0.18))  # minimum height
            card_h = min(card_h, int(h * 0.55))  # maximum height

            card_y = (h - card_h) // 2
            card_x = card_margin_x

            # 4. Draw rounded white card
            card_rect = [(card_x, card_y), (card_x + card_w, card_y + card_h)]
            draw.rounded_rectangle(card_rect, radius=30, fill=(255, 255, 255, 240))

            # 5. Reddit icon circle + subreddit name
            icon_y = card_y + inner_pad
            icon_x = card_x + inner_pad
            draw.ellipse(
                [(icon_x, icon_y), (icon_x + icon_r * 2, icon_y + icon_r * 2)],
                fill=(255, 69, 0)
            )
            cx, cy = icon_x + icon_r, icon_y + icon_r
            draw.ellipse([(cx - 8, cy - 6), (cx - 2, cy)], fill='white')
            draw.ellipse([(cx + 2, cy - 6), (cx + 8, cy)], fill='white')
            draw.arc([(cx - 8, cy - 2), (cx + 8, cy + 8)], 0, 180, fill='white', width=2)

            # Show branding handle instead of subreddit for privacy
            sub_text = f"u/{branding.strip()}" if branding and branding.strip() else f"r/{subreddit}"
            draw.text((icon_x + icon_r * 2 + 12, icon_y + 8), sub_text, fill=(30, 30, 30), font=font_sub)

            # 6. Part badge (top right of card)
            if total_parts > 1:
                badge_text = f"Part {part_number}/{total_parts}"
                badge_bbox = draw.textbbox((0, 0), badge_text, font=font_sub)
                badge_w = badge_bbox[2] - badge_bbox[0] + 30
                badge_h = badge_bbox[3] - badge_bbox[1] + 16
                badge_x = card_x + card_w - badge_w - 20
                badge_y_pos = card_y + inner_pad
                draw.rounded_rectangle(
                    [(badge_x, badge_y_pos), (badge_x + badge_w, badge_y_pos + badge_h)],
                    radius=badge_h // 2, fill=(255, 69, 0)
                )
                draw.text((badge_x + 15, badge_y_pos + 5), badge_text, fill='white', font=font_sub)

            # 7. Title text (centered in remaining space)
            title_y = icon_y + icon_r * 2 + 20
            draw.multiline_text(
                (card_x + inner_pad, title_y), wrapped,
                fill=(20, 20, 20), font=font_title, spacing=8
            )

            # 8. Bottom bar — hearts + share count
            bottom_y = card_y + card_h - inner_pad - 25
            heart = "♡"
            score_text = f"{score:,}+" if score else "999+"
            share_text = f"⤴ {score_text}"
            draw.text((card_x + inner_pad, bottom_y), f"{heart} {score_text}", fill=(120, 120, 120), font=font_meta)
            draw.text((card_x + card_w - 180, bottom_y), share_text, fill=(120, 120, 120), font=font_meta)

            # 9. Branding watermark (bottom-right corner of image)
            if branding and branding.strip():
                brand_text = branding.strip()
                brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
                brand_tw = brand_bbox[2] - brand_bbox[0]
                brand_th = brand_bbox[3] - brand_bbox[1]
                brand_pad = 12
                brand_x = w - brand_tw - brand_pad - 20
                brand_y = h - brand_th - brand_pad - 20
                # Semi-transparent background pill
                draw.rounded_rectangle(
                    [(brand_x - brand_pad, brand_y - brand_pad),
                     (brand_x + brand_tw + brand_pad, brand_y + brand_th + brand_pad)],
                    radius=16, fill=(0, 0, 0, 160)
                )
                draw.text((brand_x, brand_y), brand_text, fill=(255, 255, 255, 220), font=font_brand)

            # Save
            bg_img.save(output_path, quality=95)
            print(f"   ✓ Thumbnail saved: {output_path}")
            return output_path

        except Exception as e:
            print(f"   ❌ Thumbnail generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_video_ffmpeg(self, audio_segments: List[dict], output_path: str, tail_text: Optional[str] = None, tail_duration: float = 0.0, branding: str = ""):
        """
        Generate video using direct FFmpeg commands (Beta Engine).
        Significantly faster compositing but requires FFmpeg installed.
        """
        print(f"\n🎬 Generating video (FFMPEG Beta Engine)...")
        import subprocess
        
        temp_files = [] # Track for cleanup
        
        # Resolve FFmpeg executable
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg_exe = 'ffmpeg' # Fallback to system path
        
        try:
            # 1. Prepare Audio (Using MoviePy for safety/compatibility)
            # We reuse the concatenation logic to get one solid audio file
            audio_clips = [AudioFileClip(s['audio_path']) for s in audio_segments]
            final_audio = concatenate_audioclips(audio_clips)
            total_duration = final_audio.duration + (tail_duration if (tail_text and tail_duration and tail_duration > 0) else 0)
            
            output_dir = os.path.dirname(output_path)
            temp_audio_path = os.path.join(output_dir, "ffmpeg_audio_temp.m4a")
            final_audio.write_audiofile(temp_audio_path, codec='aac', logger=None)
            final_audio.close()
            temp_files.append(temp_audio_path)
            
            # 2. Get Background Video (Pure FFmpeg)
            print("   Preparing background (Direct FFmpeg)...")
            video_files = [f for f in os.listdir(self.backgrounds_dir) 
                          if f.lower().endswith(('.mp4', '.mov', '.avi'))]
            
            use_blank_bg = False
            if not video_files:
                print("⚠️  No background videos found — using blank background")
                use_blank_bg = True
                bg_path = None
            else:
                bg_file = random.choice(video_files)
                bg_path = os.path.join(self.backgrounds_dir, bg_file)
            
            temp_bg_path = os.path.join(output_dir, "ffmpeg_bg_temp.mp4")
            w = self.width
            h = self.height

            if use_blank_bg:
                # Generate a solid-color background using FFmpeg lavfi
                bg_color_hex = "141420"
                bg_cmd = [
                    ffmpeg_exe, '-y',
                    '-f', 'lavfi', '-i', f'color=c=0x{bg_color_hex}:s={w}x{h}:d={total_duration}:r=30',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                    temp_bg_path
                ]
                print(f"   Generating blank background: {w}x{h}, {total_duration:.1f}s")
                subprocess.run(bg_cmd, check=True)
            else:
                # Check background duration for random seeking
                start_time = 0.0
                enable_loop = True

                try:
                    with VideoFileClip(bg_path) as clip:
                        bg_duration = clip.duration

                    if bg_duration > total_duration:
                        max_start = bg_duration - total_duration
                        start_time = random.uniform(0, max_start)
                        enable_loop = False
                        print(f"   Background is long enough ({bg_duration:.1f}s). Skipping to {start_time:.1f}s.")
                    else:
                        print(f"   Background is short ({bg_duration:.1f}s). Looping.")

                except Exception as e:
                    print(f"⚠️  Could not probe background duration: {e}. Defaulting to loop from start.")

                scale_filter = f"scale='iw*max({w}/iw\\,{h}/ih)':'ih*max({w}/iw\\,{h}/ih)',crop={w}:{h}"

                bg_cmd = [ffmpeg_exe, '-y']
                if start_time > 0:
                    bg_cmd.extend(['-ss', str(start_time)])
                if enable_loop:
                    bg_cmd.extend(['-stream_loop', '-1'])
                bg_cmd.extend(['-i', bg_path, '-vf', scale_filter, '-t', str(total_duration), '-an'])

                if self.hw_accel == 'nvenc':
                    bg_cmd.extend(['-c:v', 'h264_nvenc', '-rc', 'constqp', '-qp', '26', '-b:v', '0', '-preset', 'p2'])
                elif self.hw_accel == 'amf':
                    bg_cmd.extend(['-c:v', 'h264_amf', '-rc', 'cqp', '-qp_i', '26', '-qp_p', '26'])
                else:
                    bg_cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast'])

                bg_cmd.append(temp_bg_path)
                print(f"   Background Command: {' '.join(bg_cmd)}")
                subprocess.run(bg_cmd, check=True)

            temp_files.append(temp_bg_path)
            
            # 3. Generate Overlays
            print(f"   Generating {len(audio_segments)} overlay frames...")
            concat_lines = []
            
            current_author = None
            
            for i, segment in enumerate(audio_segments):
                if i % 10 == 0: print(f"     Processing segment {i+1}/{len(audio_segments)}...")
                
                # Check Duration
                duration = audio_clips[i].duration
                
                # Create Full Frame Overlay
                overlay_path = self.create_full_frame_overlay(segment, current_author, branding=branding)
                temp_files.append(overlay_path)
                
                # Add to concat list
                # Format:
                # file 'path'
                # duration X
                escape_path = overlay_path.replace('\\', '/')
                concat_lines.append(f"file '{escape_path}'")
                concat_lines.append(f"duration {duration}")

            if tail_text and tail_duration and tail_duration > 0:
                tail_segment = {'text': tail_text, 'author': ''}
                tail_overlay_path = self.create_full_frame_overlay(tail_segment, current_author, branding=branding)
                temp_files.append(tail_overlay_path)
                escape_tail = tail_overlay_path.replace('\\', '/')
                concat_lines.append(f"file '{escape_tail}'")
                concat_lines.append(f"duration {tail_duration}")
                
            # Create concat file
            concat_path = os.path.join(output_dir, "overlay_list.txt")
            with open(concat_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(concat_lines))
            temp_files.append(concat_path)
            
            # 4. Construct FFmpeg Command
            print("   Running FFmpeg render...")
            
            # Inputs:
            # -i temp_bg_path (Background)
            # -f concat -i concat_path (Overlay Stream)
            # -i temp_audio_path (Audio)
            
            # Select codec based on hw_accel
            if self.hw_accel == 'nvenc':
                v_codec = 'h264_nvenc'
            elif self.hw_accel == 'amf':
                v_codec = 'h264_amf'
            else:
                v_codec = 'libx264'

            cmd = [
                ffmpeg_exe, '-y',
                '-i', temp_bg_path,
                '-f', 'concat', '-safe', '0', '-i', concat_path,
                '-i', temp_audio_path,
                '-filter_complex', '[0:v][1:v]overlay=0:0[outv]',
                '-map', '[outv]', '-map', '2:a',
                '-c:v', v_codec,
                '-c:a', 'aac',
                '-pix_fmt', 'yuv420p',
                '-r', '30'
            ]

            if not (tail_text and tail_duration and tail_duration > 0):
                cmd.append('-shortest')
            
            if self.hw_accel == 'nvenc':
                cmd.extend(['-preset', 'p4', '-rc', 'vbr', '-cq', '19', '-b:v', '8M'])
            elif self.hw_accel == 'amf':
                cmd.extend(['-quality', 'speed', '-rc', 'vbr_latency', '-qp_i', '19', '-qp_p', '19', '-b:v', '8M'])
            else:
                cmd.extend(['-preset', 'medium', '-crf', '18'])
                
            cmd.append(output_path)
            
            print(f"   Command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            
            print("✓ FFmpeg generation complete!")
            
            # Cleanup
            if self.use_gpu: # Maybe keep for debug if not gpu? No, clean always unless debug mode.
                pass 
                
            print("   Cleaning up temporary files...")
            for f in temp_files:
                try:
                    if os.path.exists(f): os.remove(f)
                except: pass
                
            return output_path
            
        except Exception as e:
            print(f"❌ FFmpeg Engine Error: {e}")
            import traceback
            traceback.print_exc()
            return None
