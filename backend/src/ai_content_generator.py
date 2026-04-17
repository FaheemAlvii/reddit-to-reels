"""
AI Content Generator. Creates original content scripts for video reels.

Supports 4 content styles:
  - Story: First-person Reddit-style confessional stories
  - Q&A: Provocative questions with realistic comment answers
  - Interactive: "Put a finger down" challenges, quizzes with [PAUSE:N] markers
  - Hot Take: Controversial but safe opinion posts designed to drive engagement

Uses the existing AI provider infrastructure (Gemini/OpenRouter/Ollama/Nvidia NIM).

Author: Faheem Alvi
GitHub: https://github.com/FaheemAlvii
LinkedIn: https://www.linkedin.com/in/faheem-alvi
Email: faheemalvi2000@gmail.com
License: CC BY-NC 4.0
"""

import json
import os
import sys
import re
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

if getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from gemini_hooks import _call_ai, DEFAULT_OLLAMA_URL

# ── Niches ───────────────────────────────────────────────────────────

NICHES = {
    "relationship_drama": {
        "name": "Relationship Drama",
        "subs": "r/relationship_advice, r/AmItheAsshole, r/TIFU",
        "themes": "cheating, breakups, in-law conflicts, trust issues, secret discoveries",
    },
    "childhood_nostalgia": {
        "name": "Childhood Nostalgia",
        "subs": "r/AskReddit, r/nostalgia",
        "themes": "school memories, 90s/2000s kid experiences, embarrassing moments, first crushes",
    },
    "workplace_horror": {
        "name": "Workplace Horror",
        "subs": "r/antiwork, r/MaliciousCompliance, r/talesfromretail",
        "themes": "toxic bosses, quitting stories, revenge, unfair policies, coworker drama",
    },
    "dating_disasters": {
        "name": "Dating Disasters",
        "subs": "r/dating, r/Tinder, r/relationships",
        "themes": "worst dates, catfishing, ghosting, awkward encounters, dating app horror",
    },
    "family_secrets": {
        "name": "Family Secrets",
        "subs": "r/confessions, r/FamilyDrama",
        "themes": "hidden truths, adoption reveals, inheritance fights, double lives, DNA surprises",
    },
    "school_memories": {
        "name": "School Memories",
        "subs": "r/AskReddit, r/college",
        "themes": "teachers, bullying, pranks, graduation, friendships, detention stories",
    },
    "paranormal_encounters": {
        "name": "Paranormal Encounters",
        "subs": "r/nosleep, r/Paranormal, r/Glitch_in_the_Matrix",
        "themes": "ghost sightings, unexplained events, creepy encounters, sleep paralysis, haunted places",
    },
    "neighbor_stories": {
        "name": "Neighbor Stories",
        "subs": "r/neighborsfromhell, r/pettyrevenge",
        "themes": "boundary disputes, noise complaints, HOA wars, passive-aggressive notes, property drama",
    },
    "travel_nightmares": {
        "name": "Travel Nightmares",
        "subs": "r/travel, r/tifu",
        "themes": "missed flights, scams abroad, lost luggage, language barriers, sketchy hostels",
    },
    "food_culture": {
        "name": "Food & Culture",
        "subs": "r/AskReddit, r/food",
        "themes": "weird food combos, restaurant disasters, cultural food debates, cooking fails",
    },
}

# ── System Prompts ───────────────────────────────────────────────────

STORY_SYSTEM_PROMPT = """You are a viral Reddit storyteller. Write a first-person confessional story that sounds 100% authentic — like a real Reddit post.

RULES:
- Include specific details: names (fake), ages, locations, timestamps that make it feel real
- Build tension throughout the story with escalating conflict
- End with a cliffhanger, shocking twist, or emotional gut punch
- The narrator should be relatable but in an extraordinary situation
- Write in casual, conversational Reddit tone — not formal or polished
- 800-1500 characters total (for a short reel narration)
- NO emojis, NO hashtags, NO markdown, NO stage directions
- Do NOT include "AITA" or "TIFU" prefixes — just start the story naturally
- The content must be dramatic but NOT contain explicit sexual content or graphic violence

NICHE: {niche_name}
THEMES TO DRAW FROM: {niche_themes}
SUBREDDITS THIS WOULD FIT: {niche_subs}

{topic_instruction}

Output ONLY valid JSON with this exact structure:
{{"title": "A compelling Reddit-style title", "body": "The full story text..."}}"""

