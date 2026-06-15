"""
utils/profile.py

Style profile memory — persist a user's wardrobe and style preferences
to a local JSON file so they don't have to re-enter them each session.

Usage:
    from utils.profile import save_profile, load_profile

    # Save after the user sets up their wardrobe
    save_profile(wardrobe=get_example_wardrobe(), style_notes="I love Y2K and cottagecore.")

    # Load at the start of a new session
    profile = load_profile()
    wardrobe = profile["wardrobe"]       # dict with "items" key
    notes    = profile["style_notes"]    # free-text preferences string
"""

from __future__ import annotations

import json
import os
from datetime import datetime

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "user_profile.json")


def save_profile(wardrobe: dict, style_notes: str = "") -> None:
    """
    Save the user's wardrobe and style notes to user_profile.json.

    Args:
        wardrobe:    A wardrobe dict with an "items" key.
        style_notes: Optional free-text string describing the user's style
                     preferences (e.g. "I love Y2K and cottagecore. I mostly
                     wear oversized fits.").
    """
    profile = {
        "wardrobe": wardrobe,
        "style_notes": style_notes,
        "saved_at": datetime.now().isoformat(),
    }
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    print(f"Profile saved to {os.path.abspath(_PROFILE_PATH)}")


def load_profile() -> dict | None:
    """
    Load the user's saved profile from user_profile.json.

    Returns:
        A dict with keys "wardrobe", "style_notes", and "saved_at",
        or None if no profile file exists yet.
    """
    if not os.path.exists(_PROFILE_PATH):
        return None
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def profile_exists() -> bool:
    """Return True if a saved profile file exists."""
    return os.path.exists(_PROFILE_PATH)
