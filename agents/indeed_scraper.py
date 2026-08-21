import logging

from utils.anti_bot import human_delay, slow_scroll, wait_dom

log = logging.getLogger(__name__)


async def extract_indeed_jobs(page, url: str, label: str) -> list[dict]:
    """Extract job cards from an Indeed search results page."""
    jobs: list[dict] = []

    try:
        log.info("[Indeed] Loading: %s", label)
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay(2, 4)
        await wait_dom(page)
        await slow_scroll(page, steps=3, pause=1)

        cards = await page.query_selector_all("div.job_seen_beacon, div.jobsearch-SerpJobCard, td.resultContent")
        log.info("[Indeed] Found %d job cards", len(cards))

        for card in cards:
            try:
                title_el = (
                    await card.query_selector("h2.jobTitle a")
                    or await card.query_selector("a[data-jk]")
                    or await card.query_selector("h2 a")
                )
                if not title_el:
                    continue

                title = (await title_el.inner_text() or "").strip()
                link = await title_el.get_attribute("href") or ""
                if link and not link.startswith("http"):
                    link = f"https://www.indeed.com{link}"

                company_el = await card.query_selector("span.companyName, span.company")
                company = (await company_el.inner_text()).strip() if company_el else ""

                location_el = await card.query_selector("div.companyLocation, div.location")
                location = (await location_el.inner_text()).strip() if location_el else ""

                snippet_el = await card.query_selector("div.job-snippet")
                description = (await snippet_el.inner_text(" ")).strip() if snippet_el else ""

                salary_el = await card.query_selector(
                    "div.salary-snippet-container, span.estimated-salary"
                )
                salary = (await salary_el.inner_text()).strip() if salary_el else ""

                location_lower = location.lower()
                is_remote = (
                    "remote" in location_lower
                    or "work from home" in location_lower
                    or "remote" in title.lower()
                )

                jobs.append({
                    "title": title,
                    "company": company,
                    "domain": "indeed.com",
                    "url": link.strip(),
                    "source": label,
                    "region": "REMOTE" if is_remote else "",
                    "country": "REMOTE" if is_remote else location,
                    "description": description,
                    "salary": salary,
                })
            except Exception as e:
                log.debug("[Indeed] Card parse error: %s", e)

    except Exception as e:
        log.warning("[Indeed] %s failed: %s", label, e)

    return jobs
