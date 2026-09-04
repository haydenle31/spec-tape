#!/usr/bin/env python3
"""
Spec Tape — daily speculative-stock newsletter generator.

Runs on GitHub Actions (see .github/workflows/spec-tape.yml), writes a static
newsletter to docs/index.html + docs/archive/<date>.html, and (optionally)
emails it. Data: yfinance (free, no key). Optional editorial lede: Mistral.

Edit WATCHLIST / DESK_NOTES below to change coverage. Nothing else required.
"""

import os, glob, socket, html, datetime, smtplib, json
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

socket.setdefaulttimeout(20)  # never hang a CI run on a slow endpoint

# ----------------------------------------------------------------------------
# CONFIG — edit freely
# ----------------------------------------------------------------------------
HST = ZoneInfo("Pacific/Honolulu")

NAMES = {
    "AAPL":"Apple","MSFT":"Microsoft","GOOGL":"Alphabet","AMZN":"Amazon",
    "META":"Meta","NVDA":"Nvidia","TSLA":"Tesla","SPCX":"SpaceX",
    "RKLB":"Rocket Lab \u00b7 space","OKLO":"Oklo \u00b7 nuclear SMR","IONQ":"IonQ \u00b7 quantum",
    "SOFI":"SoFi \u00b7 fintech","RBLX":"Roblox \u00b7 gaming","F":"Ford \u00b7 autos",
}

# static catalyst hints (kept fresh by you; shown as "▸ ...")
CATALYST = {
    "SPCX":"lockup ~Dec 8","NVDA":"AI capex",
    "RKLB":"Neutron debut","OKLO":"NRC / PPA news","IONQ":"2026 'quantum advantage'",
    "SOFI":"earnings + rate path","RBLX":"earnings ~Oct 28","F":"ex-div + monthly sales",
}
FLAGS = {"NVDA":"semi","Anthropic":"my maker"}

# fallback one-liners if Yahoo news is empty (so the page always reads well)
SEED_NEWS = {
    "NVDA":"Accelerator leader; watch data-center demand",
    "MSFT":"Copilot / Azure AI monetization in focus",
    "GOOGL":"Gemini + cloud; AI-search defense in focus",
    "AMZN":"AWS capex vs. ROI debate",
    "META":"Heavy AI spend; struck OKLO nuclear power deal",
    "AAPL":"Lagging the AI trade on the on-device story",
    "TSLA":"Robotaxi / Musk-complex sentiment",
    "SPCX":"IPO'd Jun 12; bought Cursor $60B; ~$2.8T cap",
    "RKLB":"Launch + spacecraft ramp; uncorrelated to semis",
    "OKLO":"AI-nuclear proxy; Meta power deal re-rated it",
    "IONQ":"Rev +755% YoY; ~$3B cash; binary on hardware proof",
    "SOFI":"Sub-$25, weekly options; IV rank often 50\u201375",
    "RBLX":"-42% YTD; IV propped by EU VLOP + class actions",
    "F":"~$1,100/contract; liquid chain; pays a dividend",
}

WATCHLIST = [
    {"head":"The Fab 10",
     "note":"Vanda's \u201cFrontier AI & Big Tech 10\u201d \u2014 Mag 7 + SpaceX + OpenAI + Anthropic. Only 8 trade.",
     "tickers":["NVDA","MSFT","GOOGL","AMZN","META","AAPL","TSLA","SPCX"],
     "private":[("OpenAI","Private \u2014 confidential IPO filed Jun 8, 2026; leaning 2027"),
                ("Anthropic","Private \u2014 confidential IPO filed Jun 1, 2026")]},
    {"head":"Speculative \u2014 growth",
     "note":"Three higher-beta growth stories \u2014 space, nuclear, quantum. Flyers, not wheels. Size 1\u20133%, staged.",
     "tickers":["RKLB","OKLO","IONQ"], "private":[]},
    {"head":"Wheel candidates",
     "note":"Liquid options, IV worth selling, capital-efficient, and a business you'd hold if assigned. None are semis.",
     "tickers":["SOFI","RBLX","F"], "private":[]},
]

