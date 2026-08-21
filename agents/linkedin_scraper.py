import logging

from agents.base import BrowserScraper
from utils.anti_bot import human_delay, slow_scroll, wait_dom

log = logging.getLogger(__name__)


async def extract_linkedin_jobs(page, queries: list[dict[str, str]]) -> list[dict]:
    jobs: list[dict] = []

    for query in queries:
        try:
            log.info("[LinkedIn] Loading: %s", query["label"])
            await page.goto(query["url"], wait_until="domcontentloaded")
            await human_delay(2, 4)
            await wait_dom(page)
            await slow_scroll(page, steps=3, pause=1.5)

            card_selectors = [
                "li.jobs-search-results__list-item",
                "li.base-card",
            ]
            cards = []
            for sel in card_selectors:
                cards = await page.query_selector_all(sel)
                if cards:
                    break

            log.info("[LinkedIn] Found %d job cards", len(cards))

            for card in cards:
                try:
                    title_el = await card.query_selector(
                        "h3.base-search-card__title, h3.job-result-card__title, "
                        "a.base-card__full-link"
                    )
                    company_el = await card.query_selector(
                        "h4.base-search-card__subtitle, a.job-result-card__meta-item"
                    )
                    location_el = await card.query_selector(
                        "span.job-search-card__location, .job-result-card__location"
                    )
                    link_el = await card.query_selector("a.base-card__full-link, a")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await location_el.inner_text() if location_el else ""
                    url = await link_el.get_attribute("href") if link_el else ""

                    jobs.append({
                        "title": title.strip(),
                        "company": company.strip(),
                        "domain": "linkedin.com",
                        "url": url.strip(),
                        "source": query["label"],
                        "region": "",
                        "country": "",
                        "description": "",
                        "location": location.strip(),
                    })
                except Exception as e:
                    log.debug("[LinkedIn] Card parse error: %s", e)

        except Exception as e:
            log.warning("[LinkedIn] Query failed: %s", e)

    return jobs
