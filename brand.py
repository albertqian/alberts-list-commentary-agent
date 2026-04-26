"""
brand.py — shared constants for Albert's List automation
Used by main.py (GitHub Actions) and thumbnail_app.py (local Streamlit).
Fonts are loaded from the repo's /fonts directory so the app works on
any OS without system font dependencies.
"""

from pathlib import Path

# Repo root = directory containing this file
REPO_ROOT = Path(__file__).parent

# Fonts — bundled in /fonts so they work on Mac, Windows, Linux
FONTS = {
    "bold":    str(REPO_ROOT / "fonts" / "Poppins-Bold.ttf"),
    "medium":  str(REPO_ROOT / "fonts" / "Poppins-Medium.ttf"),
    "regular": str(REPO_ROOT / "fonts" / "Poppins-Regular.ttf"),
}

BRAND = {
    "bg":         (10, 14, 26),    # deep navy
    "accent":     (245, 166, 35),  # Albert's List amber/gold
    "white":      (255, 255, 255),
    "light_grey": (176, 184, 204),
    "red_bar":    (229, 57, 53),   # date badge red
    "dark_panel": (18, 25, 48),    # geometric accent panel
    "face_bg":    (16, 22, 50),    # face zone background
}

# Headshot — drop headshot.png in repo root to enable face composite
HEADSHOT_PATH = REPO_ROOT / "headshot.png"
