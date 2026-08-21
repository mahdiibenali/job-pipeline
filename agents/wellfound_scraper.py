import logging

from utils.anti_bot import human_delay, slow_scroll, wait_dom

log = logging.getLogger(__name__)


async def extract_wellfound_jobs(page, url: str, label: str) -> list[dict]:
    jobs: list[dict] = []

    try:
        log.info("[Wellfound] Loading: %s", label)
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay(3, 6)
        await wait_dom(page)
        await slow_scroll(page, steps=5, pause=2)

        cards = await page.query_selector_all(
            "[data-test='JobSearchResult'], "
            "div[class*='JobListing'], "
            "a[href*='/jobs/']"
        )
        log.info("[Wellfound] Found %d job elements", len(cards))

        for card in cards:
            try:
                text = await card.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                link = await card.get_attribute("href") or ""

                title = lines[0] if lines else ""
                company = lines[1] if len(lines) > 1 else ""

                if link and not link.startswith("http"):
                    link = f"https://wellfound.com{link}"

                jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "domain": "wellfound.com",
                    "url": link.strip(),
                    "source": label,
                    "region": "",
                    "country": "",
                    "description": text,
                })
            except Exception as e:
                log.debug("[Wellfound] Card parse error: %s", e)

    except Exception as e:
        log.warning("[Wellfound] %s failed: %s", label, e)

    return jobs
