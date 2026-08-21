import json
import logging

from agents.scoring import extract_stack_match, extract_visa_signal
from utils.anti_bot import human_delay, wait_dom

log = logging.getLogger(__name__)

DETAIL_SELECTORS = [
    ".job-description",
    ".description__text",
    "[data-testid='job-description']",
    "article",
    ".posting-description",
    "main",
]


async def enrich_job_detail(page, job: dict) -> dict:
    job = dict(job)
    try:
        log.info("[Detail] Visiting: %s", job["url"])
        await page.goto(job["url"], wait_until="domcontentloaded")
        await human_delay(1, 3)
        await wait_dom(page)

        desc_text = ""
        for sel in DETAIL_SELECTORS:
            el = await page.query_selector(sel)
            if el:
                desc_text = await el.inner_text()
                if len(desc_text) > 50:
                    break

        text_lower = (job.get("title", "") + " " + desc_text).lower()
        job["visa_signal"] = extract_visa_signal(text_lower)
        job["stack_match"] = extract_stack_match(text_lower)
        job["description"] = desc_text

    except Exception as e:
        log.warning("[Detail] Enrich failed for %s: %s", job["url"], e)

    return job
