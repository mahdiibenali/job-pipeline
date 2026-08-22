# 🎯 job-pipeline

Autonomous **job-leads scraping pipeline** with production-grade reliability engineering: durable state machine, circuit breakers, budget guards and anti-detection browsing — built to run unattended for hours without getting blocked.

![CI](https://github.com/mahdiibenali/job-pipeline/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Playwright](https://img.shields.io/badge/Playwright-CDP_attach-2EAD33?logo=playwright)
![Pydantic](https://img.shields.io/badge/pydantic-v2-E92063?logo=pydantic)
![pytest](https://img.shields.io/badge/tested_with-pytest-0A9EDC?logo=pytest)
![License](https://img.shields.io/badge/License-MIT-green)

## 🎯 The problem

Job boards rate-limit and block scrapers within minutes, and a crashed run loses all progress. This pipeline is engineered around **unattended reliability**: every source has its own circuit breaker, every resource has a daily budget, every job lives in a durable SQLite state machine with an audit log — so the run survives crashes, bans and 3 AM failures.

## 🧠 The anti-detection idea

Instead of launching a fresh headless browser (trivially detectable), the pipeline **attaches to your real Chrome session over CDP** (`connect_over_cdp` on port 9222). Jobs are scraped inside the browser you actually use — same cookies, same fingerprint, same history. On top of that:

- **Gaussian human delays** (µ=1.5s, σ=0.6, truncated) between every action
- **Viewport rotation (5 profiles) × user-agent rotation (10 profiles)**
- **Slow-scroll simulation**, DOM-settle waits and typing simulation
- **Job fingerprinting** (SHA-256 of domain+title) so nothing is visited twice
- **Graceful degradation** — if Chrome isn't running, discovery falls back to RSS-only sources

## ✨ Features

| Module | What it does |
|---|---|
| `agents/` | Source scrapers: LinkedIn, Wellfound, WeWorkRemotely, Remotive (RSS), Indeed |
| `agents/scoring.py` | Weighted lead scoring for visa-sponsorship hunting: visa signal 40% · tech-stack match 35% · target region 15%, with hard skip-signals for agencies/internships |
| `scheduler/orchestrator.py` | Runs full discovery → scoring → enrichment cycles with a live Rich dashboard |
| `scheduler/state_machine.py` | Durable SQLite state machine — `PENDING → PROCESSING → EXTRACTED → QUALIFIED/DISQUALIFIED → CV_DONE → CL_DONE → PENDING_REVIEW → APPROVED/REJECTED/ARCHIVED`, plus `FAILED` / `DEAD_LETTER`, transition enforcement and an audit row per transition |
| `scheduler/circuit_breaker.py` | DB-persisted per-source breakers (`CLOSED/HALF_OPEN/OPEN`) with cooldowns (LinkedIn 8h after 5 failures…) |
| `scheduler/budget_guard.py` | Daily hard caps across 8 resource types with live burn-down tracking |
| `db/` | WAL-mode SQLite persistence, lease-based queue (30-min leases, stale-lease sweeper), retry backoff (1/5/15 min + jitter), dead-letter queue after 3 retries |
| `tests/` | 7 pytest suites · 56 tests covering breakers, guards, state machine, scoring, migrations |

## 🏗️ Architecture

```
            ┌────────────┐   circuit    ┌──────────────┐
 RSS feeds ─►│            │──breakers───►│  scoring     │
 LinkedIn  ─►│ discovery  │              │ (visa/skills)│──► enrichment ──► SQLite
 Wellfound ─►│ (Playwright│──budget─────►│              │        (LLM)      │
 WWR       ─►│  via CDP)  │  guard       └──────────────┘                   ▼
 Indeed    ─►│            │                              exports / reports / Rich dashboard
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

All source definitions, scoring weights, breaker cooldowns and budget caps are typed settings in [`config/settings.py`](config/settings.py) (pydantic-settings, overridable via `.env`). [`config/sources.yaml`](config/sources.yaml) documents the source catalog; promoting it to a live registry is on the roadmap.

## 🧪 Testing

```bash
pytest                # 56 tests across 7 suites
```

Suites cover circuit-breaker transitions, budget-guard enforcement, state-machine transitions, lead scoring, lease semantics and DB migrations. CI runs the full suite on every push ([workflow](.github/workflows/ci.yml)).

## 🔭 Roadmap

- [ ] Ruff-clean codebase and add lint gate to CI
- [ ] Make `sources.yaml` a live, hot-reloaded source registry
- [ ] Export connectors (Sheets, Notion, webhooks)
- [ ] LLM-generated cover letters wired into the `CL_DONE` stage
- [ ] Screenshot tour of the Rich operations dashboard

## 📄 License

MIT — see [LICENSE](LICENSE).
