import hashlib
import re
import unicodedata

_SCHEME = re.compile(r"^https?://", re.IGNORECASE)
_WWW = re.compile(r"^www\.", re.IGNORECASE)


def _normalizer(text: str) -> str:
    text = text.lower().strip().rstrip("/")
    text = _SCHEME.sub("", text)
    text = _WWW.sub("", text)
    return unicodedata.normalize("NFD", text)


def job_fingerprint(domain: str, title: str) -> str:
    raw = f"{_normalizer(domain)}|{_normalizer(title)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def domain_fingerprint(domain: str) -> str:
    return _normalizer(domain)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def llm_cache_key(template_version: str, input_text: str) -> str:
    raw = f"{template_version}:{input_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
