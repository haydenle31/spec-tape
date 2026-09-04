# Spec Tape — a daily stock newsletter on GitHub

A static newsletter that rebuilds itself every weekday morning and publishes to a
GitHub Pages URL you can bookmark. It covers the **Fab 10**, three **speculative
growth** names (RKLB, OKLO, IONQ), and three **wheel candidates** (SOFI, RBLX, F).

- **Data:** Yahoo Finance via `yfinance` — free, no API key.
- **Schedule:** GitHub Actions cron, 08:00 Hawaii time (18:00 UTC), Mon–Fri.
- **Output:** `docs/index.html` (today) + `docs/archive/YYYY-MM-DD.html` (back-issues).
- **Optional:** a one-line market lede from Mistral, and an email copy via Gmail.

Nothing in this repo needs editing to work. To change coverage later, edit the
`WATCHLIST`, `CATALYST`, and `DESK_NOTES` blocks at the top of `generate.py`.

---

## What's in this repo

```
spec-tape/
├── generate.py                     # builds the newsletter (edit config at top to customize)
├── requirements.txt                # Python deps: yfinance, requests
├── README.md                       # this file
├── .github/
│   └── workflows/
│       └── spec-tape.yml           # the daily schedule + build + publish
└── docs/                           # what GitHub Pages serves (auto-updated each run)
    ├── index.html                  # placeholder until the first run overwrites it
    ├── .nojekyll
    └── archive/
        └── (dated issues appear here)
```

---

## Setup — do these in order

You need a free GitHub account. Everything else is optional.

### 1. Put these files in a new repository

**Option A — git (recommended, keeps folder paths intact):**

```bash
# from inside the unzipped spec-tape/ folder
git init
git add .
git commit -m "Spec Tape newsletter"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/spec-tape.git
git push -u origin main
```

**Option B — GitHub website (no command line):**

1. Create the repo at github.com → **New repository** → name `spec-tape` → **Create**.
2. **Add file → Upload files**, then drag in `generate.py`, `requirements.txt`, and `README.md`. Commit.
3. The workflow lives in a dotted folder that drag-upload can miss, so create it by hand:
   **Add file → Create new file**, and in the name box type exactly:
   `.github/workflows/spec-tape.yml`
   (typing the slashes creates the folders). Paste the contents of `spec-tape.yml`, then commit.

### 2. (Optional) Add secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Skip any you don't want; the newsletter still builds without them.

| Secret | Purpose |
|---|---|
| `MISTRAL_API_KEY` | Writes the one-line market lede. Without it, a plain auto-lede is used. |
| `GMAIL_USER` | Your Gmail address, to also email you the issue. |
| `GMAIL_APP_PASSWORD` | A Gmail **App Password** (not your login password). |
| `GMAIL_TO` | Where to send it. Defaults to `GMAIL_USER` if omitted. |

**Do not add `GITHUB_TOKEN`** — GitHub provides it automatically.

### 3. Run it once, manually

Repo → **Actions** tab → if prompted, click **"I understand my workflows, enable them."**
Select **Spec Tape Daily** → **Run workflow** → **Run workflow**.
Wait for the green check. This first run is what creates `docs/` content.

### 4. Turn on GitHub Pages

Repo → **Settings → Pages** → **Source: Deploy from a branch** →
**Branch: `main`**, **Folder: `/docs`** → **Save**.
After ~1 minute your live URL appears there:
`https://YOUR_USERNAME.github.io/spec-tape/` — bookmark it.

### 5. That's it

The workflow now runs itself at **18:00 UTC (08:00 HST), Mon–Fri**, commits the
new issue, and Pages updates. Past issues accumulate in `docs/archive/` and link
from the top of each page.

---

## Common issues

- **Pages shows 404.** You enabled Pages before the first run created `docs/`. Do
  **Step 3 before Step 4.** Re-run the workflow, then reload the Pages URL.
- **The page shows up but prices are blank / say "—".** Yahoo returned nothing for
  those tickers on that run (it happens occasionally). The script falls back to a
  seed line instead of crashing; the next run usually fixes it.
- **The 8:00 timing drifts.** GitHub's free cron commonly fires 5–15 minutes late
  and can skip a run under load. For closer-to-8:00, change the cron in
  `spec-tape.yml` to `55 17 * * 1-5`. It will never be exact.
- **I want it on weekends too.** In `spec-tape.yml`, change `1-5` to `*`.
- **A ticker is permanently blank.** That's a Yahoo symbol problem, not the code.
  Confirm the symbol resolves on finance.yahoo.com.

---

## Customizing coverage

Open `generate.py`. Everything you'd change lives in the first ~60 lines:

- `WATCHLIST` — the sections and which tickers are in each.
- `NAMES` — display names (e.g., `"IONQ":"IonQ · quantum"`).
- `CATALYST` — the short "▸ ..." hint after each headline.
- `SEED_NEWS` — fallback one-liners used only when Yahoo news is empty.
- `DESK_NOTES` — the "From the desk" commentary at the bottom.

Save, commit, push. The next run uses your changes.

---

*Not investment advice. Data can lag or be wrong — verify before trading.*
