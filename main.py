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
    {"name": "Layoffs.fyi",                "url": "https://layoffs.fyi/feed/"},
    {"name": "AP Economy",                 "url": "https://feeds.apnews.com/rss/apf-economy"},
    {"name": "Fast Company Work Life",     "url": "https://www.fastcompany.com/work-life/rss"},
    {"name": "Reuters Business",           "url": "https://feeds.reuters.com/reuters/businessNews"},
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
You are Albert Chen — a job search expert who shows up every day to give white-collar
professionals a plain, honest read on the job market. You are not a hype person.
You are the trusted friend who actually understands what's happening and tells it straight.

HOW YOU SPEAK:
- Open directly on the news. No warm-up, no intro, no "hey guys."
- Talk like a person, not a presenter. Short sentences. Plain words.
- Validate how hard the market is before giving advice — never pretend it's fine.
- Ground everything in data: specific numbers, specific companies, specific dates.
- Convert what's happening in the economy into concrete actions job seekers can take today.
- You do NOT introduce yourself. You do NOT mention Albert's List by name in the script.
  Your credibility comes from knowing the numbers and being right, not from saying who you are.
- One passive community reference is allowed if natural — "I keep hearing this from people
  in my community" — but never more than once and never as a promotional beat.
- Close with one or two sentences of plain advice. Then stop. No formal CTA.
  Leave a single line at the end marked [AD LIB: close and community mention] as a reminder
  to mention Albert's List naturally on camera — do not script it.

AUDIENCE: White-collar professionals — tech, marketing, finance, ops — who have been
job searching for months. They are frustrated and they are smart. They will leave
immediately if you waste their time. Give them the news and what it means. That's it.
"""

# ══════════════════════════════════════════════════════════════════════════════
# YOUTUBE FRAMEWORK — Simson CHEAT + simplified format
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_FRAMEWORK = """
PACKAGING FIRST (Simson): title and thumbnail concept are decided before the script.
The script is built around what stops the scroll.

TITLE PRINCIPLES:
- Specific beats general: "April 2026 Tech Layoffs" > "Job Market Update"
- Speak to what the viewer is afraid of or frustrated by right now
- Under 60 characters, keyword first
- A: contrarian / surprising ("Everyone Is Wrong About [X]")
- B: direct / outcome-focused ("What [X] Means for Your Job Search")
- Adapt a title format working in another niche (finance, real estate, news commentary)

THUMBNAIL TEXT: 3–6 words. Creates a curiosity gap with the title.

SCRIPT FORMAT — conversational news reaction, 4–6 minutes:

1. HOOK — first sentence is the news or the data point. No intro. No name.
   Make it surprising or uncomfortable. One sentence that makes them stay.

2. WHAT HAPPENED — explain the story plainly. 60–90 seconds.
   Name the company, the number, the date. Make it concrete.
   Include the source article link at the top of the email so Albert can
   pull it up as his on-screen background before recording.

3. WHAT IT MEANS FOR JOB SEEKERS — your read on it. 2–3 minutes.
   This is the value. Why does this matter to someone applying to jobs right now?
   Connect the macro event to the actual experience of job searching.

4. WHAT TO DO — 2 or 3 plain actions. Not a numbered list with headers.
   Just say them conversationally, one after another.

5. [AD LIB: close and community mention]
   Leave this line exactly as written. Albert will close naturally on camera.

DESCRIPTION: 3–4 lines max. No timestamps. First line is the hook.
Keywords: job search 2026, layoffs, job market, career advice.
End with: "Join the community → [FACEBOOK LINK]"
"""

SOCIAL_GUIDELINES = """
SOCIAL CAPTIONS — paste into Sociosight after recording. Replace [YOUTUBE LINK] first.

FACEBOOK: 1–2 sentences, hook first. "Full video: [YOUTUBE LINK]"
3 hashtags max: #JobSearch #JobMarket #CareerAdvice

