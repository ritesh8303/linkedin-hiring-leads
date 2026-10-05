from src.filters import has_hiring_intent, is_job_seeker, is_noise, normalize_linkedin_text, qualify_post


def test_unicode_hiring_detection():
    text = normalize_linkedin_text("𝗪𝗲'𝗿𝗲 𝗛𝗶𝗿𝗶𝗻𝗴 Software Engineers")
    assert "we're hiring" in text.lower()
    assert has_hiring_intent(text.lower())


def test_filters_noise_and_seekers():
    assert is_noise("how to get a job tips for engineers")
    assert is_job_seeker("i am open to work as a developer")


def test_qualify_role_match():
    ok, reason, _ = qualify_post(
        "We are hiring a Backend Engineer for our Python team. Apply now!",
        ["Backend Engineer", "Software Engineer"],
    )
    assert ok and reason == "ok"

    ok2, reason2, _ = qualify_post(
        "We are hiring a Marketing Manager. Join our team!",
        ["Backend Engineer"],
    )
    assert not ok2 and reason2 == "role_mismatch"
