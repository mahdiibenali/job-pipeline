# 🎯 job-pipeline

Autonomous **job-leads scraping pipeline** with production-grade reliability engineering: state machine, circuit breakers, budget guards and browser fingerprinting — built to run unattended for hours without getting blocked.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Playwright](https://img.shields.io/badge/Playwright-CDP_attach-2EAD33?logo=playwright)
![Pydantic](https://img.shields.io/badge/pydantic-v2-E92063?logo=pydantic)
![pytest](https://img.shields.io/badge/tested_with-pytest-0A9EDC?logo=pytest)
![License](https://img.shields.io/badge/License-MIT-green)

## 🧠 The anti-detection idea

Instead of launching a fresh headless browser (trivially detectable), the pipeline **attaches to your real Chrome session over CDP** (`connect_over_cdp` on port 9222). Jobs are scraped inside the browser you actually use — same cookies, same fingerprint, same history. On top of that:

- **Gaussian human delays** (µ=1.5s, σ=0.6, truncated) between every action
- **Viewport & user-agent rotation** across 10 realistic profiles
- **Slow-scroll simulation** and DOM-settle waits
- **Job fingerprinting** (SHA-256 of domain+title) so nothing is visited twice

## ✨ Features

| Module | What it does |
|---|---|
| `agents/` | Source scrapers: LinkedIn, Wellfound, WeWorkRemotely, Remotive (RSS), Indeed |
| `scheduler/orchestrator.py` | Runs the full discovery → scoring → enrichment cycle |
| `scheduler/state_machine.py` | Durable job states (`discovered → scored → enriched → exported`) |
| `scheduler/circuit_breaker.py` | Per-source failure thresholds + cooldowns (LinkedIn 8h, Wellfound 4h…) |
| `scheduler/budget_guard.py` | Hard caps per resource: Playwright sessions, HTTPX calls, LLM budget |
| `agents/scoring.py` | Weighted lead scoring: visa signal 40% · skill match 35% · region 15% |
| `agents/enrichment.py` | LLM-powered detail enrichment for high-priority leads |
| `db/` | SQLite persistence with migrations |
| `tests/` | 7 pytest suites covering breaker, guard, state machine, scoring, migrations |

## 🏗️ Architecture

```
            ┌────────────┐   circuit    ┌──────────────┐
 RSS feeds ─►│            │──breakers───►│  scoring     │
 LinkedIn  ─►│ discovery  │              │ (visa/skills)│──► enrichment ──► SQLite
 Wellfound ─►│ (Playwright│──budget─────►│              │        (LLM)      │
 WWR       ─►│  via CDP)  │  guard       └──────────────┘                   ▼
 Indeed    ─►│            │                                            exports / reports
             └────────────┘
```

## 🚀 Quick start

```bash
# 1. Start a real Chrome with remote debugging
chrome.exe --remote-debugging-port=9222

# 2. Install & configure
pip install -e ".[dev]"
cp .env.example .env

# 3. Run one full discovery cycle
python -m scheduler.orchestrator --once

# 4. Tests
pytest
```

## ⚙️ Configuration

All sources, scoring weights, circuit-breaker cooldowns and budgets live in [`config/sources.yaml`](config/sources.yaml) and [`config/settings.py`](config/settings.py). Add a new source by dropping a YAML entry — the orchestrator picks it up automatically.

## 📄 License

MIT — see [LICENSE](LICENSE).
