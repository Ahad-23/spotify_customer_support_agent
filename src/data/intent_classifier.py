"""
Domain-specific intent classifier for SpotifyCares customer support issues.
"""

import re
from typing import Dict, List, Tuple

INTENT_RULES: List[Tuple[str, re.Pattern]] = [
    (
        "device_connectivity",
        re.compile(
            r"\b(spotify connect|connect to|chromecast|alexa|echo|google home|sonos|smart tv|roku|firestick|playstation|ps4|ps5|xbox|apple watch|wear os)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "offline_downloads",
        re.compile(
            r"\b(offline|download|downloading|downloaded|downloads|sync|syncing|greyed out|grayed out|storage|sd card|offline songs|disappeared)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "subscription_billing",
        re.compile(
            r"\b(cancel|canceling|cancelling|charge|charged|charging|bill|billed|billing|refund|receipt|payment|credit card|debit card|gift card|(?<!sd\s)card|sub|subscription|premium plan|family plan|student discount|duo|free trial|renew|bank)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "playback_audio",
        re.compile(
            r"\b(skipping|skips|skip|pause|pausing|pauses|stutter|stuttering|glitch|sound|volume|bluetooth|speaker|headphones|airplay|carplay|aux|static|crackle|audio quality|won't play|stopping|stops)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "playlist_library",
        re.compile(
            r"\b(playlist|playlists|liked songs|your library|recover playlist|deleted playlist|queue|shuffle|repeat|local files|daily mix|discover weekly|release radar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "account_login",
        re.compile(
            r"\b(log in|login|logging in|sign in|signin|password|reset password|email address|hacked|account hacked|username|verification|two factor|2fa|credentials|locked out)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "app_crash_freeze",
        re.compile(
            r"\b(crash|crashes|crashing|freeze|freezes|freezing|frozen|black screen|blank screen|won't open|wont open|closes automatically|force close|force stop|keeps stopping)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "content_catalog",
        re.compile(
            r"\b(missing song|missing album|artist|podcast|podcasts|lyrics|explicit|censored|unavailable in your country|region lock|rights)\b",
            re.IGNORECASE,
        ),
    ),
]



def classify_intent(text: str) -> str:
    """
    Classifies a customer inquiry into a Spotify support intent category.
    """
    if not text:
        return "general_inquiry"

    for intent, pattern in INTENT_RULES:
        if pattern.search(text):
            return intent

    return "general_inquiry"
