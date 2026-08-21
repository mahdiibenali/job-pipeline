from utils.fingerprint import (
    content_hash,
    domain_fingerprint,
    job_fingerprint,
    llm_cache_key,
)


def test_job_fingerprint_is_deterministic():
    a = job_fingerprint("example.com", "Software Engineer")
    b = job_fingerprint("example.com", "Software Engineer")
    assert a == b
    assert len(a) == 64


def test_job_fingerprint_differs_by_domain():
    a = job_fingerprint("example.com", "Software Engineer")
    b = job_fingerprint("other.com", "Software Engineer")
    assert a != b


def test_job_fingerprint_differs_by_title():
    a = job_fingerprint("example.com", "Software Engineer")
    b = job_fingerprint("example.com", "Senior Software Engineer")
    assert a != b


def test_job_fingerprint_normalizes_url():
    a = job_fingerprint("https://www.Example.com", " Software Engineer ")
    b = job_fingerprint("example.com", "software engineer")
    assert a == b


def test_domain_fingerprint_normalizes():
    a = domain_fingerprint("https://www.Example.com/")
    b = domain_fingerprint("example.com")
    assert a == b


def test_content_hash():
    a = content_hash("hello")
    b = content_hash("hello")
    c = content_hash("world")
    assert a == b
    assert a != c


def test_llm_cache_key():
    a = llm_cache_key("1.0", "some prompt")
    b = llm_cache_key("1.0", "some prompt")
    c = llm_cache_key("1.0", "different prompt")
    assert a == b
    assert a != c
