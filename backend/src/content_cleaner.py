"""
Content Cleaner — replaces profanity / offensive words with
family-friendly alternatives that remain understandable.

Usage:
    from content_cleaner import clean_profanity
    cleaned = clean_profanity("What the fuck is this shit?")
    # → "What the flip is this stuff?"
"""

import re
from typing import Dict, List, Tuple

# ── Word replacement map ────────────────────────────────────────────
# Each key is the base/root word (lowercase).
# Value is the clean replacement.
# We also generate common inflections automatically.

_BASE_REPLACEMENTS: Dict[str, str] = {
    # F-words
    "fuck": "flip",
    "fucker": "flipper",
    "fucked": "flipped",
    "fucking": "flipping",
    "fuckin": "flippin",
    "fucks": "flips",
    "fuckery": "foolery",
    "motherfucker": "motherfluffer",
    "motherfucking": "motherfluffing",
    "motherfuckers": "motherfluffers",
    "mf": "mfer",
    "stfu": "shush",
    "gtfo": "get out",
    "wtf": "what the heck",

    # S-words
    "shit": "stuff",
    "shitty": "crappy",
    "shits": "stuffs",
    "shitting": "messing",
    "bullshit": "nonsense",
    "horseshit": "nonsense",
    "dipshit": "dimwit",

    # A-words
    "ass": "butt",
    "asses": "butts",
    "asshole": "jerk",
    "assholes": "jerks",
    "badass": "tough",
    "dumbass": "dummy",
    "smartass": "smarty",
    "jackass": "fool",
    "fatass": "big guy",
    "lmao": "haha",
    "lmfao": "haha",

    # B-words
    "bitch": "witch",
    "bitches": "witches",
    "bitching": "whining",
    "bitchy": "cranky",
    "son of a bitch": "son of a gun",

    # D-words
    "damn": "dang",
    "damned": "danged",
    "damnit": "dangit",
    "dammit": "dangit",
    "goddamn": "goshdarn",
    "goddamnit": "goshdarnit",
    "goddamned": "goshdarned",
    "dick": "jerk",
    "dicks": "jerks",
    "dickhead": "blockhead",

    # H-words
    "hell": "heck",
    "hellish": "horrible",
    "what the hell": "what the heck",
    "go to hell": "go away",

    # C-words
    "crap": "crud",
    "crappy": "lousy",
    "cock": "rooster",
    "cocks": "roosters",
    "cocksucker": "loser",
    "cunt": "jerk",
    "cunts": "jerks",

    # P-words
    "piss": "tinkle",
    "pissed": "ticked",
    "pissing": "messing",
    "pissed off": "ticked off",
    "pussy": "wimp",

    # Slurs & heavy offense (replace with neutral)
    "retard": "fool",
    "retarded": "ridiculous",
    "retards": "fools",
    "nigga": "buddy",
    "niggas": "buddies",
    "nigger": "person",
    "niggers": "people",

    # Drug / substance references (light clean)
    "weed": "herb",
    "stoner": "chiller",

    # Other
    "whore": "person",
    "slut": "person",
    "skank": "person",
    "bastard": "rascal",
    "bastards": "rascals",
    "douche": "fool",
    "douchebag": "fool",
    "twat": "fool",
    "wanker": "fool",
    "bloody": "dang",
    "bollocks": "nonsense",
    "arse": "butt",
    "arsehole": "jerk",
    "suck my": "kiss my",
    "sucks": "stinks",
    "suck": "stink",
    "freaking": "freaking",  # already clean, kept for completeness
    "frickin": "frickin",
    "freakin": "freakin",
}


def _build_pattern(replacements: Dict[str, str]) -> List[Tuple[re.Pattern, str]]:
    """
    Build compiled regex patterns sorted by length (longest first)
    so multi-word phrases match before single words.
    """
    patterns = []
    # Sort by length descending so "son of a bitch" matches before "bitch"
    for word in sorted(replacements, key=len, reverse=True):
        replacement = replacements[word]
        # Word boundary pattern, case-insensitive
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        patterns.append((pattern, replacement))
    return patterns


_COMPILED_PATTERNS = _build_pattern(_BASE_REPLACEMENTS)


def _match_case(original: str, replacement: str) -> str:
    """Preserve the casing style of the original word."""
    if original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def clean_profanity(text: str) -> str:
    """
    Replace profanity in *text* with family-friendly alternatives.
    Preserves original casing style (UPPER, Title, lower).
    """
    for pattern, replacement in _COMPILED_PATTERNS:
        def _replacer(m, repl=replacement):
            return _match_case(m.group(0), repl)
        text = pattern.sub(_replacer, text)
    return text


# ── Quick test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    samples = [
        "What the fuck is this shit?",
        "That asshole is such a dumbass.",
        "HOLY SHIT that was Fucking amazing!",
        "Son of a bitch, this is bullshit.",
        "Go to hell you little bitch!",
        "Damn, that's a badass move.",
        "This pissed me off so goddamn much.",
    ]
    for s in samples:
        print(f"  IN: {s}")
        print(f" OUT: {clean_profanity(s)}")
        print()
