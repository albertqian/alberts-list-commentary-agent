#!/usr/bin/env python3
"""
Albert's List — Daily Script Automation
Runs via GitHub Actions at 3 PM PT, Monday–Friday.
Pulls RSS feeds → Generates script via Claude → Emails to albert.qian@gmail.com
"""

import os, json, hashlib, datetime, io, smtplib, feedparser, anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from brand import BRAND, FONTS, HEADSHOT_PATH

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = [
    {"name": "LinkedIn Talent Blog",       "url": "https://www.linkedin.com/business/talent/blog/rss"},
    {"name": "CNN Business",               "url": "https://rss.cnn.com/rss/money_latest.rss"},
    {"name": "CNBC Economy",               "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"name": "BuiltIn",                    "url": "https://builtin.com/rss"},
    {"name": "Indeed Hiring Lab",          "url": "https://www.hiringlab.org/feed/"},
    {"name": "Bureau of Labor Statistics", "url": "https://www.bls.gov/feed/bls_latest.rss"},
    {"name": "The Kobeissi Letter",        "url": "https://thekobeissiletter.substack.com/feed"},
    {"name": "Challenger Gray Layoffs",    "url": "https://www.challengergray.com/feed/"},
    {"name": "AP Economy",                 "url": "https://feeds.apnews.com/rss/apf-economy"},
    {"name": "Fast Company Work Life",     "url": "https://www.fastcompany.com/work-life/rss"},
]

SENDER_EMAIL    = "solivagantlabs@gmail.com"
RECIPIENT_EMAIL = "albert.qian@gmail.com"

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SMTP_USER         = os.environ.get("SMTP_USER", SENDER_EMAIL)
SMTP_PASS         = os.environ["SMTP_PASS"]
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
DRY_RUN           = os.environ.get("DRY_RUN", "false").lower() == "true"

NEWS_WINDOW_HOURS     = 24
MAX_ARTICLES_PER_FEED = 4
MAX_TOTAL_ARTICLES    = 22
DEDUPE_LOG_PATH       = Path("dedupe_log.json")

# ══════════════════════════════════════════════════════════════════════════════
# ALBERT'S VOICE PROFILE
# ══════════════════════════════════════════════════════════════════════════════

ALBERT_VOICE = """
You are Albert Chen — founder of Albert's List, a job search, AI skills, and side hustle
community of 50,000+ members on Facebook. Bay Area born and raised. Product marketer and
content strategist by day, job search entrepreneur by night.

HOW YOU COMMUNICATE:
- Conversational, like a trusted advisor in the trenches with job seekers. No jargon.
- Validate difficulty before pivoting to strategy. Never minimize how hard this is.
- Anchor every argument in data: BLS numbers, layoff counts, unemployment vs. openings.
- FIT Model as a coaching lens: Favorite part → Improvement desired → Transition made.
- North star: "Most fail not because of lack of talent, but for a lack of cohesive positioning."
- Simon Sinek's Start With Why: WHY matters more than WHAT. Titles ≠ identity.
- The job search loop: networking → recruiter → hiring manager → peers → exec → day one.
- "Most resilient professional possible" is the mission for every viewer.
- 50,000-member community is a live data source: "What I'm hearing from my community..."
- Convert macro forces (AI displacement, DOGE cuts, tariffs, white-collar freeze) into tactics.
- Always close with action. The viewer leaves with something concrete to do TODAY.

AUDIENCE: White-collar professionals in tech, marketing, finance, ops — searching 3–18 months.
Overqualified, frustrated, applying to hundreds of roles. Need pattern recognition, not cheerleading.

PHRASES: "most resilient professional possible" / "Albert's List" / "cohesive positioning" /
"the job search loop" / "white collar" / "50,000 members" / "what I'm hearing from my community"
"""

# ══════════════════════════════════════════════════════════════════════════════
# YOUTUBE FRAMEWORK — Simson CHEAT + I.M.P.A.C.T. + Peralo
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_FRAMEWORK = """
SCOTT SIMSON'S CHEAT FRAMEWORK:
C — Copy Across Niches: find what's crushing in a different niche, adapt the title format
    and angle to job search where nobody's done it yet.
H — Hands-Off Recording: one video a week, simple setup, never moved.
E — Engineer Scripts with AI: voice dump → transcribe → script. This system does that.
A — Avoid the Editing Trap: raw performs in educational niches. Cut mistakes, nothing more.
T — Track Winners and Repeat (50/50 rule): 50% proven formats, 50% new angle tests.

PACKAGING FIRST: thumbnail + title decided before script. Content built around what stops scroll.

TITLE PRINCIPLES:
- Specificity beats generality: "April 2026 Tech Layoffs" > "Job Market Update"
- Numbers stop scroll: "3 Reasons" / "#1 Mistake" / "5 Signs"
- Speak to fear or frustration the viewer has right now
- Under 60 characters; keyword front-loaded
- A: contrarian / pattern-interrupt ("Everyone Is Wrong About [X]")
- B: specific outcome ("How to [Result] in [Timeframe]")
- Apply CHEAT C: adapt a title format crushing it in another niche

THUMBNAIL TEXT: 3–6 words MAX. Thumbnail + title create a curiosity gap together.

RETENTION BEAT EVERY 45 SECONDS: pattern interrupt, new data, direct question, visual shift.
Mark these [RETENTION BEAT] in the script.

SCRIPT STRUCTURE (8–10 min):
1. HOOK [0:00–0:30] — uncomfortable truth, specific data, NO "welcome back"
   Promise: "By the end of this, you'll know exactly what to do about [X]"
   [VISUAL CUE: bold hook graphic]
2. CREDIBILITY BRIDGE [0:30–1:00] — why you can speak to this today specifically
   [VISUAL CUE: Albert's List community stats]
3. CONTEXT [1:00–2:30] — name companies, name numbers, cite today's headlines
   [VISUAL CUE: news headline graphic]
4. THE INSIGHT [2:30–5:00] — [RETENTION BEAT ~3:00] — your unique take, apply frameworks
   [VISUAL CUE: framework diagram]
5. TACTICAL ADVICE [5:00–8:00] — [RETENTION BEAT ~6:00] — 3 numbered actionable steps
   Reference what 50k community is actually doing
   [VISUAL CUE: numbered list graphic]
6. COMMUNITY MIRROR [8:00–8:45] — real example from members, anonymized
   [VISUAL CUE: community quote card]
7. CTA [8:45–9:30] — join Albert's List, comment, tease next video
   [VISUAL CUE: subscribe prompt]

DESCRIPTION (Charles Peralo): first 2 lines compelling standalone · timestamps for all sections ·
keywords: job search 2026, layoffs, career advice · CTA: Albert's List [FACEBOOK LINK] · [LINKEDIN LINK]
"""

SOCIAL_GUIDELINES = """
SOCIAL CAPTIONS — platform-native, ready to paste into Sociosight after recording.
Replace [YOUTUBE LINK] with the published URL before posting.

FACEBOOK REELS: 2–3 sentences. Hook line first. End: "Full video on YouTube — link in comments 👇"
3–5 hashtags: #JobSearch #AlbertsList #CareerAdvice #Layoffs #JobMarket

INSTAGRAM REELS: Hook as first line (no "check out my new video"). 150 chars caption max.
8–15 hashtags including: #jobsearch #layoffs #careeradvice #jobmarket2026 #resumetips
End: "Full breakdown on YouTube 🎥 Link in bio"

TIKTOK: 100–150 chars max, lowercase energy, no period. Lead with tension.
4–6 hashtags: #jobsearch #layoffs #careeradvice #fyp #jobmarket
End: "YouTube link in bio" (no clickable link in TikTok captions)

TWITTER/X: 240 chars max. Open with contrarian statement or data point — no warm-up.
Include YouTube link directly. 2 hashtags max. OR provide a 3-tweet thread if content warrants.
"""

# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def load_dedupe_log() -> dict:
    if DEDUPE_LOG_PATH.exists():
        try:
            return json.loads(DEDUPE_LOG_PATH.read_text())
        except Exception:
            pass
    return {"covered_angles": [], "last_topics": [], "winner_formats": []}

def save_dedupe_log(log: dict):
    log["covered_angles"] = log["covered_angles"][-120:]
    log["last_topics"]    = log["last_topics"][-14:]
    log["winner_formats"] = log.get("winner_formats", [])[-20:]
    DEDUPE_LOG_PATH.write_text(json.dumps(log, indent=2))

def dedupe_context(log: dict) -> str:
    lines = []
    if recent := log.get("last_topics", [])[-7:]:
        lines.append("RECENT ANGLES — do not repeat these exact takes:")
        lines.extend(f"  - {t}" for t in recent)
    if winners := log.get("winner_formats", [])[-5:]:
        lines.append("\nPROVEN WINNER FORMATS — 50% of output should use these:")
        lines.extend(f"  - {w}" for w in winners)
    return "\n".join(lines) if lines else "No history — full creative latitude."

# ══════════════════════════════════════════════════════════════════════════════
# RSS INGESTION — 24-hour window with Monday fallback
# ══════════════════════════════════════════════════════════════════════════════

def fetch_articles() -> list[dict]:
    articles, seen = [], set()
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=NEWS_WINDOW_HOURS)).date()

    for feed_cfg in RSS_FEEDS:
        try:
            feed, count = feedparser.parse(feed_cfg["url"]), 0
            for entry in feed.entries:
                if count >= MAX_ARTICLES_PER_FEED:
                    break
                pub = None
                if getattr(entry, "published_parsed", None):
                    pub = datetime.date(*entry.published_parsed[:3])
                    if pub < cutoff:
                        continue
                title = entry.get("title", "").strip()
                if not title:
                    continue
                h = hashlib.md5(title.encode()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                articles.append({
                    "source":  feed_cfg["name"],
                    "title":   title,
                    "summary": entry.get("summary", "")[:600].strip(),
                    "date":    str(pub) if pub else "today",
                })
                count += 1
                if len(articles) >= MAX_TOTAL_ARTICLES:
                    break
        except Exception as e:
            print(f"[WARN] {feed_cfg['name']}: {e}")
        if len(articles) >= MAX_TOTAL_ARTICLES:
            break

    # Monday / thin-news fallback: widen to 72h
    if len(articles) < 5:
        print("[INFO] Thin news day — widening to 72h")
        fallback = (datetime.datetime.utcnow() - datetime.timedelta(hours=72)).date()
        for feed_cfg in RSS_FEEDS:
            try:
                for entry in feedparser.parse(feed_cfg["url"]).entries[:3]:
                    pub = None
                    if getattr(entry, "published_parsed", None):
                        pub = datetime.date(*entry.published_parsed[:3])
                        if pub < fallback:
                            continue
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    h = hashlib.md5(title.encode()).hexdigest()
                    if h in seen:
                        continue
                    seen.add(h)
                    articles.append({"source": feed_cfg["name"], "title": title,
                                     "summary": entry.get("summary", "")[:600].strip(),
                                     "date": str(pub) if pub else "recent"})
            except Exception:
                pass
            if len(articles) >= MAX_TOTAL_ARTICLES:
                break

    print(f"[INFO] {len(articles)} articles fetched")
    return articles

def articles_to_text(articles: list[dict]) -> str:
    return "\n".join(
        f"[{a['source']} · {a['date']}]\nHEADLINE: {a['title']}\n"
        + (f"DETAIL: {a['summary']}\n" if a["summary"] else "")
        for a in articles
    )

# ══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL — shared logic with thumbnail_app.py via brand.py
# ══════════════════════════════════════════════════════════════════════════════

def load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONTS[key], size)
    except OSError:
        return ImageFont.load_default()

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