DESK_NOTES = [
    ("SOFI is your cleanest wheel.",
     "Sub-$25, so ~$2,000\u2013$2,500 secures a contract; deep weekly chain; IV rank often 50\u201375 in vol periods. "
     "Capital-efficient premium with no semi exposure \u2014 the anchor of the three."),
    ("RBLX pays the fattest premium of the three \u2014 for a reason.",
     "The EU-VLOP designation + securities class actions keep IV elevated; that's the premium you're paid. "
     "Only sell cash-secured puts at strikes you'd be happy to own, ideally near/below the $34 52-wk low."),
    ("F is the low-beta ballast.",
     "~$1,100 per contract, liquid chain, pays a dividend while you hold. Thin premium, but it steadies a book "
     "that's otherwise high-beta tech. Skip new puts within ~2 weeks of earnings."),
    ("The growth trio (RKLB / OKLO / IONQ) are flyers, not wheels.",
     "Thinner options, binary catalysts, big drawdowns. Buy small (1\u20133%), stage entries, and don't wheel them "
     "just because the IV looks juicy \u2014 that's how you get assigned into a falling knife."),
    ("Buying the Fab 10 wholesale deepens your concentration.",
     "It's NVDA-heavy mega-cap tech. The only legs that don't overlap your book are SPCX and the pending "
     "OpenAI/Anthropic IPOs \u2014 and SpaceX post-lockup discipline applies to all three."),
]

# ----------------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------------
def _yf():
    import yfinance as yf
    return yf

def quote(tkr):
    """Return (price_str, chg_str, chg_float) or (None, None, None)."""
    try:
        fi = _yf().Ticker(tkr).fast_info
        last = fi.get("last_price") or fi.get("lastPrice")
        prev = fi.get("previous_close") or fi.get("previousClose")
        if last and prev:
            chg = (last - prev) / prev * 100.0
            return f"${last:,.2f}", f"{chg:+.1f}%", chg
    except Exception as e:
        print(f"  quote fail {tkr}: {e}")
    return None, None, None

def headline(tkr):
    """Best-effort latest headline via yfinance; falls back to SEED_NEWS."""
    try:
        items = _yf().Ticker(tkr).news or []
        for it in items:
            # yfinance schema varies by version
            title = it.get("title") or (it.get("content") or {}).get("title")
            if title:
                return title.strip()[:120]
    except Exception as e:
        print(f"  news fail {tkr}: {e}")
    return SEED_NEWS.get(tkr, "")

def market_context():
    vix_s, tone = "~15", "mixed"
    try:
        v = _yf().Ticker("^VIX").fast_info.get("last_price")
        if v: vix_s = f"~{v:.0f}"
        spy_p, spy_c, spy_chg = quote("SPY")
        if spy_chg is not None and v:
            if spy_chg < -0.75 or v > 22: tone = "risk-off"
            elif spy_chg > 0.5 and v < 16: tone = "risk-on"
    except Exception as e:
        print(f"  context fail: {e}")
    return vix_s, tone

def build_lede(rows, tone, vix):
    """One-line editorial lede. Uses Mistral if MISTRAL_API_KEY set; else deterministic."""
    movers = [r for r in rows if r["chg_f"] is not None]
    top = max(movers, key=lambda r: abs(r["chg_f"]), default=None)
    key = os.environ.get("MISTRAL_API_KEY")
    if key:
        try:
            import requests
            facts = "; ".join(f"{r['t']} {r['chg']}" for r in movers[:8]) or "quiet tape"
            r = requests.post("https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": os.environ.get("MISTRAL_MODEL","mistral-small-latest"),
                      "max_tokens": 90, "temperature": 0.4,
                      "messages":[{"role":"user","content":
                        f"Tone {tone}, VIX {vix}. Moves: {facts}. Write ONE <=35-word market note for a "
                        f"speculative-growth options trader. Lead with the biggest move. No preamble."}]},
                timeout=25)
            txt = r.json()["choices"][0]["message"]["content"].strip()
            if txt: return txt
        except Exception as e:
            print(f"  mistral fail: {e}")
    if top:
        return (f"Tone {tone}, VIX {vix}. Biggest move on the list: {top['t']} {top['chg']}. "
                f"The beta \u2014 and the drawdowns \u2014 live in the speculative names below.")
    return ("SpaceX's June listing rewired the mega-cap trade into the \u201cFab 10.\u201d "
            "The beta lives in the speculative AI, quantum, and nuclear names below.")

# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
def esc(s): return html.escape(str(s), quote=False)

