from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(default=ROOT / "data" / "pipeline.db")
    chrome_debug_port: int = Field(default=9222, ge=1024, le=65535)

    budget_gemini: int = Field(default=50, ge=0)
    budget_adzuna: int = Field(default=500, ge=0)
    budget_serp: int = Field(default=100, ge=0)
    budget_brave: int = Field(default=150, ge=0)
    budget_playwright: int = Field(default=200, ge=0)
    budget_smtp: int = Field(default=50, ge=0)
    budget_httpx: int = Field(default=2000, ge=0)
    budget_ddg: int = Field(default=200, ge=0)

    cb_failure_threshold: int = Field(default=5, ge=1)
    cb_default_cooldown_hours: int = Field(default=4, ge=1)

    cb_cooldown_linkedin: int = Field(default=8, ge=1)
    cb_cooldown_wellfound: int = Field(default=4, ge=1)
    cb_cooldown_weworkremotely: int = Field(default=2, ge=1)
    cb_cooldown_adzuna: int = Field(default=1, ge=0)
    cb_cooldown_rss: int = Field(default=1, ge=0)

    min_fit_score: float = Field(default=0.35, ge=0.0, le=1.0)
    high_priority_score: float = Field(default=0.60, ge=0.0, le=1.0)
    max_high_priority: int = Field(default=30, ge=1)

    adzuna_app_id: str = Field(default="")
    adzuna_api_key: str = Field(default="")

    log_level: str = Field(default="INFO")

    # Source URLs
    linkedin_queries: list[dict[str, str]] = Field(default=[
        {"url": "https://www.linkedin.com/jobs/search/?keywords=full+stack+python+vue+visa+sponsorship&location=Europe&f_WT=2", "label": "LinkedIn: fullstack+visa+Europe"},
        {"url": "https://www.linkedin.com/jobs/search/?keywords=python+fastapi+remote+relocation&location=Worldwide&f_WT=2", "label": "LinkedIn: python+fastapi+remote"},
        {"url": "https://www.linkedin.com/jobs/search/?keywords=vue.js+python+%22open+to+relocation%22&location=Belgium", "label": "LinkedIn: vue+python+relocation+Belgium"},
        {"url": "https://www.linkedin.com/jobs/search/?keywords=vue.js+python+%22open+to+relocation%22&location=Netherlands", "label": "LinkedIn: vue+python+relocation+NL"},
    ])
    rss_feeds: list[dict[str, str]] = Field(default=[
        {"url": "https://weworkremotely.com/remote-jobs/search?term=python+vue&format=rss", "label": "WWR: python+vue"},
        {"url": "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss", "label": "WWR: full-stack"},
        {"url": "https://remotive.com/remote-jobs/software-dev/feed", "label": "Remotive: software-dev"},
        {"url": "https://remotive.com/remote-jobs/software-dev?search=vue+python&format=rss", "label": "Remotive: vue+python"},
    ])
    browser_queries: list[dict[str, str]] = Field(default=[
        {"url": "https://weworkremotely.com/remote-jobs/search?term=python+vue", "label": "WWR browser: python+vue", "platform": "weworkremotely"},
        {"url": "https://wellfound.com/jobs?role=fullstack&remote=true", "label": "Wellfound: fullstack remote", "platform": "wellfound"},`n        {"url": "https://www.indeed.com/jobs?q=python+developer&l=Europe&fromage=14", "label": "Indeed: python Europe 14d", "platform": "indeed"},
    ])


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

