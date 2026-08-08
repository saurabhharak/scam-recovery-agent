"""Tests for the pre-filled Gmail compose link generator.

The agent builds a mailto/Gmail-compose link so the user can send the
complaint from THEIR OWN email in one tap — no SMTP, no credentials.
"""

from urllib.parse import urlparse, parse_qs

from bodyguard.email_link import (
    build_gmail_compose_url,
    build_mailto_url,
    encode_field,
    MAX_GMAIL_BODY_CHARS,
)


def test_gmail_url_has_expected_params():
    url = build_gmail_compose_url(
        to="fraud@hdfcbank.com",
        subject="Fraud complaint ref BNK-123",
        body="Dear bank,\n\n₹50,000 was debited.\n\nRegards, Saurabh",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "mail.google.com"
    qs = parse_qs(parsed.query)
    assert qs["to"] == ["fraud@hdfcbank.com"]
    assert qs["su"] == ["Fraud complaint ref BNK-123"]
    assert qs["body"][0].startswith("Dear bank")


def test_gmail_url_encodes_rupee_and_newlines():
    """Special chars (₹, newlines, &, =) must be URL-encoded correctly."""
    url = build_gmail_compose_url(
        to="fraud@hdfcbank.com",
        subject="Refund ₹50,000 & dispute",
        body="Amount: ₹50,000\nUTR: 323456789012",
    )
    qs = parse_qs(urlparse(url).query)
    assert "₹" in qs["su"][0]  # decoded back to ₹
    assert "₹" in qs["body"][0]
    assert "\n" in qs["body"][0]


def test_gmail_url_supports_multiple_recipients():
    url = build_gmail_compose_url(
        to=["fraud@hdfcbank.com", "grievance@hdfcbank.com"],
        subject="Fraud complaint",
        body="Body",
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["to"] == ["fraud@hdfcbank.com,grievance@hdfcbank.com"]


def test_gmail_url_truncates_very_long_body():
    long_body = "x" * (MAX_GMAIL_BODY_CHARS + 500)
    url = build_gmail_compose_url(to="a@b.com", subject="S", body=long_body)
    qs = parse_qs(urlparse(url).query)
    # Body is truncated to a safe length (never exceeds the cap)
    assert len(qs["body"][0]) <= MAX_GMAIL_BODY_CHARS + 10  # small tolerance


def test_mailto_url_builds():
    url = build_mailto_url(
        to="fraud@hdfcbank.com",
        subject="Fraud complaint",
        body="Body text",
    )
    assert url.startswith("mailto:fraud@hdfcbank.com?")
    assert "subject=" in url
    assert "body=" in url


def test_encode_field_handles_special_chars():
    encoded = encode_field("a&b=c?d ₹")
    # '&' must be percent-encoded (%26) so it doesn't break the query string
    assert "%26" in encoded
    assert "&" not in encoded  # literal & would break the URL
    # '=' and '?' also percent-encoded for safety in query values
    assert "%3D" in encoded
    assert "%3F" in encoded
