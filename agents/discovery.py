import json
import logging
import time
from pathlib import Path

from config.settings import get_settings
from scheduler.budget_guard import BudgetGuard
from scheduler.circuit_breaker import CircuitBreaker, CircuitOpenError
from scheduler.state_machine import enqueue_job
from utils.fingerprint import job_fingerprint

from agents.enrichment import enrich_job_detail
from agents.rss_scraper import fetch_rss_jobs
from agents.linkedin_scraper import extract_linkedin_jobs
from agents.weworkremotely_scraper import extract_weworkremotely_jobs
from agents.indeed_scraper import extract_indeed_jobs
from agents.wellfound_scraper import extract_wellfound_jobs
from agents.scoring import score_job

log = logging.getLogger(__name__)
settings = get_settings()
budget = BudgetGuard()

OUTPUT_FILE = settings.db_path.parent / "discovered_jobs.json"


async def run_discovery(persist: bool = True) -> list[dict]:
    all_jobs: list[dict] = []
    seen: set[str] = set()

    # --- Step 1: RSS Feeds ---
    log.info("=== Step 1: RSS Feeds ===")
    breaker_rss = CircuitBreaker("rss")
    try:
        rss_jobs = await breaker_rss.call(fetch_rss_jobs, settings.rss_feeds)
        for job in rss_jobs:
            fp = job_fingerprint(job["domain"], job["title"])
            if fp not in seen:
                seen.add(fp)
                job["fingerprint"] = fp
                all_jobs.append(job)
    except CircuitOpenError:
        log.info("[CB] Skipping RSS: circuit open.")

    # --- Step 2: Browser Sources ---
    log.info("=== Step 2: Browser Sources ===")
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as pw:
            addr = f"http://127.0.0.1:{settings.chrome_debug_port}"
            log.info("Connecting to Chrome at port %d", settings.chrome_debug_port)
            browser = await pw.chromium.connect_over_cdp(addr)
            contexts = browser.contexts
            log.info("Connected. Contexts: %d", len(contexts))
            page = await contexts[0].new_page() if contexts else await browser.new_page()

            browser_queries = list(settings.browser_queries)
            linkedin_queries = list(settings.linkedin_queries)

            for query in browser_queries:
                platform = query.get("platform", "")
                breaker = CircuitBreaker(platform)

                new_jobs = []
                try:
                    if platform == "weworkremotely":
                        new_jobs = await breaker.call(
                            extract_weworkremotely_jobs, page, query["url"], query["label"],
                        )
                    elif platform == "wellfound":
                        new_jobs = await breaker.call(
                            extract_wellfound_jobs, page, query["url"], query["label"],
                        )
                    elif platform == "indeed":
                        new_jobs = await breaker.call(
                            extract_indeed_jobs, page, query["url"], query["label"],
                        )
                except CircuitOpenError:
                    log.info("[CB] Skipping %s: circuit open.", platform)
                    continue

                for job in new_jobs:
                    fp = job_fingerprint(job["domain"], job["title"])
                    if fp not in seen:
                        seen.add(fp)
                        job["fingerprint"] = fp
                        all_jobs.append(job)

            if linkedin_queries:
                breaker_li = CircuitBreaker("linkedin")
                try:
                    li_jobs = await breaker_li.call(extract_linkedin_jobs, page, linkedin_queries)
                    for job in li_jobs:
                        fp = job_fingerprint(job["domain"], job["title"])
                        if fp not in seen:
                            seen.add(fp)
                            job["fingerprint"] = fp
                            all_jobs.append(job)
                except CircuitOpenError:
                    log.info("[CB] Skipping LinkedIn: circuit open.")

            await page.close()
            await browser.close()

    except Exception as e:
        log.warning("Playwright connection failed: %s. Continuing with RSS results only.", e)

    # --- Scoring ---
    for job in all_jobs:
        score, visa_sig, region, country, skills = score_job(
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("description", ""),
        )
        job["discovery_score"] = score
        job["visa_signal"] = visa_sig
        job["region"] = region
        job["country"] = country
        job["stack_match"] = skills
        if "location" in job:
            del job["location"]

    # Filter high priority
    high = [j for j in all_jobs if j.get("discovery_score", 0) >= settings.high_priority_score]
    high.sort(key=lambda j: j["discovery_score"], reverse=True)
    high = high[: settings.max_high_priority]

    # Enrich high priority jobs
    log.info("Enriching %d qualifying jobs with detail pages", len(high))
    for job in high:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{settings.chrome_debug_port}"
                )
                ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await ctx.new_page()
                job = await enrich_job_detail(page, job)
                await page.close()
                await browser.close()
        except Exception as e:
            log.warning("Enrichment error: %s", e)

    # Persist
    qualified = [j for j in all_jobs if j.get("discovery_score", 0) >= settings.min_fit_score]
    inserted = 0

    if persist:
        for job in all_jobs:
            if job.get("discovery_score", 0) >= settings.min_fit_score:
                jid = enqueue_job(
                    title=job["title"],
                    company=job["company"],
                    domain=job["domain"],
                    url=job["url"],
                    source=job["source"],
                    fingerprint=job["fingerprint"],
                    region=job.get("region"),
                    country=job.get("country"),
                    discovery_score=job.get("discovery_score", 0.0),
                    visa_signal=job.get("visa_signal"),
                )
                if jid:
                    inserted += 1

    # Write JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scraped": len(all_jobs),
        "total_qualified": len(qualified),
        "jobs": all_jobs,
    }
    OUTPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("DISCOVERY COMPLETE")
    log.info("  Scraped total   : %d", len(all_jobs))
    log.info("  Qualified (>=%.2f): %d", settings.min_fit_score, len(qualified))
    log.info("  High (>=%.2f)    : %d", settings.high_priority_score, len(high))
    if persist:
        log.info("Persisted %d new jobs to queue (duplicates skipped).", inserted)
    log.info("JSON output written to: %s", OUTPUT_FILE)

    return all_jobs
