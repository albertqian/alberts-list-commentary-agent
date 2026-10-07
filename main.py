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

NEWS_WINDOW_HOURS     = 72   # 3-day window — analysis beats instant reaction
MAX_ARTICLES_PER_FEED = 4
MAX_TOTAL_ARTICLES    = 22
DEDUPE_LOG_PATH       = Path("dedupe_log.json")

# ══════════════════════════════════════════════════════════════════════════════
# ALBERT'S VOICE PROFILE
# ══════════════════════════════════════════════════════════════════════════════

ALBERT_VOICE = """
You are Albert Chen — a job search expert who gives white-collar professionals a clear,
honest read on what is actually happening in the job market. You are not a breaking news
channel. You are the person who waits for the dust to settle and then tells people what
it actually means for their search.

Your positioning: analysis over reaction. By the time you cover something, the hot takes
are already done. You are the one who explains what the story actually means now that
we know how it played out. That is more valuable to a job seeker than a same-day reaction.

HOW YOU SPEAK:
- Open on the insight, not the event. Lead with what it means, not what happened.
  Wrong: "Google just announced layoffs." Right: "Google's latest cut tells you
  something specific about which roles are actually safe right now."
- Talk like a person, not a presenter. Short sentences. Plain words.
- Validate how hard the market is before giving advice — never pretend it's fine.
- Ground everything in data: specific numbers, specific companies, specific dates.
- The extra time means you can add one layer of context the instant takes missed —
  a follow-up number, a pattern across multiple companies, a contrarian angle.
  Use it. That is what makes this worth watching over the person who covered it first.
- You do NOT introduce yourself. You do NOT mention Albert's List by name in the script.
  Your credibility comes from knowing the numbers and being right, not from saying who you are.
- One passive community reference is allowed if natural — "I keep hearing this from people
  in my community" — but never more than once and never as a promotional beat.
- End every script with the sign-off written out in full on its own line, preceded by [SIGN-OFF]:
  [SIGN-OFF]
  That's your job market update. Follow Albert's List for analysis that actually helps
  your search, and if you want to go deeper — join us at our next live event. Link in
  the description.

AUDIENCE: White-collar professionals — tech, marketing, finance, ops — who have been
job searching for months. They are frustrated and they are smart. They have already seen
the hot take. Give them the real read.
"""