def item_html(r):
    q = (f'<span class="quote"><span class="pr">{esc(r["price"])}</span>'
         f'{f" <span class=\"{ 'down' if r['chg_f'] and r['chg_f']<0 else 'up' }\">{esc(r['chg'])}</span>" if r["chg"] else ""}</span>') \
        if r["price"] else ('<span class="quote">private</span>' if r.get("priv") else '<span class="quote">\u2014</span>')
    flag = f'<span class="flag">{esc(r["flag"])}</span>' if r.get("flag") else ""
    cat = f'<span class="cat">\u25b8 {esc(r["cat"])}.</span> ' if r.get("cat") else ""
    priv = " private" if r.get("priv") else ""
    return (f'<div class="item{priv}"><div class="line1">'
            f'<span class="tk">{esc(r["t"])}</span> {flag} <span class="nm">{esc(r["name"])}</span>{q}</div>'
            f'<div class="news">{cat}{esc(r["news"])}</div></div>')

CSS = """
:root{--ink:#171A1F;--muted:#5C6470;--faint:#8A8F98;--paper:#F1F2EE;--surface:#FBFBF9;
--line:#DEE0D9;--up:#137A4F;--down:#BF3B2E;--catalyst:#B4791F;--rail:#171A1F}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;
font-size:15.5px;line-height:1.58;-webkit-font-smoothing:antialiased}
.rail{height:5px;background:var(--rail)}.wrap{max-width:720px;margin:0 auto;padding:0 22px 72px}
.util{display:flex;align-items:center;gap:10px;padding:12px 0 0;font-size:13px;color:var(--muted)}
.util a{font-family:"IBM Plex Mono",monospace;font-size:13px;color:var(--ink);text-decoration:none;
border:1px solid var(--line);border-radius:5px;padding:3px 9px;background:var(--surface)}
.util a:hover{border-color:var(--ink)}.util .sp{margin-left:auto}
.mast{padding:14px 0 14px;border-bottom:2px solid var(--ink);margin-bottom:6px}
.mast h1{font-family:"Space Grotesk",sans-serif;font-weight:700;font-size:44px;letter-spacing:-.02em;margin:0;line-height:.95}
.tagline{font-size:14px;color:var(--muted);margin:8px 0 0}
.dateline{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--muted);margin-top:12px}
.dateline .b{color:var(--ink)}
.tone-risk-on{color:var(--up)}.tone-risk-off{color:var(--down)}.tone-mixed{color:var(--catalyst)}
.lede{font-size:17px;line-height:1.55;margin:18px 0 6px}.lede .lbl{color:var(--catalyst);font-weight:600}
.sec{padding:20px 0 4px;border-top:1px solid var(--line);margin-top:16px}.sec:first-of-type{border-top:none}
.sh{font-family:"Space Grotesk",sans-serif;font-weight:600;font-size:19px;margin:0 0 2px;letter-spacing:-.01em}
.sn{font-size:13.5px;color:var(--muted);margin:0 0 10px}
.item{padding:9px 0;border-top:1px solid var(--line)}.item:first-of-type{border-top:none}
.line1{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.tk{font-family:"IBM Plex Mono",monospace;font-weight:500;font-size:14px}
.nm{color:var(--muted);font-size:13.5px}
.quote{margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:13.5px;color:var(--muted)}
.quote .pr{color:var(--ink)}.quote .up{color:var(--up)}.quote .down{color:var(--down)}
.news{font-size:14.5px;margin-top:2px}.news .cat{color:var(--catalyst);font-weight:600}
.flag{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px}
.item.private .tk,.item.private .nm,.item.private .quote{color:var(--faint)}
.note{padding:11px 0;border-top:1px solid var(--line)}.note:first-of-type{border-top:none}
.note .v{font-weight:600}.note p{margin:3px 0 0;color:var(--muted);font-size:14.5px}
footer{padding-top:22px;margin-top:20px;border-top:2px solid var(--ink);font-size:12.5px;color:var(--muted)}
footer p{margin:6px 0}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Spec Tape \u2014 {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style></head><body><div class="rail"></div><div class="wrap">
<div class="util"><span>generated {time} HST</span><div class="sp"></div>{archive_links}</div>
<div class="mast"><h1>SPEC TAPE</h1><p class="tagline">A daily dispatch: the Fab 10, three growth flyers, three wheel setups.</p>
<div class="dateline"><span class="b">MILILANI, HI</span> \u00b7 <span class="b">{date}</span> \u00b7 tone <span class="tone-{tone_c}">{tone}</span> \u00b7 VIX {vix}</div></div>
<p class="lede"><span class="lbl">This morning:</span> {lede}</p>
{sections}
<div class="sec"><h2 class="sh">From the desk</h2><p class="sn">Standing views, tuned to your book.</p>{notes}</div>
<footer><p>Auto-built by GitHub Actions each weekday morning (08:00 HST). Data: Yahoo Finance via yfinance.</p>
<p>Not investment advice and I'm not your advisor \u2014 a research scratchpad. Feeds can lag or err; verify before trading. Rules carried through: 1\u20133% per speculative name, staged tranches.</p>
<p><b>Conflict flag:</b> Anthropic is in the Fab 10 and this was drafted with Claude (made by Anthropic). Apply inverse skepticism to anything positive about it.</p></footer>
</div></body></html>"""

