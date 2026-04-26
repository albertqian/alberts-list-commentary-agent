"""
Albert's List — Thumbnail Generator
────────────────────────────────────
Streamlit app. Paste title + hook text from your 3 PM email → download 1280×720 PNG.

FIRST-TIME SETUP:
  pip install streamlit pillow
  # Drop headshot.png in this folder (same directory as this file)
  streamlit run thumbnail_app.py

DAILY USE (~30 seconds):
  1. Open http://localhost:8501
  2. Paste title from email
  3. Paste thumbnail hook text from email
  4. Generate → Download
  5. Upload PNG to YouTube
"""

import io, datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from brand import BRAND, FONTS, HEADSHOT_PATH

# ── Page ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Albert's List · Thumbnails",
    page_icon="🎬",
    layout="centered",
)

# ── Font loader ───────────────────────────────────────────────────────────────

def load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONTS[key], size)
    except OSError:
        return ImageFont.load_default()

# ── Text wrapping ─────────────────────────────────────────────────────────────

def wrap_text(draw, text, font, max_w):
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

# ── Face composite ────────────────────────────────────────────────────────────

def composite_face(img: Image.Image, headshot: Image.Image, text_max_w: int) -> Image.Image:
    """
    Composites headshot on the right side with a soft left-edge fade.
    Face zone: x=740 to x=1280, full height.
    """
    W, H     = img.size
    face_w   = W - text_max_w - 40
    face_h   = H
    face_x   = text_max_w + 40

    src_w, src_h = headshot.size
    scale    = max(face_w / src_w, face_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized  = headshot.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - face_w) // 2
    top  = (new_h - face_h) // 2
    cropped = resized.crop((left, top, left + face_w, top + face_h)).convert("RGBA")

    # Soft fade on left edge of face zone
    pixels = cropped.load()
    fade_px = 100
    for x in range(fade_px):
        alpha = int(255 * (x / fade_px))
        for y in range(face_h):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, min(a, alpha))

    base = img.convert("RGBA")
    base.paste(cropped, (face_x, 0), cropped)
    return base.convert("RGB")

# ── Thumbnail generator ───────────────────────────────────────────────────────

def generate_thumbnail(
    title:    str,
    hook_text: str,
    date_str:  str,
    headshot:  Image.Image | None,
) -> Image.Image:
    W, H = 1280, 720

    # Background gradient
    img  = Image.new("RGB", (W, H), BRAND["bg"])
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(int(10+t*12), int(14+t*8), int(26+t*28)))

    # Accent bars
    draw.rectangle([(0, 0), (14, H)],      fill=BRAND["accent"])
    draw.rectangle([(0, H - 10), (W, H)],  fill=BRAND["accent"])

    # Text zone width
    if headshot:
        text_max_w = 700   # text lives in left 700px; face fills the rest
        draw.rectangle([(740, 0), (W, H)], fill=BRAND["face_bg"])
        img = composite_face(img, headshot, text_max_w)
        draw = ImageDraw.Draw(img)
    else:
        text_max_w = W - 100
        draw.rectangle([(W - 280, 0), (W, 280)], fill=BRAND["dark_panel"])

    # Fonts
    title_size = 88 if len(title) < 32 else 72 if len(title) < 48 else 58
    f_title = load_font("bold",   title_size)
    f_hook  = load_font("medium", 28)
    f_brand = load_font("bold",   30)
    f_sub   = load_font("medium", 22)
    f_badge = load_font("bold",   20)

    # Brand label
    brand_w = draw.textlength("ALBERT'S LIST", font=f_brand)
    br_x    = min(text_max_w - brand_w - 10, W - brand_w - 36)
    draw.text((br_x, 28), "ALBERT'S LIST",          font=f_brand, fill=BRAND["accent"])
    draw.text((br_x, 64), "Job Search Intelligence", font=f_sub,   fill=BRAND["light_grey"])

    # Date badge
    bw = draw.textlength(date_str.upper(), font=f_badge)
    draw.rounded_rectangle([(34, 28), (bw + 58, 58)], radius=4, fill=BRAND["red_bar"])
    draw.text((46, 33), date_str.upper(), font=f_badge, fill=BRAND["white"])

    # Title
    margin = 46
    lines  = wrap_text(draw, title.upper(), f_title, text_max_w - margin)[:4]
    line_h = f_title.size + 12
    start_y = max((H - len(lines) * line_h) // 2 - 30, 100)

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        draw.text((margin + 4, y + 4), line, font=f_title, fill=(0, 0, 0))
        draw.text((margin, y),          line, font=f_title, fill=BRAND["white"])

    # Hook sub-line
    if hook_text:
        hook_y = start_y + len(lines) * line_h + 18
        for j, hl in enumerate(wrap_text(draw, hook_text, f_hook, text_max_w - margin)[:2]):
            draw.text((margin, hook_y + j * 36), hl, font=f_hook, fill=BRAND["light_grey"])

    return img

# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown("## 🎬 Albert's List · Thumbnail Generator")
st.caption("Paste from your 3 PM email. Generate a 1280×720 PNG in seconds.")
st.divider()

col1, col2 = st.columns([2, 1])
with col1:
    title = st.text_input(
        "Video title",
        placeholder="The Job Market Changed Overnight",
        help="Copy title A or B from your daily email",
    )
with col2:
    date_str = st.text_input(
        "Date badge",
        value=datetime.date.today().strftime("%b %d, %Y"),
    )

hook_text = st.text_input(
    "Thumbnail hook  (3–6 words from email)",
    placeholder="NOBODY IS TELLING YOU THIS",
    help="Copy the thumbnail_hook field from your daily email",
)

# ── Headshot ──────────────────────────────────────────────────────────────────

headshot_img = None

if HEADSHOT_PATH.exists():
    st.success(f"✓ Headshot loaded from `headshot.png` — no upload needed")
    headshot_img = Image.open(HEADSHOT_PATH)
else:
    st.info(
        "**One-time setup:** drop your photo as `headshot.png` in the repo folder "
        "and it auto-loads every session. Or upload below:"
    )
    uploaded = st.file_uploader("Upload headshot", type=["jpg", "jpeg", "png"])
    if uploaded:
        headshot_img = Image.open(uploaded)
        st.success("Photo loaded — drop it as headshot.png to skip this step next time")

# ── Generate ──────────────────────────────────────────────────────────────────

if st.button("Generate thumbnail", type="primary", disabled=not title.strip()):
    with st.spinner("Building..."):
        thumbnail = generate_thumbnail(
            title     = title.strip(),
            hook_text = hook_text.strip(),
            date_str  = date_str.strip(),
            headshot  = headshot_img,
        )

    st.image(thumbnail, caption="Preview — download below for full 1280×720", use_container_width=True)

    buf = io.BytesIO()
    thumbnail.save(buf, format="PNG", optimize=True)
    buf.seek(0)

    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:40]
    fname = f"thumbnail_{datetime.date.today()}_{safe}.png".replace(" ", "_")

    st.download_button(
        label     = "⬇ Download PNG  (1280×720)",
        data      = buf,
        file_name = fname,
        mime      = "image/png",
        type      = "primary",
    )

st.divider()
with st.expander("Setup & install"):
    st.code("pip install streamlit pillow", language="bash")
    st.code("streamlit run thumbnail_app.py", language="bash")
    st.markdown(
        "Drop your photo as **headshot.png** in the same folder — "
        "it loads automatically from then on. No re-upload needed."
    )