QA_SYSTEM_PROMPT = """You are writing a viral AskReddit-style thread. Create ONE attention-grabbing question and realistic "comment" answers from different users.

RULES:
- The question should be the kind that makes people NEED to answer — provocative, relatable, or thought-provoking
- Each answer should be 100-300 characters, dramatic but believable
- Give each commenter a realistic Reddit-style username
- Answers should vary in tone: some funny, some serious, some shocking
- 5-7 answers total
- NO emojis, NO hashtags, NO markdown formatting
- Content should be engaging but NOT contain explicit content

NICHE: {niche_name}
THEMES TO DRAW FROM: {niche_themes}
SUBREDDITS THIS WOULD FIT: {niche_subs}

{topic_instruction}

Output ONLY valid JSON with this exact structure:
{{"title": "The AskReddit question as the title", "question": "Same question or expanded version", "comments": [{{"author": "username123", "body": "Their answer..."}}, ...]}}"""

INTERACTIVE_SYSTEM_PROMPT = """You are a viral short-form video content creator specializing in interactive engagement content.

Create a "{format_type}" challenge/quiz that hooks viewers and makes them participate.

FORMATS:
- "put_a_finger_down": Write 8-12 statements starting with "Put a finger down if..." from common to rare. End with a scoring punchline.
- "would_you_rather": Write 6-8 impossible "Would you rather" dilemmas. Each should be genuinely hard to choose.
- "rate_yourself": Write 8-10 "Give yourself a point if..." statements. End with a rating scale result.
- "guess_the_answer": Write 5-6 trivia/riddle questions. Give the answer after a pause.

RULES:
- Each statement/question MUST be followed by [PAUSE:3] to give viewers time to think/respond
- Make it RELATABLE — viewers should feel personally called out
- Order from common/mild to rare/extreme for maximum engagement
- End with a fun scoring result or punchline
- NO emojis, NO hashtags
- Keep each individual statement under 200 characters
- Total content should fill a 45-90 second video

NICHE: {niche_name}
THEMES TO DRAW FROM: {niche_themes}

{topic_instruction}

Output ONLY valid JSON with this exact structure:
{{"title": "Catchy title for the challenge", "segments": [{{"text": "Put a finger down if...", "pause_seconds": 3}}, ...]}}

The LAST segment should be the scoring punchline (with pause_seconds: 0)."""

HOT_TAKE_SYSTEM_PROMPT = """You are a viral opinion writer who crafts controversial but SAFE takes — the kind that get thousands of comments because everyone has a strong reaction.

RULES:
- The opinion should be genuinely debatable — NOT obviously right or wrong
- Write 400-800 characters defending the take in a passionate, conversational tone
- It should feel like a real Reddit rant/confession
- Make readers immediately want to agree OR argue — no lukewarm takes
- Stay away from politics, religion, or genuinely harmful topics
- Focus on everyday life controversies: food, relationships, social norms, pop culture
- NO emojis, NO hashtags, NO markdown

NICHE: {niche_name}
THEMES TO DRAW FROM: {niche_themes}

{topic_instruction}

Output ONLY valid JSON with this exact structure:
{{"title": "The hot take as a bold statement", "body": "The full opinion/rant defending it..."}}"""

# Interactive format types
INTERACTIVE_FORMATS = [
    {"id": "put_a_finger_down", "name": "Put a Finger Down", "desc": "Relatable statement challenge"},
    {"id": "would_you_rather", "name": "Would You Rather", "desc": "Impossible choice dilemmas"},
    {"id": "rate_yourself", "name": "Rate Yourself", "desc": "Point-based self-rating quiz"},
    {"id": "guess_the_answer", "name": "Guess the Answer", "desc": "Trivia & riddles with reveals"},
]