def render(rows_by_sec, date, time_s, tone, vix, lede, archive_links):
    secs = ""
    for sec in WATCHLIST:
        rows = rows_by_sec[sec["head"]]
        secs += (f'<div class="sec"><h2 class="sh">{esc(sec["head"])}</h2>'
                 f'<p class="sn">{sec["note"]}</p>' + "".join(item_html(r) for r in rows) + "</div>")
    notes = "".join(f'<div class="note"><span class="v">{esc(v)}</span><p>{esc(p)}</p></div>' for v,p in DESK_NOTES)
    return PAGE.format(css=CSS, date=esc(date), time=esc(time_s), tone=esc(tone),
                       tone_c=tone.replace(" ","-"), vix=esc(vix), lede=esc(lede),
                       sections=secs, notes=notes, archive_links=archive_links)

# ----------------------------------------------------------------------------
# EMAIL (optional)
# ----------------------------------------------------------------------------
def maybe_email(subject, rows, tone, vix, lede):
    user, pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw):
        return
    to = os.environ.get("GMAIL_TO") or user
    lines = [f"SPEC TAPE \u2014 {subject}", f"tone {tone} | VIX {vix}", "", lede, ""]
    for r in rows:
        px = f"{r['price']} {r['chg']}" if r["price"] else ("private" if r.get("priv") else "")
        lines.append(f"{r['t']:<7} {px:<16} {r['news']}")
    lines += ["", "\u2014 auto-sent by Spec Tape (GitHub Actions)"]
    msg = MIMEText("\n".join(lines))
    msg["Subject"], msg["From"], msg["To"] = f"Spec Tape \u2014 {subject}", user, to
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw); s.sendmail(user, [to], msg.as_string())
        print("email sent")
    except Exception as e:
        print(f"  email fail: {e}")

# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    now = datetime.datetime.now(HST)
    date_s = now.strftime("%a, %b %-d, %Y")
    iso = now.strftime("%Y-%m-%d")
    time_s = now.strftime("%-I:%M %p")

    vix, tone = market_context()
    rows_by_sec, flat = {}, []
    for sec in WATCHLIST:
        rows = []
        for t in sec["tickers"]:
            p, c, cf = quote(t)
            r = {"t":t, "name":NAMES.get(t,t), "price":p, "chg":c, "chg_f":cf,
                 "news":headline(t), "cat":CATALYST.get(t,""), "flag":FLAGS.get(t,"")}
            rows.append(r); flat.append(r)
        for nm, status in sec.get("private", []):
            rows.append({"t":nm, "name":"", "price":None, "chg":None, "chg_f":None,
                         "news":status, "cat":"", "flag":FLAGS.get(nm,""), "priv":True})
        rows_by_sec[sec["head"]] = rows

    lede = build_lede(flat, tone, vix)

    # archive links (existing files + today), newest first
    os.makedirs("docs/archive", exist_ok=True)
    existing = {os.path.basename(p)[:-5] for p in glob.glob("docs/archive/*.html")}
    existing.add(iso)
    dates = sorted(existing, reverse=True)[:30]
    links = " ".join(f'<a href="archive/{d}.html">{d}</a>' for d in dates if d != iso)
    idx_links = links  # index sits in docs/, archive pages link back up one level
    arc_links = '<a href="../index.html">\u2190 latest</a> ' + " ".join(
        f'<a href="{d}.html">{d}</a>' for d in dates if d != iso)

    page_index = render(rows_by_sec, date_s, time_s, tone, vix, lede, idx_links)
    page_arch  = render(rows_by_sec, date_s, time_s, tone, vix, lede, arc_links)

    with open("docs/index.html","w",encoding="utf-8") as f: f.write(page_index)
    with open(f"docs/archive/{iso}.html","w",encoding="utf-8") as f: f.write(page_arch)
    # .nojekyll so GitHub Pages serves the folder as-is
    open("docs/.nojekyll","w").close()
    print(f"wrote docs/index.html and docs/archive/{iso}.html")

    maybe_email(date_s, flat, tone, vix, lede)

if __name__ == "__main__":
    main()