def generate_thumbnail(title: str, hook_text: str, date_str: str) -> bytes:
    W, H = 1280, 720
    img  = Image.new("RGB", (W, H), BRAND["bg"])
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(int(10+t*12), int(14+t*8), int(26+t*28)))

    draw.rectangle([(0, 0), (14, H)],      fill=BRAND["accent"])
    draw.rectangle([(0, H-10), (W, H)],    fill=BRAND["accent"])
    draw.rectangle([(W-320, 0), (W, 320)], fill=BRAND["dark_panel"])

    f_brand = load_font("bold",   30)
    f_sub   = load_font("medium", 22)
    f_badge = load_font("bold",   20)
    f_title = load_font("bold",   90 if len(title) < 35 else 74 if len(title) < 50 else 60)
    f_hook  = load_font("medium", 28)

    bw = draw.textlength("ALBERT'S LIST", font=f_brand)
    draw.text((W - bw - 40, 28), "ALBERT'S LIST",         font=f_brand, fill=BRAND["accent"])
    draw.text((W - bw - 40, 64), "Job Search Intelligence", font=f_sub,   fill=BRAND["light_grey"])

    bw2 = draw.textlength(date_str.upper(), font=f_badge)
    draw.rounded_rectangle([(34, 28), (bw2+58, 58)], radius=4, fill=BRAND["red_bar"])
    draw.text((46, 33), date_str.upper(), font=f_badge, fill=BRAND["white"])

    margin, max_w = 46, W - 110
    lines   = wrap_text(draw, title.upper(), f_title, max_w)[:4]
    line_h  = f_title.size + 12
    start_y = max((H - len(lines) * line_h) // 2 - 30, 110)

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        draw.text((margin+4, y+4), line, font=f_title, fill=(0, 0, 0))
        draw.text((margin, y),     line, font=f_title, fill=BRAND["white"])

    if hook_text:
        hook_y = start_y + len(lines) * line_h + 18
        for j, hl in enumerate(wrap_text(draw, hook_text, f_hook, max_w)[:2]):
            draw.text((margin, hook_y + j*36), hl, font=f_hook, fill=BRAND["light_grey"])

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_script(articles: list[dict], dedupe_log: dict) -> dict:
    client    = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today_str = datetime.date.today().strftime("%B %d, %Y")

    prompt = f"""Today is {today_str}.

{ALBERT_VOICE}

{YOUTUBE_FRAMEWORK}

{SOCIAL_GUIDELINES}

{dedupe_context(dedupe_log)}

TODAY'S JOB MARKET NEWS (last 24h):
{articles_to_text(articles)}

Follow Simson's packaging-first rule: decide title + thumbnail concept FIRST, then build script.
Apply CHEAT C: adapt a title format from another niche.

Return ONLY valid JSON — no markdown, no preamble:
{{
  "title_a": "contrarian/pattern-interrupt, under 60 chars",
  "title_b": "how-to/specific outcome, under 60 chars",
  "cheat_note": "one sentence — which niche/format was adapted for the C",
  "thumbnail_hook": "3–6 words for thumbnail image, punchy",
  "description": "full YouTube description, first 2 lines standalone, timestamps, CTAs, [FACEBOOK LINK] and [LINKEDIN LINK] placeholders",
  "script": "full 8–10 min script, 7-part structure, Albert voice, [VISUAL CUE:] notes, [RETENTION BEAT] markers, \\n line breaks",
  "social": {{
    "facebook": "Facebook Reels caption",
    "instagram": "Instagram Reels caption with hashtags",
    "tiktok": "TikTok caption",
    "twitter": "single tweet or array of 3 thread tweets"
  }},
  "angle_summary": "one sentence for deduplication tracking"
}}"""

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
    return json.loads(raw)

# ══════════════════════════════════════════════════════════════════════════════
# EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def social_html(social: dict) -> str:
    platforms = [
        ("facebook",  "Facebook Reels", "#1877F2"),
        ("instagram", "Instagram Reels", "#C13584"),
        ("tiktok",    "TikTok",          "#010101"),
        ("twitter",   "Twitter / X",     "#1DA1F2"),
    ]
    rows = []
    for key, label, color in platforms:
        raw = social.get(key, "")
        body = "<br><br>".join(
            f'<span style="color:#888">Tweet {i+1}:</span> {t}'
            for i, t in enumerate(raw)
        ) if isinstance(raw, list) else raw.replace("\n", "<br>")
        rows.append(
            f'<tr><td style="padding:14px 0;border-bottom:1px solid #eef0f4;vertical-align:top">'
            f'<div style="display:inline-block;padding:3px 10px;border-radius:12px;background:{color};'
            f'color:#fff;font-size:11px;font-weight:700;margin-bottom:8px">{label}</div>'
            f'<div style="font-size:13px;line-height:1.75;color:#333">{body}</div></td></tr>'
        )
    return "".join(rows)

def build_html(result: dict, articles: list[dict], date_str: str) -> str:
    cheat = f'<div style="background:#f0fff4;border:1px solid #b7ebc8;border-radius:8px;padding:10px 14px;font-size:12px;color:#1a6b33;margin-top:10px">📋 CHEAT C: {result["cheat_note"]}</div>' if result.get("cheat_note") else ""
    sources = "".join(
        f'<tr><td style="padding:5px 0;font-size:13px;color:#555;border-bottom:1px solid #f4f4f4">'
        f'<b style="color:#1a1a2e">{a["source"]}</b> &nbsp;·&nbsp; {a["title"]}</td></tr>'
        for a in articles
    )
    return f"""<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#eef0f4}}
.w{{max-width:720px;margin:24px auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 6px 28px rgba(0,0,0,.12)}}
.h{{background:#0A0E1A;padding:30px 38px}}.h h1{{font-size:22px;font-weight:700;color:#fff}}.h p{{font-size:13px;color:#7a8aa8;margin-top:6px}}
.s{{padding:26px 38px;border-bottom:1px solid #eef0f4}}
.l{{font-size:10px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:#8899bb;margin-bottom:14px}}
.ta{{background:#fffbf0;border-left:4px solid #F5A623;padding:14px 18px;font-size:17px;font-weight:700;border-radius:0 8px 8px 0;margin-bottom:10px}}
.tb{{background:#f6f8ff;border-left:4px solid #4361ee;padding:14px 18px;font-size:17px;font-weight:700;border-radius:0 8px 8px 0}}
.sc{{background:#fafbfd;border:1px solid #e4e8f0;border-radius:10px;padding:26px;font-size:14px;line-height:1.95;color:#2d3142}}
.dc{{background:#f3f6ff;border-radius:10px;padding:20px;font-size:13px;line-height:1.85;color:#333}}
.tc{{text-align:center;padding:28px 38px;border-bottom:1px solid #eef0f4;background:#f8f9fc}}
.sn{{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:12px 16px;font-size:12px;color:#7a5c00;margin-bottom:14px}}
.ft{{padding:20px 38px;text-align:center;font-size:12px;color:#aab}}
table{{width:100%;border-collapse:collapse}}
</style></head><body><div class="w">
<div class="h"><h1>Albert's List &nbsp;·&nbsp; Daily Script</h1>
<p>{date_str} &nbsp;·&nbsp; 3 PM PT &nbsp;·&nbsp; {len(articles)} sources &nbsp;·&nbsp; 24h window</p></div>

<div class="tc"><div class="l">Thumbnail Preview &nbsp;·&nbsp; 1280×720</div>
<img src="cid:thumbnail" style="max-width:100%;border-radius:8px;border:1px solid #dde">
<p style="font-size:12px;color:#9aa;margin-top:10px">Text on image: <b style="color:#F5A623">"{result.get('thumbnail_hook','')}"</b></p></div>

<div class="s"><div class="l">YouTube Titles &nbsp;·&nbsp; A/B Test</div>
<div class="ta"><span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#F5A623;color:#fff">A</span> &nbsp;{result['title_a']}</div>
<div class="tb"><span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#4361ee;color:#fff">B</span> &nbsp;{result['title_b']}</div>
{cheat}</div>

<div class="s"><div class="l">YouTube Description</div>
<div class="dc">{result['description'].replace(chr(10),'<br>')}</div></div>

<div class="s"><div class="l">Script &nbsp;·&nbsp; 8–10 min</div>
<div class="sc">{result['script'].replace(chr(10),'<br>')}</div></div>

<div class="s"><div class="l">Social Captions &nbsp;·&nbsp; Ready for Sociosight</div>
<div class="sn">⚡ Record first, then paste these into Sociosight. Replace [YOUTUBE LINK] before posting.</div>
<table>{social_html(result.get('social', {}))}</table></div>

<div class="s"><div class="l">News Sources ({len(articles)} articles · last 24h)</div>
<table>{sources}</table></div>

<div class="ft">Albert's List Script Automation &nbsp;·&nbsp; GitHub Actions<br>
<span style="color:#ccd">Angle: {result.get('angle_summary','')}</span></div>
</div></body></html>"""

def send_email(result: dict, articles: list[dict], thumbnail_bytes: bytes):
    date_str   = datetime.date.today().strftime("%B %d, %Y")
    short_date = datetime.date.today().strftime("%b %d")
    subject    = f"[Albert's List] {short_date} · {result['title_a'][:52]}"

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(build_html(result, articles, date_str), "html"))

    img_part = MIMEImage(thumbnail_bytes, _subtype="png")
    img_part.add_header("Content-ID", "<thumbnail>")
    img_part.add_header("Content-Disposition", "inline",
                        filename=f"thumbnail_{datetime.date.today()}.png")
    msg.attach(img_part)

    if DRY_RUN:
        print("[DRY RUN] Subject:", subject)
        print("[DRY RUN] Title A:", result["title_a"])
        print("[DRY RUN] Thumbnail hook:", result.get("thumbnail_hook"))
        print("[DRY RUN] Script preview:\n", result["script"][:400])
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.starttls()
        srv.login(SMTP_USER, SMTP_PASS)
        srv.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"[INFO] Delivered → {RECIPIENT_EMAIL}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"[INFO] Albert's List Automation — {datetime.date.today()}")
    dedupe_log = load_dedupe_log()
    articles   = fetch_articles()

    print("[INFO] Generating script via Anthropic API...")
    result = generate_script(articles, dedupe_log)
    print(f"[INFO] Done — Title A: {result['title_a']}")

    if angle := result.get("angle_summary", ""):
        dedupe_log["last_topics"].append(angle)
        dedupe_log["covered_angles"].append({
            "date": str(datetime.date.today()), "angle": angle, "title": result["title_a"]
        })
    save_dedupe_log(dedupe_log)

    print("[INFO] Generating thumbnail...")
    thumbnail = generate_thumbnail(
        title     = result["title_a"],
        hook_text = result.get("thumbnail_hook", ""),
        date_str  = datetime.date.today().strftime("%b %d, %Y"),
    )

    send_email(result, articles, thumbnail)
    print("[INFO] Done.")

if __name__ == "__main__":
    main()