# ══════════════════════════════════════════════════════════════════════════════
# YOUTUBE FRAMEWORK — Simson CHEAT + simplified format
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_FRAMEWORK = """
THIS SYSTEM IS SHORTS-FIRST. Every output is built around a 40–70 second video.
The thinking script (15–30s) is the secondary deliverable. There is no long-form script.

═══ SIMSON'S PACKAGING RULE ════════════════════════════════════════════════════
Title and thumbnail are decided BEFORE the script. The short is built around what
stops the scroll, not the other way around. If the title isn't strong enough to
make someone pause mid-scroll, the content is irrelevant.

═══ TITLE PRINCIPLES — from Albert's actual performance data ════════════════════
HARD RULE: Every title must contain a named company, named figure, OR specific
dollar/headcount figure. This is not optional. Titles without these consistently
underperform. Bottom performers have zero named entities. Top performers always have one.

Duration target: 40–70 seconds. Under 40s signals low value to the algorithm.
Over 80s loses the audience before the point lands.

Proven title formulas — use in order of performance:
  1. "The $[Amount] [Thing] Nobody's Talking About"
  2. "Why [Company]'s [Thing] Won't Help Your Job Search"
  3. "[Group] Are Quietly [Doing X] (Not Just [Expected Group])"
  4. "[Company] Is [Action]-ing [N] [People] (Here's the Catch)"
  5. "[Person]'s [Advice] Is Wrong for Job Seekers"
  6. "[X] Down [%] But You Can't Get Hired (Here's Why)"
  7. "[Company] Just [Action]-ed. What It Means for Your Job Search"

Title A: use one of the formulas above, matched to today's lead story
Title B: "What [Named Entity] Means for Job Seekers" — direct, no formula required
Under 60 characters. Keyword first. Written to be read WITHOUT a description below it
— Shorts viewers rarely read descriptions.

═══ THUMBNAIL TEXT ══════════════════════════════════════════════════════════════
3–6 words. Works as a standalone statement even without the title.
Creates a curiosity gap — the thumbnail raises a question the title answers,
or vice versa. Never redundant with the title.

═══ SIMSON'S SHORTS HOOK RULE ══════════════════════════════════════════════════
First sentence is the entire game. On Shorts, there is no patience — the viewer
decides in under 2 seconds. The first sentence must be:
- A specific insight that reframes a story everyone already heard ("Everyone said
  Google's layoffs were about cost. The numbers say something different.")
- A direct contradiction ("The job market added 175,000 jobs last month. You still
  can't get hired. Here's why that makes sense.")
- A pattern across events that nobody connected yet ("Three companies cut the same
  role in the last two weeks. Here's what that tells you.")
- A contrarian take on a story that had a consensus reaction ("Everyone treated
  Microsoft's hiring pause as bad news. For mid-career candidates it's actually
  the opposite.")
Never start with context. Never start with "so" or "today" as a warm-up.
The insight IS the opening. You are not breaking news — you are explaining it.

═══ SHORTS SCRIPT STRUCTURE (40–70 seconds) ════════════════════════════════════
1. HOOK [0:00–0:08] — one sentence. Lead with the insight, not the event.
   What does this story actually mean, now that the dust has settled?
2. WHAT ACTUALLY HAPPENED [0:08–0:25] — 2–3 sentences. Named entity, number, date.
   Include one detail or follow-up data point the instant takes missed.
3. WHAT IT MEANS FOR YOUR SEARCH [0:25–0:50] — 2–3 sentences. Direct implication.
   One clear, actionable takeaway the viewer can use this week.
4. [SIGN-OFF] — scripted, read directly.

═══ THINKING SCRIPT STRUCTURE (15–30 seconds) ══════════════════════════════════
Mid-thought open. Reads like Albert caught something and is working through it.
Starters: "So I'm looking at this..." / "Wait — this number doesn't add up..." /
"Okay, this is interesting..." / "Something nobody's mentioning about this..."
One observation. One implication. No sign-off. Stops cleanly on the insight.
Written to feel unscripted even though every word is chosen.

DESCRIPTION: 4–6 lines. Written for someone who watched the short and wants more context.
Line 1 = the hook sentence from the script — the specific fact or contradiction that opened the video.
Line 2 = 1–2 sentences expanding on what the video covered. Name the company, figure, or number.
Line 3 = one concrete action the viewer can take today based on what was in the video.
Line 4 = blank line for breathing room.
Line 5 = "Join the community → https://www.facebook.com/groups/125930820922472/"
No timestamps. No keyword stuffing. Write it for a person, not an algorithm.
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

    # Thin-news fallback: widen to 5 days
    if len(articles) < 5:
        print("[INFO] Thin news day — widening to 120h")
        fallback = (datetime.datetime.utcnow() - datetime.timedelta(hours=120)).date()
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

    # Score and sort — highest relevance first
    for a in articles:
        a["score"] = score_article(a)
    articles.sort(key=lambda x: x["score"], reverse=True)

    for a in articles[:3]:
        print(f"[INFO] Score {a['score']:>3}  {a['source']}: {a['title'][:70]}")

    return articles

def score_article(article: dict) -> int:
    """
    Score each article by how likely it is to produce a high-view short.
    Based on analysis of Albert's top-performing videos:
    - Named companies and specific figures drive views
    - Dollar amounts and headcounts drive views
    - Abstract macro without a named entity kills performance
    """
    text  = (article["title"] + " " + article["summary"]).lower()
    score = 0

    # Named companies — strongest signal from data
    companies = [
        "google","microsoft","apple","amazon","meta","nvidia","salesforce",
        "spacex","cisco","oracle","tesla","openai","anthropic","ibm","intel",
        "boeing","walmart","jpmorgan","goldman","blackrock","uber","airbnb",
        "linkedin","indeed","stripe","palantir","snowflake","cloudflare",
        "workday","servicenow","zoom","slack","twitter","x.com","bytedance",
        "tiktok","spotify","netflix","disney","ford","gm","ups","fedex",
    ]
    named_cos = [c for c in companies if c in text]
    score += len(named_cos) * 3

    # Named figures — Jensen Huang, Trump, Powell, etc. drive views
    figures = ["trump","powell","jensen","musk","bezos","pichai","nadella",
               "altman","zuckerberg","yellen","fed chair","ceo","cfo"]
    score += sum(2 for f in figures if f in text)

    # Specific dollar amounts or headcounts — "$110B", "1,000 jobs", "50%"
    import re
    if re.search(r'\$[\d,\.]+[bmk]?', text):           score += 2
    if re.search(r'[\d,]+ (jobs|workers|employees|people|grads|cuts)', text): score += 2
    if re.search(r'\d+%', text):                        score += 1

    # High-signal topic categories based on winning videos
    if any(w in text for w in ["layoff","laid off","cut","fired","job cut"]): score += 2
    if any(w in text for w in ["hiring","hired","jobs added","openings"]):    score += 2
    if any(w in text for w in ["ai","artificial intelligence"]) and \
       any(w in text for w in ["job","hire","work","employ","replace"]):      score += 2
    if any(w in text for w in ["salary","wage","pay","compensation","earn"]): score += 2
    if any(w in text for w in ["merger","acquisition","ipo","deal","billion"]): score += 2

    # Contrarian or paradox angle — "but", "won't", "actually", "nobody"
    if any(w in text for w in ["but","won't","actually","nobody","quiet","catch",
                                 "wrong","trap","fail","broken","paradox"]):  score += 1

    # Demographic specificity — Men/Women video was #3
    if any(w in text for w in ["men","women","gen z","millennial","boomer",
                                 "young","graduate","entry"]):                score += 1

    # Penalize abstract macro with no named entity
    if not named_cos and any(w in text for w in
        ["uncertainty","concern","worry","fear","sentiment","outlook",
         "fed rate","interest rate","inflation","gdp","cpi"]):               score -= 2

    # Penalize generic job search advice (no news hook)
    if any(w in text for w in ["how to","tips","secrets","guide","steps"]):  score -= 1

    # Hard penalize mock interview content — wrong format for shorts strategy
    if any(w in text for w in ["mock interview","interview practice","interview feedback",
                                "interview question","interview prep"]):      score -= 5

    return score

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
  "title_a": "one of the 7 proven formulas, named entity required, under 60 chars",
  "title_b": "What [Named Entity] Means for Job Seekers — direct, under 60 chars",
  "thumbnail_hook": "3–6 words, standalone statement, curiosity gap with title",
  "lead_article_url": "URL of the highest-scoring article — Albert opens this as background before recording",
  "description": "4-6 lines: hook sentence on line 1, 1-2 sentences expanding on what was covered (named entity + number) on line 2, one concrete action the viewer can take today on line 3, blank line, then 'Join the community → https://www.facebook.com/groups/125930820922472/' as the final line",
  "short_script": "PRIMARY DELIVERABLE. 40–70 seconds. Hook sentence first — specific fact or direct contradiction, no warm-up. What happened (named entity + number). What it means for job seekers. One action. [SIGN-OFF] That's your job market update for today. Follow Albert's List for daily news, and if you want to go deeper — join us at our next live event. Link in the description. Use \\n for line breaks.",
  "thinking_script": "SECONDARY DELIVERABLE. 15–30 seconds. Mid-thought open. One observation working through to one implication. No sign-off. Stops on the insight. Use \\n for line breaks.",
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
<p>{date_str} &nbsp;·&nbsp; 3 PM PT &nbsp;·&nbsp; {len(articles)} sources &nbsp;·&nbsp; 72h window</p></div>

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

<div class="s"><div class="l">Short Script &nbsp;·&nbsp; PRIMARY &nbsp;·&nbsp; 40–70 sec</div>
<div style="background:#f0f7ff;border:1px solid #c0d8f8;border-radius:10px;padding:20px;font-size:15px;line-height:1.9;color:#1a2a4a;font-weight:500">{result.get('short_script','').replace(chr(10),'<br>')}</div>
</div>

<div class="s"><div class="l">Thinking Script &nbsp;·&nbsp; SECONDARY &nbsp;·&nbsp; 15–30 sec</div>
<div style="background:#f5f0ff;border:1px solid #d4b8f8;border-radius:10px;padding:20px;font-size:15px;line-height:1.9;color:#2a1a4a;font-weight:500;font-style:italic">{result.get('thinking_script','').replace(chr(10),'<br>')}</div>
</div>

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
        print("[DRY RUN] Short script preview:\n", result.get("short_script","")[:400])
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