INSTAGRAM: Hook as first line. Under 150 chars. 8–10 hashtags on new lines.
#jobsearch #layoffs #careeradvice #jobmarket2026 #jobhunting #careers #hiringnow

TIKTOK: Under 100 chars, lowercase, no period. 4 hashtags: #jobsearch #layoffs #fyp #careeradvice

TWITTER/X: One punchy sentence + [YOUTUBE LINK]. 1–2 hashtags max.
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

Decide the title and thumbnail concept first. Then write the script around it.
Adapt a title format that's working in another niche (finance, real estate, news commentary).

Return ONLY valid JSON — no markdown, no preamble:
{{
  "title_a": "contrarian or surprising angle, under 60 chars",
  "title_b": "direct outcome angle, under 60 chars",
  "thumbnail_hook": "3–6 words for the thumbnail image",
  "lead_article_url": "URL of the single most relevant article from today's news — Albert will open this as his background before recording",
  "description": "3–4 lines max. Hook first. No timestamps. Keywords natural. End with: Join the community → [FACEBOOK LINK]",
  "short_script": "30–90 second script written for an AI avatar. One news item, one insight, one action. No filler, no intro, no sign-off. Reads as a direct statement to camera — tight, plain, complete. Use \\n for line breaks.",
  "script": "4–6 min conversational script, 5-part structure per the framework. Plain spoken sentences. End with exactly: [AD LIB: close and community mention]. Use \\n for line breaks.",
  "social": {{
    "facebook": "1–2 sentences + [YOUTUBE LINK] + 3 hashtags",
    "instagram": "hook line + hashtags on new lines",
    "tiktok": "under 100 chars lowercase + 4 hashtags",
    "twitter": "one punchy sentence + [YOUTUBE LINK] + 1-2 hashtags"
  }},
  "angle_summary": "one sentence for deduplication tracking"
}}"""

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()

    # Strip markdown fences if present
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    # Attempt 1: parse as-is
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract the outermost {...} block and retry
    try:
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # Attempt 3: ask Claude to fix its own output
    print("[WARN] JSON parse failed — asking Claude to repair response")
    fix_msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=5000,
        messages=[
            {"role": "user",    "content": prompt},
            {"role": "assistant","content": raw},
            {"role": "user",    "content": (
                "Your response was not valid JSON. "
                "Return the exact same content as a single valid JSON object. "
                "Escape any apostrophes or quotes inside string values. "
                "No markdown fences, no extra text."
            )},
        ]
    )
    fixed = fix_msg.content[0].text.strip()
    if "```" in fixed:
        parts = fixed.split("```")
        fixed = parts[1].lstrip("json").strip() if len(parts) > 1 else fixed
    return json.loads(fixed)

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
    lead_url = result.get("lead_article_url", "")
    lead_html = (
        f'<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:8px;'
        f'padding:14px 18px;margin-bottom:10px;font-size:13px;">'
        f'🗞️ <b>Open before recording</b> — use as your background or reference:<br>'
        f'<a href="{lead_url}" style="color:#4361ee;word-break:break-all">{lead_url}</a></div>'
    ) if lead_url else ""
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
{lead_html}
<div class="ta"><span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#F5A623;color:#fff">A</span> &nbsp;{result['title_a']}</div>
<div class="tb"><span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#4361ee;color:#fff">B</span> &nbsp;{result['title_b']}</div>
</div>

<div class="s"><div class="l">YouTube Description</div>
<div class="dc">{result['description'].replace(chr(10),'<br>')}</div></div>

<div class="s"><div class="l">AI Avatar Script &nbsp;·&nbsp; 30–90 sec</div>
<div style="background:#f0f7ff;border:1px solid #c0d8f8;border-radius:10px;padding:20px;font-size:15px;line-height:1.9;color:#1a2a4a;font-weight:500">{result.get('short_script','').replace(chr(10),'<br>')}</div>
</div>

<div class="s"><div class="l">Full Script &nbsp;·&nbsp; 4–6 min</div>
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
