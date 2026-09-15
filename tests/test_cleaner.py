"""
Unit tests for Twitter dialogue text cleaner and heuristics.
"""

import pytest
from src.data.cleaner import (
    analyze_agent_response,
    clean_tweet_text,
    score_agent_resolution,
)


@pytest.mark.parametrize(
    "input_text,expected",
    [
        ("Please restart your device and let us know /AY", "Please restart your device and let us know"),
        ("Try a clean reinstall ^RR", "Try a clean reinstall"),
        ("Head to settings and clear cache /CP.", "Head to settings and clear cache"),
        ("Check your offline songs ^HP. ", "Check your offline songs"),
        ("Does this happen on other tracks? /ay", "Does this happen on other tracks?"),
    ],
)
def test_clean_tweet_text_signatures(input_text, expected):
    assert clean_tweet_text(input_text, is_agent=True) == expected


def test_clean_tweet_text_multi_mentions():
    msg = "@105840 @SpotifyCares @99999 Hey @SpotifyCares my app is broken"
    cleaned = clean_tweet_text(msg, is_agent=False)
    # Leading mentions stripped; internal @SpotifyCares replaced with Spotify
    assert cleaned == "Hey Spotify my app is broken"


def test_clean_tweet_text_html_entities():
    msg = "I&quot;m having issues &amp; problems with &lt;rock&gt; songs &apos;70s"
    cleaned = clean_tweet_text(msg, is_agent=False)
    assert cleaned == "I\"m having issues & problems with <rock> songs '70s"


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\t  \n", None])
def test_clean_tweet_text_empty(empty_input):
    assert clean_tweet_text(empty_input) == ""


@pytest.mark.parametrize(
    "deflection_text",
    [
        "Please send us a DM with your account email address.",
        "Drop us a dm and we'll check backstage.",
        "Shoot us a direct message so we can help.",
        "Reach out via DM with your username.",
        "PM us your receipt details.",
    ],
)
def test_analyze_agent_response_deflections(deflection_text):
    is_deflect, has_trouble = analyze_agent_response(deflection_text)
    assert is_deflect is True


@pytest.mark.parametrize(
    "troubleshooting_text",
    [
        "Could you try performing a clean reinstall of the app?",
        "Does clearing your cache in the settings make a difference?",
        "Make sure offline storage permissions are toggled on.",
        "Try unpairing and repairing your bluetooth headphones.",
        "Restart your device and check if you are connected to WiFi.",
    ],
)
def test_analyze_agent_response_troubleshooting_cases(troubleshooting_text):
    is_deflect, has_trouble = analyze_agent_response(troubleshooting_text)
    assert has_trouble is True


def test_score_agent_resolution_hierarchies():
    actionable = "Try logging out > restarting your device > logging back in."
    diagnostic = "What operating system and Spotify version are you using?"
    deflective = "Please send us a DM with your username."
    empty = ""

    score_act = score_agent_resolution(actionable)
    score_diag = score_agent_resolution(diagnostic)
    score_def = score_agent_resolution(deflective)
    score_emp = score_agent_resolution(empty)

    # Actionable instructions score higher than questions or deflections
    assert score_act > score_diag
    assert score_diag >= score_def
    assert score_emp == 0