# ── Content Generator ────────────────────────────────────────────────

class AIContentGenerator:
    """Generates original viral content using AI models."""

    def __init__(self, config: dict):
        """Initialize from the app's config.json."""
        gemini_cfg = config.get("gemini", {})
        self.provider = gemini_cfg.get("provider", "gemini")
        self.model = gemini_cfg.get("model", "gemini-2.0-flash")
        self.ollama_url = gemini_cfg.get("ollama_url", DEFAULT_OLLAMA_URL)

        # Pick API key based on provider
        if self.provider == "ollama":
            self.api_key = ""
        elif self.provider == "openrouter":
            self.api_key = gemini_cfg.get("openrouter_api_key", "")
            if not self.model or self.model.startswith("gemini"):
                self.model = "google/gemini-2.0-flash-exp:free"
        elif self.provider == "nvidia_nim":
            self.api_key = gemini_cfg.get("nvidia_nim_api_key", "")
            if not self.model:
                self.model = "meta/llama-3.1-405b-instruct"
        else:
            self.api_key = gemini_cfg.get("api_key", "")

        self.used_topics_path = os.path.join(PROJECT_ROOT, "used_topics.json")

    def _load_used_topics(self) -> List[str]:
        if os.path.exists(self.used_topics_path):
            try:
                with open(self.used_topics_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_topic(self, topic_summary: str):
        topics = self._load_used_topics()
        topics.append(topic_summary)
        # Keep last 100
        topics = topics[-100:]
        with open(self.used_topics_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, indent=2)

    def _topic_instruction(self, custom_topic: Optional[str] = None) -> str:
        recent = self._load_used_topics()[-20:]
        parts = []
        if custom_topic:
            parts.append(f"SPECIFIC TOPIC TO WRITE ABOUT: {custom_topic}")
        if recent:
            parts.append("AVOID these recently used themes (do NOT repeat):\n- " + "\n- ".join(recent))
        return "\n\n".join(parts) if parts else "Choose a fresh, unique angle."

    def _call(self, prompt: str, system_prompt: str, max_tokens: int = 1500) -> Optional[str]:
        """Call the AI provider with higher token limit for content generation."""
        # We reuse _call_ai but content generation needs more tokens
        # The underlying providers have their own defaults; we rely on the prompt to control length
        return _call_ai(self.provider, self.api_key, prompt, system_prompt, self.model, self.ollama_url)

    def _parse_json_response(self, raw: str) -> Optional[dict]:
        """Extract and parse JSON from AI response, handling markdown code blocks and thinking tags."""
        if not raw:
            return None
        # Strip <think>...</think> reasoning blocks
        cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        # Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _generate_with_retry(self, prompt: str, system_prompt: str, required_keys: List[str], retries: int = 3) -> Optional[dict]:
        """Generate content with retry logic for JSON parsing failures."""
        for attempt in range(retries):
            raw = self._call(prompt, system_prompt)
            if not raw:
                print(f"⚠️  AI returned empty (attempt {attempt + 1}/{retries})")
                continue

            parsed = self._parse_json_response(raw)
            if parsed and all(k in parsed for k in required_keys):
                return parsed

            print(f"⚠️  Invalid JSON or missing keys (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                # Reinforce JSON requirement
                prompt = prompt + "\n\nIMPORTANT: Output ONLY valid JSON. No extra text before or after the JSON object."
                time.sleep(2)

        return None

    # ── Public generators ────────────────────────────────────────────

    def generate_story(self, niche: str, custom_topic: Optional[str] = None) -> Optional[dict]:
        """Generate a story-mode post. Returns {title, body} or None."""
        niche_info = NICHES.get(niche, NICHES["relationship_drama"])
        system = STORY_SYSTEM_PROMPT.format(
            niche_name=niche_info["name"],
            niche_themes=niche_info["themes"],
            niche_subs=niche_info["subs"],
            topic_instruction=self._topic_instruction(custom_topic),
        )
        prompt = f"Write a viral Reddit story in the {niche_info['name']} niche. Make it unforgettable."

        result = self._generate_with_retry(prompt, system, ["title", "body"])
        if result:
            self._save_topic(f"Story: {result['title'][:80]}")
        return result

    def generate_qa(self, niche: str, custom_topic: Optional[str] = None, num_answers: int = 6) -> Optional[dict]:
        """Generate a Q&A post. Returns {title, question, comments[]} or None."""
        niche_info = NICHES.get(niche, NICHES["relationship_drama"])
        system = QA_SYSTEM_PROMPT.format(
            niche_name=niche_info["name"],
            niche_themes=niche_info["themes"],
            niche_subs=niche_info["subs"],
            topic_instruction=self._topic_instruction(custom_topic),
        )
        prompt = f"Write a viral AskReddit thread in the {niche_info['name']} niche with {num_answers} answers."

        result = self._generate_with_retry(prompt, system, ["title", "comments"])
        if result:
            self._save_topic(f"Q&A: {result['title'][:80]}")
            # Ensure question field exists
            if "question" not in result:
                result["question"] = result["title"]
        return result

    def generate_interactive(self, niche: str, format_type: str = "put_a_finger_down",
                             custom_topic: Optional[str] = None) -> Optional[dict]:
        """Generate interactive engagement content. Returns {title, segments[{text, pause_seconds}]} or None."""
        niche_info = NICHES.get(niche, NICHES["childhood_nostalgia"])
        fmt = next((f for f in INTERACTIVE_FORMATS if f["id"] == format_type), INTERACTIVE_FORMATS[0])

        system = INTERACTIVE_SYSTEM_PROMPT.format(
            format_type=fmt["name"],
            niche_name=niche_info["name"],
            niche_themes=niche_info["themes"],
            topic_instruction=self._topic_instruction(custom_topic),
        )
        prompt = f"Create a '{fmt['name']}' challenge video about {niche_info['name']}."

        result = self._generate_with_retry(prompt, system, ["title", "segments"])
        if result:
            self._save_topic(f"Interactive ({fmt['name']}): {result['title'][:60]}")
            # Ensure segments have pause_seconds
            for seg in result.get("segments", []):
                if "pause_seconds" not in seg:
                    seg["pause_seconds"] = 3
        return result

    def generate_hot_take(self, niche: str, custom_topic: Optional[str] = None) -> Optional[dict]:
        """Generate a hot take / opinion post. Returns {title, body} or None."""
        niche_info = NICHES.get(niche, NICHES["relationship_drama"])
        system = HOT_TAKE_SYSTEM_PROMPT.format(
            niche_name=niche_info["name"],
            niche_themes=niche_info["themes"],
            topic_instruction=self._topic_instruction(custom_topic),
        )
        prompt = f"Write a controversial but safe hot take about {niche_info['name']}."

        result = self._generate_with_retry(prompt, system, ["title", "body"])
        if result:
            self._save_topic(f"Hot Take: {result['title'][:80]}")
        return result

    def generate(self, content_style: str, niche: str,
                 custom_topic: Optional[str] = None,
                 interactive_format: str = "put_a_finger_down") -> Optional[dict]:
        """
        Unified entry point. Returns the generated content dict or None.
        Adds a 'content_style' key to the result for downstream processing.
        """
        if content_style == "story":
            result = self.generate_story(niche, custom_topic)
        elif content_style == "qa":
            result = self.generate_qa(niche, custom_topic)
        elif content_style == "interactive":
            result = self.generate_interactive(niche, interactive_format, custom_topic)
        elif content_style == "hot_take":
            result = self.generate_hot_take(niche, custom_topic)
        else:
            print(f"❌ Unknown content style: {content_style}")
            return None

        if result:
            result["content_style"] = content_style
        return result


# ── Helpers for external use ─────────────────────────────────────────

def get_available_niches() -> List[dict]:
    """Return list of available niches for the UI."""
    return [{"id": k, "name": v["name"], "themes": v["themes"]} for k, v in NICHES.items()]

def get_interactive_formats() -> List[dict]:
    """Return list of interactive format types for the UI."""
    return INTERACTIVE_FORMATS
