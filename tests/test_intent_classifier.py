"""
Comprehensive unit and boundary tests for domain-specific intent classification.
"""

import pytest
from src.data.intent_classifier import classify_intent


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        # 1. Billing & Subscription
        ("How do I cancel my Spotify Premium subscription?", "subscription_billing"),
        ("I was charged twice on my credit card receipt this month", "subscription_billing"),
        ("Can I upgrade to a student discount or family plan?", "subscription_billing"),
        ("Where can I request a refund for an accidental charge?", "subscription_billing"),
        ("My bank blocked the payment for Spotify Duo", "subscription_billing"),
        
        # 2. Offline Downloads
        ("My downloaded songs disappeared when in offline mode", "offline_downloads"),
        ("Playlists are greyed out and won't sync to my SD card", "offline_downloads"),
        ("Cannot download tracks to external storage on Android", "offline_downloads"),
        ("Songs won't sync for offline listening", "offline_downloads"),
        
        # 3. Playback & Audio
        ("My music keeps skipping constantly on my bluetooth speaker", "playback_audio"),
        ("Songs randomly pause whenever I listen with headphones", "playback_audio"),
        ("Awful static crackle and glitch when streaming over AirPlay", "playback_audio"),
        ("Tracks won't play or stop after 10 seconds", "playback_audio"),
        
        # 4. Playlist & Library
        ("How can I recover a deleted playlist from my library?", "playlist_library"),
        ("Shuffle keeps repeating the same 5 songs in my liked songs", "playlist_library"),
        ("Queue is not showing my local files", "playlist_library"),
        
        # 5. Account & Authentication
        ("I forgot my password and cannot log in to my account", "account_login"),
        ("Need to reset password for my email address", "account_login"),
        ("I suspect my account was hacked, username changed", "account_login"),
        ("Locked out by two factor 2fa verification code", "account_login"),
        
        # 6. App Crash & Freeze
        ("Spotify app keeps crashing and freezing on Windows 11", "app_crash_freeze"),
        ("Black screen when opening the app, it force closes automatically", "app_crash_freeze"),
        ("The desktop client keeps freezing when loading", "app_crash_freeze"),
        
        # 7. Device Connectivity
        ("Spotify Connect won't connect to my Sonos speaker", "device_connectivity"),
        ("Cannot cast to my Chromecast on the TV", "device_connectivity"),
        ("Echo Alexa won't find Spotify device on WiFi", "device_connectivity"),
        ("Spotify on PlayStation PS5 won't link", "device_connectivity"),
        
        # 8. Content Catalog
        ("Why is this album missing from the artist page?", "content_catalog"),
        ("Certain tracks are unavailable in your country due to rights", "content_catalog"),
        ("Missing lyrics for new release podcasts", "content_catalog"),
        
        # 9. General Inquiry / Fallbacks
        ("Hello, what are your support hours today?", "general_inquiry"),
        ("Can you help me with a general question?", "general_inquiry"),
        ("", "general_inquiry"),
        ("   ", "general_inquiry"),
        (None, "general_inquiry"),
    ],
)
def test_classify_intent_comprehensive(query, expected_intent):
    assert classify_intent(query) == expected_intent


def test_sd_card_vs_credit_card_boundary():
    # Crucial boundary: "SD card" should be offline_downloads, NOT billing
    sd_query = "Downloaded songs are not saving to my SD card"
    assert classify_intent(sd_query) == "offline_downloads"

    # "Credit card" should be subscription_billing
    cc_query = "Update credit card details for subscription"
    assert classify_intent(cc_query) == "subscription_billing"


def test_connect_speaker_vs_bluetooth_speaker_boundary():
    # "Spotify Connect won't find Sonos" -> device_connectivity (Connect prioritized)
    connect_query = "Spotify Connect won't detect my Sonos speaker"
    assert classify_intent(connect_query) == "device_connectivity"

    # "Bluetooth speaker skipping" -> playback_audio
    bt_query = "Music keeps skipping on my bluetooth speaker"
    assert classify_intent(bt_query) == "playback_audio"
