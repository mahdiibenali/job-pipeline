import logging

from utils.anti_bot import human_delay, slow_scroll, wait_dom

log = logging.getLogger(__name__)


async def extract_weworkremotely_jobs(page, url: str, label: str) -> list[dict]:
    jobs: list[dict] = []

    try:
        log.info("[WWR] Loading: %s", label)
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay(2, 4)
        await wait_dom(page)
        await slow_scroll(page, steps=2, pause=1)

        cards = await page.query_selector_all("li.feature, section.jobs article li")
        log.info("[WWR] Found %d job cards", len(cards))

        for card in cards:
            try:
                title_el = await card.query_selector("span.title, h2")
                company_el = await card.query_selector("span.company, .company")
                link_el = await card.query_selector("a")

                title = await title_el.inner_text() if title_el else ""
                company = await company_el.inner_text() if company_el else ""
                url = await link_el.get_attribute("href") if link_el else ""

                if url and not url.startswith("http"):
                    url = f"https://weworkremotely.com{url}"

                jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "domain": "weworkremotely.com",
                    "url": url.strip(),
                    "source": label,
                    "region": "REMOTE",
                    "country": "REMOTE",
                    "description": "",
                })
            except Exception as e:
                log.debug("[WWR] Card parse error: %s", e)

    except Exception as e:
        log.warning("[WWR] %s failed: %s", label, e)

    return jobs
