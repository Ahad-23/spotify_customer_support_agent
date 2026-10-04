"""
Text cleaning and sanitization utilities for Twitter Customer Support dialogues.
"""

import html
import re
from typing import Tuple

# Matches agent signatures like /AY, /CP, ^HP, ^RR at end of message
SIGNATURE_PATTERN = re.compile(r"\s*[/^][A-Za-z]{2,4}\.?\s*$", re.IGNORECASE)

# Matches leading Twitter handles (@username or @12345)
LEADING_MENTIONS_PATTERN = re.compile(r"^(\s*@\w+)+\s*", re.UNICODE)

# Matches internal mentions (@12345 or @SpotifyCares)
INTERNAL_MENTION_PATTERN = re.compile(r"@(\d+)", re.UNICODE)
BRAND_MENTION_PATTERN = re.compile(r"@SpotifyCares", re.IGNORECASE)

# Matches multiple whitespaces/newlines
WHITESPACE_PATTERN = re.compile(r"[ \t]+", re.UNICODE)
MULTI_NEWLINE_PATTERN = re.compile(r"\n\s*\n+", re.UNICODE)

# Common DM deflection phrasing
DM_DEFLECTION_PATTERN = re.compile(
    r"\b(dm us|send us a dm|direct message|pm us|drop us a dm|reach out via dm|inbox us|dm me|send a dm)\b",
    re.IGNORECASE
)

# Troubleshooting indicators in Spotify agent responses
TROUBLESHOOTING_PATTERN = re.compile(
    r"\b(reinstall|clean reinstall|restart|log out|log in|cache|offline|bluetooth|settings|version|spoti\.fi|update|storage|device|connection|wifi|uninstall|permission)\b",
    re.IGNORECASE
)

# Actionable advice keywords (preferred over diagnostic clarifying questions)
ACTIONABLE_SOLUTION_PATTERN = re.compile(
    r"\b(logging out|restarting|restart|clean reinstall|reinstall|clear cache|check if|make sure|toggle|try|steps here|can you try|head over to|spoti\.fi|go to settings)\b",
    re.IGNORECASE
)


def score_agent_resolution(text: str) -> int:
    """
    Scores an agent message: higher score means higher diagnostic/actionable value.
    Actionable advice (e.g. restart, clean reinstall) scores higher than questions.
    """
    if not text:
        return 0
    score = 0
    if ACTIONABLE_SOLUTION_PATTERN.search(text):
        score += 5
    if TROUBLESHOOTING_PATTERN.search(text):
        score += 2
    if DM_DEFLECTION_PATTERN.search(text):
        score -= 3
    return score



def clean_tweet_text(text: str, is_agent: bool = False) -> str:
    """
    Cleans a tweet message by removing leading mentions, agent sign-offs,
    and normalizing whitespace and HTML entities.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unescape HTML entities (&amp; -> &, &gt; -> >, etc.)
    text = html.unescape(text)

    # 2. Strip agent signatures (/AY, ^RR, etc.)
    if is_agent:
        text = SIGNATURE_PATTERN.sub("", text.strip())

    # 3. Strip leading @mentions
    text = LEADING_MENTIONS_PATTERN.sub("", text)

    # 4. Normalize brand mentions and user IDs in the text
    text = BRAND_MENTION_PATTERN.sub("Spotify", text)
    text = INTERNAL_MENTION_PATTERN.sub("user", text)

    # 5. Normalize whitespace
    text = WHITESPACE_PATTERN.sub(" ", text)
    text = MULTI_NEWLINE_PATTERN.sub("\n", text)

    return text.strip()


def analyze_agent_response(text: str) -> Tuple[bool, bool]:
    """
    Analyzes an agent tweet to determine:
    - is_deflection: True if the response primarily deflects to private DM
    - has_troubleshooting: True if actionable diagnostic steps or help are provided
    """
    if not text:
        return False, False

    is_deflect = bool(DM_DEFLECTION_PATTERN.search(text))
    has_troubleshoot = bool(TROUBLESHOOTING_PATTERN.search(text))

    return is_deflect, has_troubleshoot


def sanitize_solution_text(text: str) -> str:
    """
    Cleans raw historical support resolutions into neutral, actionable troubleshooting
    steps without historical customer names (e.g. 'Harry'), Twitter handles, or sign-offs.
    """
    if not text or not isinstance(text, str):
        return ""

    s = html.unescape(text).strip()

    # 1. Remove agent signatures (/AY, ^RR, etc.)
    s = SIGNATURE_PATTERN.sub("", s)

    # 2. Remove leading @mentions
    s = LEADING_MENTIONS_PATTERN.sub("", s)

    # 3. Remove personalized customer greetings: e.g. "Hi Harry!", "Hey there,", "Hello Sarah -"
    s = re.sub(r"^(?:Hi|Hey|Hello|Dear)\s+[\w\s.-]+?[!.,:\-–]\s*", "", s, flags=re.I)

    # 4. Remove support intro slogans: e.g. "Help's here.", "Spotify Support here!", "We're here to help."
    s = re.sub(r"^(?:Help's here|Help is here|Spotify Support here|Spotify here|We're here to help)[!.,:\-–]\s*", "", s, flags=re.I)

    # 5. Remove trailing sign-offs: e.g. "Keep us posted!", "Let us know how it goes", "Cheers"
    s = re.sub(
        r"(?:Keep us posted|Let us know(?: how it goes| once you've given this a shot)?|Let me know|Hope this helps|Cheers|Keep us updated)[!.,:]?\s*$",
        "",
        s,
        flags=re.I,
    )

    # 6. Convert action arrow notations: e.g. "logging out > restarting your device > logging back in"
    def _arrow_action_replacer(match: re.Match) -> str:
        parts = [p.strip() for p in match.group(0).split(">") if p.strip()]
        if len(parts) >= 2 and any(p.lower().endswith("ing") for p in parts):
            return ", ".join(parts[:-1]) + f", and {parts[-1]}"
        return match.group(0)

    s = re.sub(r"[\w\s]+(?:\s*>\s*[\w\s]+){2,}", _arrow_action_replacer, s)

    # 7. Normalize brand mentions & whitespace
    s = BRAND_MENTION_PATTERN.sub("Spotify", s)
    s = INTERNAL_MENTION_PATTERN.sub("user", s)
    s = WHITESPACE_PATTERN.sub(" ", s).strip()

    # 8. Ensure capitalization
    if s and s[0].islower():
        s = s[0].upper() + s[1:]

    return s

