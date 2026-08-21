from agents.scoring import (
    extract_stack_match,
    extract_visa_signal,
    infer_region,
    score_job,
    SKIP_SIGNALS,
)


class TestExtractStackMatch:
    def test_matches_skills(self):
        result = extract_stack_match("python vue.js docker postgresql")
        assert "Python" in result
        assert "Vue.js" in result
        assert "Docker" in result
        assert "PostgreSQL" in result

    def test_empty_text(self):
        assert extract_stack_match("") == []

    def test_case_insensitive(self):
        result = extract_stack_match("PYTHON FASTAPI")
        assert "Python" in result
        assert "FastAPI" in result


class TestExtractVisaSignal:
    def test_detects_visa_sponsorship(self):
        assert extract_visa_signal("we offer visa sponsorship") == "visa sponsorship"

    def test_detects_relocation(self):
        assert extract_visa_signal("open to relocation") == "open to relocation"

    def test_no_signal(self):
        assert extract_visa_signal("just a normal job posting") is None

    def test_remote_worldwide(self):
        assert extract_visa_signal("remote worldwide position") == "remote worldwide"


class TestInferRegion:
    def test_europe(self):
        region, country = infer_region("based in europe")
        assert region == "EU"

    def test_belgium(self):
        region, country = infer_region("located in brussels")
        assert country == "BE"

    def test_remote(self):
        region, country = infer_region("worldwide remote")
        assert region == "REMOTE"

    def test_unknown(self):
        region, country = infer_region("some random location")
        assert region == "UNKNOWN"


class TestScoreJob:
    def test_skip_signal_zeros(self):
        score, visa, region, country, skills = score_job(
            "Software Engineer Internship"
        )
        assert score == 0.0

    def test_visa_and_skills_boost_score(self):
        score, visa, region, country, skills = score_job(
            title="Full Stack Engineer",
            description="Python Vue.js Docker remote anywhere visa sponsorship",
        )
        assert score > 0.5
        assert visa is not None
        assert region in ("EU", "REMOTE")

    def test_low_score_no_signals(self):
        score, visa, region, country, skills = score_job(
            title="Junior Developer",
            description="local position on-site only",
        )
        assert score == 0.0

    def test_skill_extraction(self):
        _, _, _, _, skills = score_job(
            title="Python Developer",
            description="Vue.js Docker PostgreSQL FastAPI",
        )
        assert "Python" in skills
        assert "Vue.js" in skills
        assert "Docker" in skills

    def test_visa_weight_is_40_percent(self):
        score, visa, _, _, _ = score_job(
            title="Engineer",
            description="visa sponsorship available",
        )
        assert visa is not None
        assert score == 0.40

    def test_all_skip_signals(self):
        for signal in SKIP_SIGNALS:
            score, _, _, _, _ = score_job(title="Engineer", description=signal)
            assert score == 0.0, f"Signal '{signal}' should zero the score"
