import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

log = logging.getLogger(__name__)

DELAY_MU = 1.5
DELAY_SIGMA = 0.6
DELAY_MIN = 0.3
DELAY_MAX = 5.0

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
]

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]


def _truncated_normal(mu: float, sigma: float, lo: float, hi: float) -> float:
    val = random.gauss(mu, sigma)
    return max(lo, min(hi, val))


async def human_delay(min_s: float | None = None, max_s: float | None = None) -> None:
    if min_s is not None and max_s is not None:
        delay = random.uniform(min_s, max_s)
    else:
        delay = _truncated_normal(DELAY_MU, DELAY_SIGMA, DELAY_MIN, DELAY_MAX)
    log.debug("[anti_bot] Delay: %.2fs", delay)
    await asyncio.sleep(delay)


async def slow_scroll(page: "Page", steps: int = 5, pause: int = 2) -> None:
    for _ in range(steps):
        amount = random.randint(200, 600)
        await page.evaluate(f"window.scrollBy(0, {amount})")
        jitter = random.uniform(pause * 0.7, pause * 1.3)
        await asyncio.sleep(jitter)


async def wait_dom(page: "Page", timeout: float = 10.0) -> None:
    await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
    await asyncio.sleep(random.uniform(0.3, 1.5))


def random_viewport() -> dict:
    return random.choice(VIEWPORTS)


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


async def human_type(page: "Page", selector: str, text: str) -> None:
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.25))
