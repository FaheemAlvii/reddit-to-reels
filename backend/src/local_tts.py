"""
Local TTS providers: Microsoft VibeVoice and Qwen3-TTS.
These run entirely on the local machine using GPU inference.
"""
import os
import sys
import subprocess
import json
import hashlib
import time
import shutil
from typing import Optional, List
from pathlib import Path

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_MODELS_DIR = os.path.join(PROJECT_ROOT, "models")


def _run_cmd(cmd: list, cwd: str = None, timeout: int = 600) -> dict:
    """Run a shell command and return result."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


# ── VibeVoice ──────────────────────────────────────────────────────────

VIBEVOICE_DIR = os.path.join(LOCAL_MODELS_DIR, "VibeVoice")
VIBEVOICE_REPO = "https://github.com/vibevoice-community/VibeVoice.git"
VIBEVOICE_MODELS = {
    "vibevoice-1.5b": {
        "hf_id": "microsoft/VibeVoice-1.5B",
        "name": "VibeVoice 1.5B",
        "description": "Full model (~3B params). Multi-speaker, up to ~90 min generation. Best quality.",
        "size": "~6 GB",
    },
    "vibevoice-0.5b": {
        "hf_id": "microsoft/VibeVoice-Realtime-0.5B",
        "name": "VibeVoice Realtime 0.5B",
        "description": "Lightweight streaming model (~1B params). Single speaker, ~300ms latency. Fast.",
        "size": "~2 GB",
    },
}


def check_vibevoice() -> dict:
    """Check if VibeVoice is installed and ready."""
    status = {
        "installed": False,
        "repo_cloned": os.path.isdir(VIBEVOICE_DIR),
        "model_downloaded": False,
        "python_deps": False,
        "details": "",
    }

    if not status["repo_cloned"]:
        status["details"] = "Repository not cloned"
        return status

    # Check if package is importable
    try:
        result = _run_cmd(
            [sys.executable, "-c", "import vibevoice; print('ok')"],
            timeout=30,
        )
        status["python_deps"] = result["success"]
    except Exception:
        pass

    # Check which model weights exist
    models_downloaded = []
    for model_key in VIBEVOICE_MODELS:
        if os.path.isdir(os.path.join(LOCAL_MODELS_DIR, model_key)):
            models_downloaded.append(model_key)
    status["model_downloaded"] = len(models_downloaded) > 0
    status["models_downloaded"] = models_downloaded

    status["installed"] = status["repo_cloned"] and status["python_deps"]
    if status["installed"]:
        status["details"] = "Ready" + (" (model downloaded)" if status["model_downloaded"] else " (model will download on first use)")
    else:
        missing = []
        if not status["repo_cloned"]:
            missing.append("repo")
        if not status["python_deps"]:
            missing.append("python deps")
        status["details"] = f"Missing: {', '.join(missing)}"

    return status


def install_vibevoice() -> dict:
    """Install VibeVoice: clone repo + pip install."""
    os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)

    steps = []

    # 1. Clone repo
    if not os.path.isdir(VIBEVOICE_DIR):
        result = _run_cmd(
            ["git", "clone", "--depth", "1", VIBEVOICE_REPO, VIBEVOICE_DIR],
            timeout=120,
        )
        steps.append({"step": "clone_repo", **result})
        if not result["success"]:
            return {"success": False, "steps": steps, "error": "Failed to clone repository"}
    else:
        steps.append({"step": "clone_repo", "success": True, "stdout": "Already cloned", "stderr": ""})

    # 2. Install Python package
    result = _run_cmd(
        [sys.executable, "-m", "pip", "install", "-e", VIBEVOICE_DIR],
        timeout=300,
    )
    steps.append({"step": "pip_install", **result})
    if not result["success"]:
        return {"success": False, "steps": steps, "error": "Failed to install Python dependencies"}

    # 3. Install additional deps
    result = _run_cmd(
        [sys.executable, "-m", "pip", "install", "huggingface_hub", "transformers", "accelerate", "soundfile", "torchaudio", "einops"],
        timeout=300,
    )
    steps.append({"step": "extra_deps", **result})

    return {"success": True, "steps": steps}


def discover_vibevoice_voices() -> List[dict]:
    """Scan the VibeVoice voices directory and return available voices."""
    voices_dir = os.path.join(VIBEVOICE_DIR, "voices")
    results = []
    seen_names = set()

    if not os.path.isdir(voices_dir):
        return []

    # Scan .wav files in voices/ root
    for f in sorted(os.listdir(voices_dir)):
        if f.endswith(".wav"):
            name = f.replace(".wav", "")
            # Parse pattern: lang-Name_gender or lang-Name_gender_bgm
            parts = name.split("-", 1)
            lang = parts[0] if len(parts) > 1 else "en"
            rest = parts[1] if len(parts) > 1 else parts[0]
            has_bgm = rest.endswith("_bgm")
            if has_bgm:
                rest = rest[:-4]
            # Split by underscore: Name_gender
            tokens = rest.rsplit("_", 1)
            display_name = tokens[0] if tokens else rest
            gender = tokens[1] if len(tokens) > 1 else "unknown"
            voice_id = name
            if voice_id not in seen_names:
                seen_names.add(voice_id)
                results.append({
                    "id": voice_id,
                    "name": display_name,
                    "lang": lang,
                    "gender": gender,
                    "has_bgm": has_bgm,
                    "type": "wav",
                    "file": f,
                })

    # Scan .pt files in voices/streaming_model/
    streaming_dir = os.path.join(voices_dir, "streaming_model")
    if os.path.isdir(streaming_dir):
        for f in sorted(os.listdir(streaming_dir)):
            if f.endswith(".pt"):
                name = f.replace(".pt", "")
                parts = name.split("-", 1)
                lang = parts[0] if len(parts) > 1 else "en"
                rest = parts[1] if len(parts) > 1 else parts[0]
                tokens = rest.rsplit("_", 1)
                display_name = tokens[0] if tokens else rest
                gender = tokens[1] if len(tokens) > 1 else "unknown"
                voice_id = name
                if voice_id not in seen_names:
                    seen_names.add(voice_id)
                    results.append({
                        "id": voice_id,
                        "name": display_name,
                        "lang": lang,
                        "gender": gender,
                        "has_bgm": False,
                        "type": "streaming",
                        "file": f,
                    })

    return results


class VibeVoiceTTS:
    """VibeVoice local TTS wrapper."""

    @staticmethod
    def get_available_voices() -> List[str]:
        """Dynamically discover voices from the filesystem."""
        voices = discover_vibevoice_voices()
        return [v["id"] for v in voices] if voices else ["en-Alice_woman", "en-Frank_man"]

    def __init__(self, voice: str = "en-Alice_woman", model_size: str = "vibevoice-1.5b", output_dir: str = "audio", cancel_check=None):
        self.voice = voice
        self.model_size = model_size
        self.output_dir = output_dir
        self.cancel_check = cancel_check
        self.model = None
        os.makedirs(output_dir, exist_ok=True)

    def _ensure_model(self):
        if self.model is not None:
            return
        try:
            import torch

            # Add VibeVoice repo to path so its modules are importable
            if VIBEVOICE_DIR not in sys.path:
                sys.path.insert(0, VIBEVOICE_DIR)

            from huggingface_hub import snapshot_download
            model_info = VIBEVOICE_MODELS.get(self.model_size, list(VIBEVOICE_MODELS.values())[0])
            hf_id = model_info["hf_id"] if isinstance(model_info, dict) else model_info
            self._model_path = os.path.join(LOCAL_MODELS_DIR, self.model_size)
            if not os.path.isdir(self._model_path):
                print(f"📥 Downloading {self.model_size} model (first time)...")
                snapshot_download(hf_id, local_dir=self._model_path)

            # Determine which classes to use based on model size
            if self.model_size == "vibevoice-0.5b":
                from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference as InferenceClass
                from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor as ProcessorClass
            else:
                from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference as InferenceClass
                from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor as ProcessorClass

            self.processor = ProcessorClass.from_pretrained(self._model_path)

            # Determine device, dtype, and attention implementation
            if torch.cuda.is_available():
                device_map = "cuda"
                load_dtype = torch.bfloat16
                attn_impl = "flash_attention_2"
            else:
                device_map = "cpu"
                load_dtype = torch.float32
                attn_impl = "sdpa"

            try:
                self.model = InferenceClass.from_pretrained(
                    self._model_path,
                    torch_dtype=load_dtype,
                    device_map=device_map,
                    attn_implementation=attn_impl,
                )
            except Exception:
                # Fallback to sdpa if flash_attention_2 fails
                if attn_impl == "flash_attention_2":
                    print("⚠ flash_attention_2 not available, falling back to sdpa")
                    self.model = InferenceClass.from_pretrained(
                        self._model_path,
                        torch_dtype=load_dtype,
                        device_map=device_map,
                        attn_implementation="sdpa",
                    )
                else:
                    raise

            self.model.eval()
            self.model.set_ddpm_inference_steps(num_steps=10)
            self._device = device_map
            print(f"✓ VibeVoice model loaded ({self.model_size}) on {device_map}")
        except ImportError as e:
            print(f"❌ VibeVoice import failed: {e}")
            print("   Make sure VibeVoice is installed: pip install -e models/VibeVoice")
            raise RuntimeError(f"VibeVoice not available: {e}")
        except Exception as e:
            import traceback
            print(f"❌ VibeVoice model load failed: {e}")
            traceback.print_exc()
            raise RuntimeError(f"VibeVoice not available: {e}")

    def _resolve_voice_path(self) -> Optional[str]:
        """Resolve the voice path from self.voice id."""
        if self.model_size == "vibevoice-0.5b":
            # Streaming model uses .pt files
            voice_pt = os.path.join(VIBEVOICE_DIR, "voices", "streaming_model", f"{self.voice}.pt")
            if os.path.exists(voice_pt):
                return voice_pt
            # Fallback to any .pt in streaming_model
            streaming_dir = os.path.join(VIBEVOICE_DIR, "voices", "streaming_model")
            if os.path.isdir(streaming_dir):
                pts = sorted(f for f in os.listdir(streaming_dir) if f.endswith(".pt"))
                if pts:
                    return os.path.join(streaming_dir, pts[0])
        else:
            # Full model uses .wav files
            voice_wav = os.path.join(VIBEVOICE_DIR, "voices", f"{self.voice}.wav")
            if os.path.exists(voice_wav):
                return voice_wav
            # Fallback: try first available wav
            voices_dir = os.path.join(VIBEVOICE_DIR, "voices")
            if os.path.isdir(voices_dir):
                wavs = sorted(f for f in os.listdir(voices_dir) if f.endswith(".wav"))
                if wavs:
                    return os.path.join(voices_dir, wavs[0])
        return None

    def _generate_filename(self, text: str) -> str:
        text_hash = hashlib.md5(f"{text}_{self.voice}".encode()).hexdigest()[:12]
        return f"vv_{self.voice}_{text_hash}.wav"

    def segment_text(self, text: str) -> List[str]:
        """Split text into sentences."""
        if not text or not text.strip():
            return []
        import re
        sentences = re.split(r'([.!?]+)', text)
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            combined.append(sentences[i] + sentences[i + 1])
        if len(sentences) % 2 == 1:
            combined.append(sentences[-1])
        return [s.strip() for s in combined if s.strip()]

    def synthesize(self, text: str, output_filename: Optional[str] = None, max_retries: int = 2) -> Optional[str]:
        if not text or not text.strip():
            return None

        if not output_filename:
            output_filename = self._generate_filename(text)
        output_path = os.path.join(self.output_dir, output_filename)

        if os.path.exists(output_path):
            return output_path

        if self.cancel_check:
            self.cancel_check()

        try:
            self._ensure_model()
            import torch

            # Build transcript in VibeVoice format - ensure every line has a speaker prefix
            lines = text.strip().split('\n')
            transcript = "\n".join([f"Speaker 1: {line.strip()}" for line in lines if line.strip()])
            transcript = transcript.replace("\u2019", "'")

            # Resolve voice sample path
            voice_path = self._resolve_voice_path()
            
            # Process inputs
            if self.model_size == "vibevoice-0.5b":
                if not voice_path:
                    print("❌ VibeVoice: no voice prompt found for streaming model")
                    return None
                
                cached_prompt = torch.load(voice_path, map_location="cpu")
                
                # Move cached prompt tensors to target device
                target_device = self._device if self._device != "cpu" else "cpu"
                if isinstance(cached_prompt, dict):
                    for k, v in cached_prompt.items():
                        if isinstance(v, dict):
                            for sub_k, sub_v in v.items():
                                if torch.is_tensor(sub_v):
                                    v[sub_k] = sub_v.to(target_device)
                        elif torch.is_tensor(v):
                            cached_prompt[k] = v.to(target_device)

                inputs = self.processor.process_input_with_cached_prompt(
                    text=text,
                    cached_prompt=cached_prompt,
                    padding=True,
                    return_tensors="pt",
                    return_attention_mask=True,
                )
            else:
                voice_samples = [[voice_path]] if voice_path else [[]]
                inputs = self.processor(
                    text=[transcript],
                    voice_samples=voice_samples,
                    padding=True,
                    return_tensors="pt",
                    return_attention_mask=True,
                )

            # Move tensors to model device
            target_device = self._device if self._device != "cpu" else "cpu"
            for k, v in inputs.items():
                if torch.is_tensor(v):
                    inputs[k] = v.to(target_device)

            # Generate audio
            import copy
            with torch.no_grad():
                if self.model_size == "vibevoice-0.5b":
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=None,
                        cfg_scale=1.3,
                        tokenizer=self.processor.tokenizer,
                        generation_config={'do_sample': False},
                        verbose=False,
                        all_prefilled_outputs=copy.deepcopy(cached_prompt) if cached_prompt is not None else None,
                    )
                else:
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=None,
                        cfg_scale=1.3,
                        tokenizer=self.processor.tokenizer,
                        generation_config={"do_sample": False},
                        verbose=False,
                        is_prefill=True,
                    )

            # Save audio using processor
            if outputs.speech_outputs and outputs.speech_outputs[0] is not None:
                self.processor.save_audio(outputs.speech_outputs[0], output_path=output_path)
                print(f"✓ VibeVoice TTS: {output_filename}")
                return output_path
            else:
                print(f"❌ VibeVoice: no audio output generated")
                return None
        except Exception as e:
            import traceback
            print(f"❌ VibeVoice synthesis error: {e}")
            traceback.print_exc()
            return None

    def generate_segments(self, text: str, progress_callback=None, cancel_check=None) -> List[dict]:
        segments = self.segment_text(text)
        results = []
        for i, seg_text in enumerate(segments):
            if cancel_check:
                cancel_check()
            filename = self._generate_filename(seg_text)
            audio_path = self.synthesize(seg_text, output_filename=filename)
            if audio_path:
                results.append({"text": seg_text, "audio_path": audio_path})
            if progress_callback:
                progress_callback(i + 1, len(segments), seg_text)
        return results


# ── Qwen3-TTS ──────────────────────────────────────────────────────────

QWEN3_TTS_DIR = os.path.join(LOCAL_MODELS_DIR, "Qwen3-TTS")
QWEN3_TTS_REPO = "https://github.com/QwenLM/Qwen3-TTS.git"
QWEN3_TTS_MODELS = {
    "qwen3-tts-1.7b-custom": {
        "hf_id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "name": "Qwen3-TTS 1.7B Custom",
        "description": "Full model with 9 preset voices and style control.",
        "size": "~4.5 GB",
        "type": "custom",
    },
    "qwen3-tts-0.6b-custom": {
        "hf_id": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "name": "Qwen3-TTS 0.6B Custom",
        "description": "Smaller model with 9 preset voices. Fast.",
        "size": "~2.5 GB",
        "type": "custom",
    },
    "qwen3-tts-1.7b-design": {
        "hf_id": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "name": "Qwen3-TTS 1.7B Design",
        "description": "Full model for descriptive voice design.",
        "size": "~4.5 GB",
        "type": "design",
    },
    "qwen3-tts-1.7b-base": {
        "hf_id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "name": "Qwen3-TTS 1.7B Base",
        "description": "Base model for zero-shot voice cloning (requires ref audio).",
        "size": "~4.5 GB",
        "type": "base",
    },
    "qwen3-tts-0.6b-base": {
        "hf_id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "name": "Qwen3-TTS 0.6B Base",
        "description": "Smaller base model for voice cloning.",
        "size": "~2.5 GB",
        "type": "base",
    },
}

# Redirect generic keys to the most useful variants (CustomVoice)
QWEN3_TTS_MODELS["qwen3-tts-1.7b"] = QWEN3_TTS_MODELS["qwen3-tts-1.7b-custom"]
QWEN3_TTS_MODELS["qwen3-tts-0.6b"] = QWEN3_TTS_MODELS["qwen3-tts-0.6b-custom"]


def check_qwen3tts() -> dict:
    """Check if Qwen3-TTS is installed and ready."""
    status = {
        "installed": False,
        "repo_cloned": os.path.isdir(QWEN3_TTS_DIR),
        "model_downloaded": False,
        "python_deps": False,
        "details": "",
    }

    # Check transformers is available
    try:
        result = _run_cmd(
            [sys.executable, "-c", "import transformers; print(transformers.__version__)"],
            timeout=30,
        )
        status["python_deps"] = result["success"]
    except Exception:
        pass

    # Check which model weights are cached
    models_downloaded = []
    for model_key in QWEN3_TTS_MODELS:
        if os.path.isdir(os.path.join(LOCAL_MODELS_DIR, model_key)):
            models_downloaded.append(model_key)
    status["model_downloaded"] = len(models_downloaded) > 0
    status["models_downloaded"] = models_downloaded

    status["installed"] = status["python_deps"]
    if status["installed"]:
        status["details"] = "Ready" + (" (model cached)" if status["model_downloaded"] else " (model downloads on first use ~3GB)")
    else:
        status["details"] = "Missing: transformers, torch"

    return status


def install_qwen3tts() -> dict:
    """Install Qwen3-TTS dependencies."""
    os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)
    steps = []

    # 1. Clone repo (optional, for reference scripts)
    if not os.path.isdir(QWEN3_TTS_DIR):
        result = _run_cmd(
            ["git", "clone", "--depth", "1", QWEN3_TTS_REPO, QWEN3_TTS_DIR],
            timeout=120,
        )
        steps.append({"step": "clone_repo", **result})
    else:
        steps.append({"step": "clone_repo", "success": True, "stdout": "Already cloned", "stderr": ""})

    # 2. Install core deps
    result = _run_cmd(
        [sys.executable, "-m", "pip", "install", "transformers>=4.51.0", "torch", "soundfile", "accelerate", "huggingface_hub"],
        timeout=300,
    )
    steps.append({"step": "pip_install", **result})
    if not result["success"]:
        return {"success": False, "steps": steps, "error": "Failed to install dependencies"}

    # 3. Optional: install requirements from repo
    req_file = os.path.join(QWEN3_TTS_DIR, "requirements.txt")
    if os.path.exists(req_file):
        result = _run_cmd(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            timeout=300,
        )
        steps.append({"step": "repo_requirements", **result})

    return {"success": True, "steps": steps}


class Qwen3TTS:
    """Qwen3-TTS local inference wrapper."""

    AVAILABLE_VOICES = ["Default", "Warm", "Authoritative", "Calm", "Energetic"]

    def __init__(self, voice: str = "Default", model_size: str = "qwen3-tts-1.7b", output_dir: str = "audio", cancel_check=None):
        self.voice = voice
        self.model_size = model_size
        self.output_dir = output_dir
        self.cancel_check = cancel_check
        self.model = None
        self.tokenizer = None
        os.makedirs(output_dir, exist_ok=True)

    def _ensure_model(self):
        if self.model is not None:
            return
        try:
            from qwen_tts import Qwen3TTSModel
            
            # Resolve real model key (avoid aliases for folder names)
            model_key = self.model_size
            if model_key == "qwen3-tts-1.7b":
                model_key = "qwen3-tts-1.7b-custom"
            elif model_key == "qwen3-tts-0.6b":
                model_key = "qwen3-tts-0.6b-custom"
                
            model_info = QWEN3_TTS_MODELS.get(model_key, list(QWEN3_TTS_MODELS.values())[0])
            hf_id = model_info["hf_id"] if isinstance(model_info, dict) else model_info
            model_path = os.path.join(LOCAL_MODELS_DIR, model_key)
            
            if not os.path.isdir(model_path):
                print(f"📥 Downloading {self.model_size} model...")
                from huggingface_hub import snapshot_download
                snapshot_download(hf_id, local_dir=model_path)
            
            import torch
            # Determine device and dtype
            if torch.cuda.is_available():
                device = "cuda:0"
                dtype = torch.bfloat16
                attn_impl = "flash_attention_2"
            else:
                device = "cpu"
                dtype = torch.float32
                attn_impl = "sdpa"

            print(f"Loading Qwen3-TTS from {model_path} on {device}...")
            
            try:
                self.model = Qwen3TTSModel.from_pretrained(
                    model_path,
                    device_map=device,
                    dtype=dtype,
                    attn_implementation=attn_impl,
                )
            except Exception as e:
                if attn_impl == "flash_attention_2":
                    print(f"⚠ flash_attention_2 failed, falling back to sdpa: {e}")
                    self.model = Qwen3TTSModel.from_pretrained(
                        model_path,
                        device_map=device,
                        dtype=dtype,
                        attn_implementation="sdpa",
                    )
                else:
                    raise

            # Qwen3TTSModel in qwen-tts package handles its own tokenizer
            self.tokenizer = getattr(self.model, "tokenizer", None)
            
            print(f"✓ Qwen3-TTS model loaded ({self.model_size})")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Qwen3-TTS model load failed: {e}")
            raise RuntimeError(f"Qwen3-TTS not available: {e}")

    def _generate_filename(self, text: str) -> str:
        text_hash = hashlib.md5(f"{text}_{self.voice}".encode()).hexdigest()[:12]
        return f"qwen_{self.voice}_{text_hash}.wav"

    def segment_text(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []
        import re
        sentences = re.split(r'([.!?]+)', text)
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            combined.append(sentences[i] + sentences[i + 1])
        if len(sentences) % 2 == 1:
            combined.append(sentences[-1])
        return [s.strip() for s in combined if s.strip()]

    def synthesize(self, text: str, output_filename: Optional[str] = None, max_retries: int = 2) -> Optional[str]:
        if not text or not text.strip():
            return None

        if not output_filename:
            output_filename = self._generate_filename(text)
        output_path = os.path.join(self.output_dir, output_filename)

        if os.path.exists(output_path):
            return output_path

        if self.cancel_check:
            self.cancel_check()

        try:
            self._ensure_model()

            # Get model type
            model_info = QWEN3_TTS_MODELS.get(self.model_size, {})
            model_type = model_info.get("type", "custom")

            # Voice style mapping
            voice_configs = {
                "Default": {"speaker": "Vivian", "instruct": "Speak in a natural, neutral tone."},
                "Warm": {"speaker": "Vivian", "instruct": "Speak in a warm, friendly, and welcoming tone."},
                "Authoritative": {"speaker": "John", "instruct": "Speak in a clear, authoritative, and professional voice."},
                "Calm": {"speaker": "Vivian", "instruct": "Speak in a calm, soothing, and gentle manner."},
                "Energetic": {"speaker": "John", "instruct": "Speak with high energy, enthusiasm, and excitement."},
            }
            config = voice_configs.get(self.voice, voice_configs["Default"])

            # Generate based on model type
            import torch
            audio = None
            sr = 24000

            if model_type == "custom" and hasattr(self.model, "generate_custom_voice"):
                # Use CustomVoice model
                audio, sr = self.model.generate_custom_voice(
                    text=text,
                    language="English",
                    speaker=config["speaker"],
                    instruct=config["instruct"]
                )
            elif model_type == "design" and hasattr(self.model, "generate_voice_design"):
                # Use VoiceDesign model
                audio, sr = self.model.generate_voice_design(
                    text=text,
                    language="English",
                    instruct=config["instruct"]
                )
            elif model_type == "base" and hasattr(self.model, "generate_voice_clone"):
                # Use Base model - but this REQUIRES ref_audio. 
                # Since we don't have it, we'll try to use it with just instructions if it supports it, 
                # but it usually fails as seen in the user's log.
                # We'll try to provide a dummy instruction to see if it works as a fallback.
                try:
                    audio, sr = self.model.generate_voice_clone(
                        text=text,
                        language="English",
                        instruction=config["instruct"]
                    )
                except Exception as e:
                    raise RuntimeError(f"Base model requires reference audio for cloning. Please use a 'custom' or 'design' model variant. Error: {e}")
            else:
                # Generic fallback
                if hasattr(self.model, "generate_speech"):
                    audio = self.model.generate_speech(text, voice_prompt=config["instruct"])
                else:
                    inputs = self.tokenizer(text, return_tensors="pt")
                    audio = self.model.generate(**inputs)

            import soundfile as sf
            # Handle list of audios if returned
            if isinstance(audio, (list, tuple)):
                audio = audio[0]
            
            if hasattr(audio, 'cpu'):
                audio = audio.cpu().numpy()
            
            # Use sample rate from model if available
            sf.write(output_path, audio, sr)
            print(f"✓ Qwen3-TTS: {output_filename}")
            return output_path
        except Exception as e:
            print(f"❌ Qwen3-TTS synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_segments(self, text: str, progress_callback=None, cancel_check=None) -> List[dict]:
        segments = self.segment_text(text)
        results = []
        for i, seg_text in enumerate(segments):
            if cancel_check:
                cancel_check()
            filename = self._generate_filename(seg_text)
            audio_path = self.synthesize(seg_text, output_filename=filename)
            if audio_path:
                results.append({"text": seg_text, "audio_path": audio_path})
            if progress_callback:
                progress_callback(i + 1, len(segments), seg_text)
        return results
