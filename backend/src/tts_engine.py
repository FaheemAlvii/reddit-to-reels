"""
TTS engine wrappers for Streamlabs Polly (cloud) and VibeVoice (local).

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""
import requests
import json
import os
import sys
import hashlib
import time
from typing import Optional, List
from pathlib import Path


class StreamlabsTTS:
    """
    Streamlabs Polly TTS (undocumented API) integration.
    Uses the free Streamlabs endpoint for Amazon Polly voices.
    """
    
    # Streamlabs Polly endpoint
    API_URL = "https://streamlabs.com/polly/speak"
    
    # Max text length per request (safe limit)
    MAX_TEXT_LENGTH = 200
    
    # Available voices (Amazon Polly)
    AVAILABLE_VOICES = [
        "Brian",      # Male, British English (en-GB) - Popular choice
        "Amy",        # Female, British English (en-GB)
        "Emma",       # Female, British English (en-GB)
        "Joanna",     # Female, US English (en-US)
        "Matthew",    # Male, US English (en-US)
        "Joey",       # Male, US English (en-US)
        "Justin",     # Male, US English (en-US)
        "Kendra",     # Female, US English (en-US)
        "Kimberly",   # Female, US English (en-US)
        "Salli",      # Female, US English (en-US)
        "Ivy",        # Female, US English (en-US)
        "Nicole",     # Female, Australian English (en-AU)
        "Russell",    # Male, Australian English (en-AU)
    ]
    
    def __init__(self, voice: str = "Brian", output_dir: str = "audio", delay_between_requests: float = 0.5, cancel_check=None):
        """
        Initialize TTS with a specific voice.
        
        Args:
            voice: Voice name (e.g., "Brian", "Amy")
            output_dir: Directory to save audio files
            delay_between_requests: Delay in seconds between API requests (default 0.5s)
            cancel_check: Optional callable that raises if cancellation requested
        """
        self.voice = voice if voice in self.AVAILABLE_VOICES else "Brian"
        self.output_dir = output_dir
        self.delay_between_requests = delay_between_requests
        self.cancel_check = cancel_check
        os.makedirs(output_dir, exist_ok=True)
        
        # Headers required for the API
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://streamlabs.com/'
        }
    
    def _generate_filename(self, text: str, voice: str) -> str:
        """Generate a unique filename based on text and voice."""
        # Create hash of text + voice for unique filename
        text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()[:12]
        return f"{voice}_{text_hash}.mp3"
    
    def _hard_split(self, text: str) -> List[str]:
        """Force-split text that exceeds MAX_TEXT_LENGTH by words, never exceeding the limit."""
        words = text.split()
        segments = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= self.MAX_TEXT_LENGTH:
                current += " " + word
            else:
                segments.append(current)
                current = word
        if current:
            segments.append(current)
        # Final safety: if a single word exceeds the limit, chunk it by character count
        final = []
        for seg in segments:
            if len(seg) > self.MAX_TEXT_LENGTH:
                for i in range(0, len(seg), self.MAX_TEXT_LENGTH):
                    final.append(seg[i:i + self.MAX_TEXT_LENGTH])
            else:
                final.append(seg)
        return final

    def segment_text(self, text: str) -> List[str]:
        """
        Split text into sentences for subtitle syncing.
        Returns a list of sentence strings, each within MAX_TEXT_LENGTH.
        Preserves [PAUSE:N] markers as separate segments.
        """
        if not text or not text.strip():
            return []

        import re

        # Split on [PAUSE:N] markers first, keeping them as separate items
        pause_split = re.split(r'(\[PAUSE:\d+\])', text)

        final_segments = []
        for part in pause_split:
            part = part.strip()
            if not part:
                continue
            # Keep pause markers as standalone segments
            if re.match(r'^\[PAUSE:\d+\]$', part):
                final_segments.append(part)
                continue

            # Normal text — split by sentences
            sentences = re.split(r'([.!?]+)', part)

            combined_sentences = []
            for i in range(0, len(sentences)-1, 2):
                combined_sentences.append(sentences[i] + sentences[i+1])
            if len(sentences) % 2 == 1:
                combined_sentences.append(sentences[-1])

            for sentence in combined_sentences:
                cleaned = sentence.strip()
                if not cleaned:
                    continue

                if len(cleaned) <= self.MAX_TEXT_LENGTH:
                    final_segments.append(cleaned)
                    continue

                # Try splitting by commas first
                sub_segments = cleaned.split(',')
                current = ""
                for sub in sub_segments:
                    sub = sub.strip()
                    if not sub: continue
                    if not current:
                        current = sub
                    elif len(current) + len(sub) + 2 <= self.MAX_TEXT_LENGTH:
                        current += ", " + sub
                    else:
                        if len(current) > self.MAX_TEXT_LENGTH:
                            final_segments.extend(self._hard_split(current))
                        else:
                            final_segments.append(current)
                        current = sub
                if current:
                    if len(current) > self.MAX_TEXT_LENGTH:
                        final_segments.extend(self._hard_split(current))
                    else:
                        final_segments.append(current)
                
        return final_segments
    
    def synthesize(self, text: str, output_filename: Optional[str] = None, max_retries: int = 3) -> Optional[str]:
        """
        Synthesize text to speech using Streamlabs Polly with retry logic.
        Validates text length and chunks if necessary.
        """
        if not text or not text.strip():
            print("⚠️  Empty text provided, skipping TTS")
            return None
        
        # Generate filename
        if not output_filename:
            output_filename = self._generate_filename(text, self.voice)
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Check if file already exists (cache)
        if os.path.exists(output_path):
            print(f"✓ Using cached audio: {output_filename}")
            return output_path

        # Handle long text by chunking
        if len(text) > self.MAX_TEXT_LENGTH:
            print(f"ℹ️  Text too long ({len(text)} chars), splitting into chunks...")
            chunks = self.segment_text(text)
            chunk_files = []
            
            print(f"   Processing {len(chunks)} chunks...")
            
            for i, chunk in enumerate(chunks):
                # Check cancellation between chunks
                if self.cancel_check:
                    self.cancel_check()
                chunk_filename = f"temp_{int(time.time())}_{i}.mp3"
                chunk_path = self.synthesize(chunk, output_filename=chunk_filename, max_retries=max_retries)
                
                if not chunk_path:
                    print(f"❌ Failed to generate chunk {i+1}/{len(chunks)}")
                    return None
                    
                chunk_files.append(chunk_path)
                # Small delay between chunks to be safe
                time.sleep(0.5)
            
            # Combine chunks
            try:
                with open(output_path, 'wb') as outfile:
                    for chunk_path in chunk_files:
                        with open(chunk_path, 'rb') as infile:
                            outfile.write(infile.read())
                        # Clean up temp file
                        try:
                            os.remove(chunk_path)
                        except:
                            pass
                
                print(f"✓ Combined {len(chunks)} chunks into: {output_filename}")
                return output_path
            except Exception as e:
                print(f"❌ Error combining chunks: {e}")
                return None
        
        # Prepare form data (POST request, not GET!)
        data = {
            'voice': self.voice,
            'text': text
        }
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            # Check cancellation before each attempt
            if self.cancel_check:
                self.cancel_check()
            
            try:
                # Rate limiting delay (skip on first request if it's the first overall)
                if attempt > 0 or self.delay_between_requests > 0:
                    delay = self.delay_between_requests * (2 ** attempt)  # Exponential backoff
                    time.sleep(delay)
                
                # Make POST request to Streamlabs API
                response = requests.post(
                    self.API_URL,
                    data=data,
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                
                # Parse JSON response
                try:
                    result = response.json()
                    if not result.get('success'):
                        print(f"✗ TTS Error: API returned success=false")
                        if attempt < max_retries - 1:
                            print(f"  Retrying ({attempt + 2}/{max_retries})...")
                            continue
                        return None
                    
                    speak_url = result.get('speak_url')
                    if not speak_url:
                        print(f"✗ TTS Error: No speak_url in response")
                        return None
                    
                    # Download the actual audio file
                    audio_response = requests.get(speak_url, timeout=30)
                    audio_response.raise_for_status()
                    
                    # Save audio file
                    with open(output_path, 'wb') as f:
                        f.write(audio_response.content)
                    
                    print(f"✓ Generated TTS: {output_filename} ({self.voice})")
                    return output_path
                    
                except json.JSONDecodeError:
                    print(f"✗ TTS Error: Invalid JSON response")
                    if attempt < max_retries - 1:
                        print(f"  Retrying ({attempt + 2}/{max_retries})...")
                        continue
                    return None
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 422:
                    # Rate limit or validation error - retry with backoff
                    print(f"DEBUG: 422 Response: {e.response.text}")
                    if attempt < max_retries - 1:
                        wait_time = self.delay_between_requests * (2 ** (attempt + 1))
                        print(f"✗ Rate limit (422) - waiting {wait_time:.1f}s before retry ({attempt + 2}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"✗ TTS Error: {e} (max retries reached)")
                        return None
                else:
                    print(f"✗ TTS Error: {e}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"✗ TTS Error: {e}")
                if attempt < max_retries - 1:
                    print(f"  Retrying ({attempt + 2}/{max_retries})...")
                    continue
                return None
        
        return None
    
    def _generate_silence(self, duration_seconds: int, output_path: str) -> str:
        """Generate a silent audio file of specified duration."""
        import struct
        import wave

        # Generate silent WAV then convert path (consumers handle mp3/wav)
        wav_path = output_path.replace('.mp3', '.wav') if output_path.endswith('.mp3') else output_path
        sample_rate = 22050
        num_samples = sample_rate * duration_seconds
        
        with wave.open(wav_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack('<' + 'h' * num_samples, *([0] * num_samples)))
        
        return wav_path

    def generate_segments(self, text: str, progress_callback=None, cancel_check=None) -> List[dict]:
        """
        Generate audio segments for a text, splitting by sentences.
        Returns a list of dicts: {'text': str, 'audio_path': str}
        Handles [PAUSE:N] markers by generating silence segments.
        
        progress_callback(current, total, segment_text): called after each segment
        cancel_check(): called between segments, should raise if cancelled
        """
        import re
        segments = self.segment_text(text)
        results = []
        
        print(f"   Processing {len(segments)} segments...")
        
        for i, segment_text in enumerate(segments):
            if cancel_check:
                cancel_check()
            
            # Handle [PAUSE:N] markers
            pause_match = re.match(r'^\[PAUSE:(\d+)\]$', segment_text)
            if pause_match:
                pause_secs = int(pause_match.group(1))
                silence_filename = f"pause_{int(time.time())}_{i}_{pause_secs}s.wav"
                silence_path = self._generate_silence(pause_secs, os.path.join(self.output_dir, silence_filename))
                results.append({
                    'text': f'[{pause_secs}s pause]',
                    'audio_path': silence_path,
                    'is_pause': True,
                })
                if progress_callback:
                    progress_callback(i + 1, len(segments), f"[Pause {pause_secs}s]")
                continue

            # Normal text segment
            filename = self._generate_filename(segment_text, self.voice)
            audio_path = self.synthesize(segment_text, output_filename=filename)
            
            if audio_path:
                results.append({
                    'text': segment_text,
                    'audio_path': audio_path
                })
            
            # Report progress after each segment is generated
            if progress_callback:
                progress_callback(i + 1, len(segments), segment_text)
            
            # Small delay
            if i < len(segments) - 1:
                time.sleep(0.2)
                    
        return results

    def synthesize_batch(self, texts: List[str], voices: Optional[List[str]] = None) -> List[Optional[str]]:
        """
        Synthesize multiple texts to speech.
        
        Args:
            texts: List of texts to convert
            voices: Optional list of voices (one per text). If None, uses self.voice for all
            
        Returns:
            List of paths to generated audio files
        """
        if voices is None:
            voices = [self.voice] * len(texts)
        
        if len(voices) != len(texts):
            print("⚠️  Voice count doesn't match text count, using main voice")
            voices = [self.voice] * len(texts)
        
        results = []
        for i, (text, voice) in enumerate(zip(texts, voices)):
            # Temporarily change voice
            original_voice = self.voice
            self.voice = voice
            
            result = self.synthesize(text)
            results.append(result)
            
            # Restore original voice
            self.voice = original_voice
        
        return results


class LazyPyTikTokTTS:
    """
    TikTok TTS via the lazypy.ro proxy API.
    Uses POST to https://lazypy.ro/tts/request_tts.php
    Free, no API key needed, returns mp3 audio URLs.
    """

    API_URL = "https://lazypy.ro/tts/request_tts.php"

    # Max text length per request (TikTok has ~300 char limit)
    MAX_TEXT_LENGTH = 280

    # Popular English TikTok voices
    AVAILABLE_VOICES = [
        # Female
        "en_us_001",            # Female
        "en_us_002",            # Female
        "en_female_emotional",  # Peaceful
        "en_female_grandma",    # Grandma
        "en_female_madam_leota", # Ghost
        "en_female_ht_f08_glorious", # Glorious
        "en_female_ht_f08_wonderful_world", # Wonderful World
        # Male
        "en_us_006",            # Male 1
        "en_us_007",            # Male 2
        "en_us_009",            # Male 3
        "en_us_010",            # Male 4
        "en_male_narration",    # Narrator
        "en_male_funny",        # Funny
        "en_male_cody",         # Cody
        "en_male_wizard",       # Wizard
        # Characters / Singing
        "en_us_ghostface",      # Ghostface
        "en_us_chewbacca",      # Chewbacca
        "en_us_c3po",           # C3PO
        "en_us_stitch",         # Stitch
        "en_us_stormtrooper",   # Stormtrooper
        "en_us_rocket",         # Rocket
        "en_female_samc",       # Singing Alto
        "en_male_sing_deep_jingle", # Singing Deep
    ]

    def __init__(self, voice: str = "en_male_narration", output_dir: str = "audio",
                 delay_between_requests: float = 0.5, cancel_check=None):
        self.voice = voice if voice in self.AVAILABLE_VOICES else "en_male_narration"
        self.output_dir = output_dir
        self.delay_between_requests = delay_between_requests
        self.cancel_check = cancel_check
        os.makedirs(output_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://lazypy.ro/tts/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

    def _generate_filename(self, text: str, voice: str) -> str:
        text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()[:12]
        return f"tiktok_{voice}_{text_hash}.mp3"

    def _hard_split(self, text: str) -> List[str]:
        """Force-split text that exceeds MAX_TEXT_LENGTH by words."""
        words = text.split()
        segments = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= self.MAX_TEXT_LENGTH:
                current += " " + word
            else:
                segments.append(current)
                current = word
        if current:
            segments.append(current)
        final = []
        for seg in segments:
            if len(seg) > self.MAX_TEXT_LENGTH:
                for i in range(0, len(seg), self.MAX_TEXT_LENGTH):
                    final.append(seg[i:i + self.MAX_TEXT_LENGTH])
            else:
                final.append(seg)
        return final

    def segment_text(self, text: str) -> List[str]:
        """Split text into sentences, respecting MAX_TEXT_LENGTH."""
        if not text or not text.strip():
            return []
        import re
        sentences = re.split(r'([.!?]+)', text)
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            combined.append(sentences[i] + sentences[i + 1])
        if len(sentences) % 2 == 1:
            combined.append(sentences[-1])

        final = []
        for sentence in combined:
            cleaned = sentence.strip()
            if not cleaned:
                continue
            if len(cleaned) <= self.MAX_TEXT_LENGTH:
                final.append(cleaned)
                continue

            sub_parts = cleaned.split(',')
            current = ""
            for sub in sub_parts:
                sub = sub.strip()
                if not sub:
                    continue
                if not current:
                    current = sub
                elif len(current) + len(sub) + 2 <= self.MAX_TEXT_LENGTH:
                    current += ", " + sub
                else:
                    if len(current) > self.MAX_TEXT_LENGTH:
                        final.extend(self._hard_split(current))
                    else:
                        final.append(current)
                    current = sub
            if current:
                if len(current) > self.MAX_TEXT_LENGTH:
                    final.extend(self._hard_split(current))
                else:
                    final.append(current)
        return final

    def synthesize(self, text: str, output_filename: Optional[str] = None, max_retries: int = 3) -> Optional[str]:
        if not text or not text.strip():
            return None

        if not output_filename:
            output_filename = self._generate_filename(text, self.voice)
        output_path = os.path.join(self.output_dir, output_filename)

        if os.path.exists(output_path):
            print(f"✓ Using cached audio: {output_filename}")
            return output_path

        # Handle long text by chunking
        if len(text) > self.MAX_TEXT_LENGTH:
            print(f"ℹ️  Text too long ({len(text)} chars), splitting into chunks...")
            chunks = self.segment_text(text)
            chunk_files = []
            for i, chunk in enumerate(chunks):
                if self.cancel_check:
                    self.cancel_check()
                chunk_filename = f"temp_tt_{int(time.time())}_{i}.mp3"
                chunk_path = self.synthesize(chunk, output_filename=chunk_filename, max_retries=max_retries)
                if not chunk_path:
                    print(f"❌ Failed to generate chunk {i+1}/{len(chunks)}")
                    return None
                chunk_files.append(chunk_path)
                time.sleep(0.3)

            try:
                with open(output_path, 'wb') as outfile:
                    for cp in chunk_files:
                        with open(cp, 'rb') as inf:
                            outfile.write(inf.read())
                        try:
                            os.remove(cp)
                        except:
                            pass
                print(f"✓ Combined {len(chunks)} TikTok TTS chunks: {output_filename}")
                return output_path
            except Exception as e:
                print(f"❌ Error combining chunks: {e}")
                return None

        # POST request to LazyPy
        data = {
            'service': 'TikTok',
            'voice': self.voice,
            'text': text,
        }

        for attempt in range(max_retries):
            if self.cancel_check:
                self.cancel_check()
            try:
                if attempt > 0:
                    time.sleep(self.delay_between_requests * (2 ** attempt))

                response = requests.post(
                    self.API_URL, data=data, headers=self.headers, timeout=30
                )
                response.raise_for_status()

                result = response.json()
                if not result.get('success'):
                    err = result.get('error_msg', 'Unknown error')
                    print(f"✗ TikTok TTS Error: {err}")
                    if attempt < max_retries - 1:
                        continue
                    return None

                audio_url = result.get('audio_url')
                if not audio_url:
                    print("✗ TikTok TTS: No audio_url in response")
                    return None

                # Download audio
                audio_resp = requests.get(audio_url, timeout=30)
                audio_resp.raise_for_status()

                with open(output_path, 'wb') as f:
                    f.write(audio_resp.content)

                print(f"✓ TikTok TTS: {output_filename} ({self.voice})")
                return output_path

            except requests.exceptions.RequestException as e:
                print(f"✗ TikTok TTS Error: {e}")
                if attempt < max_retries - 1:
                    continue
                return None

        return None

    def generate_segments(self, text: str, progress_callback=None, cancel_check=None) -> List[dict]:
        """Generate audio segments split by sentences."""
        segments = self.segment_text(text)
        results = []
        print(f"   Processing {len(segments)} TikTok TTS segments...")
        for i, seg_text in enumerate(segments):
            if cancel_check:
                cancel_check()
            filename = self._generate_filename(seg_text, self.voice)
            audio_path = self.synthesize(seg_text, output_filename=filename)
            if audio_path:
                results.append({'text': seg_text, 'audio_path': audio_path})
            if progress_callback:
                progress_callback(i + 1, len(segments), seg_text)
            if i < len(segments) - 1:
                time.sleep(0.2)
        return results

    def synthesize_batch(self, texts: List[str], voices: Optional[List[str]] = None) -> List[Optional[str]]:
        if voices is None:
            voices = [self.voice] * len(texts)
        if len(voices) != len(texts):
            voices = [self.voice] * len(texts)
        results = []
        for text, voice in zip(texts, voices):
            orig = self.voice
            self.voice = voice
            results.append(self.synthesize(text))
            self.voice = orig
        return results


if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TTSManager:
    """
    Manages TTS generation for Reddit posts with configurable voices.
    """
    
    def __init__(self, config_filename: str = "config.json"):
        """Initialize with configuration."""
        self.config_path = os.path.join(PROJECT_ROOT, config_filename)
        self.config = self._load_config(self.config_path)
        self.tts_config = self.config.get('tts', {})
        
        if not self.tts_config.get('enabled', False):
            print("⚠️  TTS is disabled in config")
            self.enabled = False
            return
        
        self.enabled = True
        self.main_voice = self.tts_config.get('main_voice', 'Brian')
        self.use_multiple_voices = self.tts_config.get('use_multiple_voices', True)
        self.comment_voices = self.tts_config.get('comment_voices', ['Brian'])
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file not found: {config_path}")
            return {}
    
    def generate_story_mode_audio(self, post_id: str, text: str) -> Optional[str]:
        """
        Generate audio for story mode (single voice).
        
        Args:
            post_id: Post ID for organizing files
            text: Story text
            
        Returns:
            Path to generated audio file
        """
        if not self.enabled:
            return None
        
        audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
        tts = StreamlabsTTS(voice=self.main_voice, output_dir=audio_dir)
        
        print(f"\n🎙️  Generating Story Mode TTS...")
        return tts.synthesize(text, "story_mode.mp3")
    
    def generate_qa_mode_audio(
        self, 
        post_id: str, 
        post_text: str, 
        comments: List[dict]
    ) -> dict:
        """
        Generate audio for Q&A mode with multiple voices.
        
        Args:
            post_id: Post ID for organizing files
            post_text: Main post text
            comments: List of comment dicts with 'author' and 'body'
            
        Returns:
            Dict with paths to all generated audio files
        """
        if not self.enabled:
            return {}
        
        audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
        tts = StreamlabsTTS(voice=self.main_voice, output_dir=audio_dir)
        
        results = {
            'post': None,
            'comments': []
        }
        
        print(f"\n🎙️  Generating Q&A Mode TTS...")
        
        # Generate post audio
        print(f"  📝 Post ({self.main_voice})...")
        results['post'] = tts.synthesize(post_text, "qa_post.mp3")
        
        # Generate comment audios with different voices
        print(f"  💬 Comments...")
        for i, comment in enumerate(comments):
            # Assign voice based on author (consistent per author)
            if self.use_multiple_voices:
                # Use hash of author name to consistently assign voice
                author_hash = hash(comment.get('author', '')) % len(self.comment_voices)
                voice = self.comment_voices[author_hash]
            else:
                voice = self.main_voice
            
            # Create comment text (no attribution - username shown elsewhere)
            comment_text = comment.get('body', '')
            
            # Generate audio
            tts.voice = voice
            filename = f"qa_comment_{i+1:02d}.mp3"
            audio_path = tts.synthesize(comment_text, filename)
            
            results['comments'].append({
                'index': i + 1,
                'author': comment.get('author'),
                'voice': voice,
                'audio_path': audio_path
            })
        
        return results
    
    def generate_full_narrative(
        self, 
        post_id: str, 
        post_title: str,
        post_body: str, 
        post_author: str,
        comments: List[dict],
        progress_callback=None,
        cancel_check=None
    ) -> List[dict]:
        """
        Generate a complete list of audio segments for the entire video timeline.
        Returns list of dicts: {'text': ..., 'audio_path': ..., 'author': ...}
        
        progress_callback(phase, current, total, detail): called after each segment
        cancel_check(): called between segments, should raise if cancelled
        """
        if not self.enabled:
            return []

        full_timeline = []
        audio_dir = os.path.join(PROJECT_ROOT, "posts", post_id, "audio")
        tts = StreamlabsTTS(voice=self.main_voice, output_dir=audio_dir, cancel_check=cancel_check)
        
        print(f"\n🎙️  Generating Full Narrative for Video...")

        # Pre-calculate total segments for progress
        tts_temp = StreamlabsTTS(voice=self.main_voice, output_dir=audio_dir)
        title_segs = tts_temp.segment_text(post_title)
        body_segs = tts_temp.segment_text(post_body) if post_body and post_body.strip() else []
        comment_seg_counts = []
        for c in comments:
            comment_seg_counts.append(len(tts_temp.segment_text(c.get('body', ''))))
        
        total_segments = len(title_segs) + len(body_segs) + sum(comment_seg_counts)
        current_segment = 0

        def _progress(phase, current_in_phase, total_in_phase, detail=""):
            nonlocal current_segment
            current_segment += 1
            if progress_callback:
                progress_callback(phase, current_segment, total_segments, f"({current_in_phase}/{total_in_phase}) {detail[:40]}")

        def _check():
            if cancel_check:
                cancel_check()

        def _make_seg_progress(phase):
            """Returns a callback for generate_segments that reports per-segment progress."""
            def _cb(current_in_phase, total_in_phase, seg_text):
                nonlocal current_segment
                current_segment += 1
                if progress_callback:
                    progress_callback(phase, current_segment, total_segments, f"({current_in_phase}/{total_in_phase}) {seg_text[:40]}")
            return _cb

        # 1. Post Title
        print(f"  📝 Processing Title...")
        tts.voice = self.main_voice
        title_segments = tts.generate_segments(post_title, progress_callback=_make_seg_progress("Title"), cancel_check=cancel_check)
        for seg in title_segments:
            seg['author'] = post_author
            full_timeline.append(seg)
            
        # 2. Post Body
        if post_body and post_body.strip():
            print(f"  📝 Processing Body...")
            body_segments = tts.generate_segments(post_body, progress_callback=_make_seg_progress("Body"), cancel_check=cancel_check)
            for seg in body_segments:
                seg['author'] = post_author
                full_timeline.append(seg)
        
        # 3. Comments
        print(f"  💬 Processing {len(comments)} Comments...")
        for i, comment in enumerate(comments):
            _check()
            author = comment.get('author', 'Anonymous')
            body = comment.get('body', '')
            
            # Select voice
            if self.use_multiple_voices:
                author_hash = hash(author) % len(self.comment_voices)
                voice = self.comment_voices[author_hash]
            else:
                voice = self.main_voice
            
            tts.voice = voice
            
            comment_segments = tts.generate_segments(body, progress_callback=_make_seg_progress(f"Comment {i+1}"), cancel_check=cancel_check)
            for seg in comment_segments:
                seg['author'] = author
                full_timeline.append(seg)
                
        print(f"✓ Narrative complete! {len(full_timeline)} segments generated.")
        return full_timeline

    def generate_from_formatted_files(self, post_id: str, mode: str = 'qa') -> Optional[dict]:
        """
        Generate TTS from already formatted text files.
        
        Args:
            post_id: Post ID
            mode: 'story' or 'qa'
            
        Returns:
            Dict with audio file paths
        """
        if not self.enabled:
            return None
        
        post_folder = os.path.join(PROJECT_ROOT, "posts", post_id)
        
        if mode == 'story':
            # Read story mode text
            story_path = os.path.join(post_folder, "story_mode.txt")
            if not os.path.exists(story_path):
                print(f"✗ Story mode text not found: {story_path}")
                return None
            
            with open(story_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            audio_path = self.generate_story_mode_audio(post_id, text)
            return {'story': audio_path}
        
        elif mode == 'qa':
            # For Q&A mode, we need to parse the formatted text
            # This is a simplified version - in practice you'd want to parse properly
            print("⚠️  For Q&A mode, use generate_qa_mode_audio() with comment data")
            return None


def main():
    """Demo/test function."""
    print("=" * 60)
    print("Streamlabs TTS Test")
    print("=" * 60)
    
    # Test basic TTS
    tts = StreamlabsTTS(voice="Brian", output_dir="test_audio")
    
    test_text = "Hello! This is a test of the Streamlabs Polly text to speech system."
    print(f"\nTesting with voice: {tts.voice}")
    print(f"Text: {test_text}")
    
    result = tts.synthesize(test_text)
    
    if result:
        print(f"\n✅ Success! Audio saved to: {result}")
    else:
        print(f"\n❌ Failed to generate audio")


if __name__ == "__main__":
    main()
