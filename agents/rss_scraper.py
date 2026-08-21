import logging
import re

import feedparser
import httpx

log = logging.getLogger(__name__)
MAX_PER_SOURCE = 30


async def fetch_rss_jobs(feeds: list[dict[str, str]]) -> list[dict]:
    jobs: list[dict] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        for feed in feeds:
            try:
                log.info("[RSS] Fetching: %s", feed["label"])
                resp = await client.get(
                    feed["url"],
                    follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                log.info("[RSS] %s: %d entries", feed["label"], len(parsed.entries))

                for entry in parsed.entries[:MAX_PER_SOURCE]:
                    try:
                        title = getattr(entry, "title", "") or ""
                        company = getattr(entry, "author", "") or ""
                        job_url = getattr(entry, "link", "") or ""
                        summary = getattr(entry, "summary", "") or ""

                        domain_match = re.search(r"https?://([^/]+)", job_url)
                        domain = re.sub(r"^www\.", "", domain_match.group(1)) if domain_match else ""

                        region, country = "REMOTE", "REMOTE"

                        jobs.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "domain": domain,
                            "url": job_url.strip(),
                            "source": feed["label"],
                            "region": region,
                            "country": country,
                            "description": summary.strip(),
                        })
                    except Exception as e:
                        log.warning("[RSS] Entry parse error: %s", e)

            except Exception as e:
                log.warning("[RSS] %s failed: %s", feed["label"], e)

    return jobs
