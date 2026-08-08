"""Pre-filled email compose links.

Lets the victim send the complaint from THEIR OWN email account in one tap —
no SMTP setup, no credentials, no third-party integration needed. The agent
builds a Gmail compose URL (or mailto: fallback) with the recipient, subject,
and body pre-filled; the user reviews and hits Send.

This is the honest replacement for "auto-submitting" to banks/portals that
offer no API (see research: cybercrime.gov.in and cms.rbi.org.in both require
OTP + human interaction and expose no public API/SDK).
"""

from urllib.parse import quote, urlencode

# Gmail compose URLs have practical length limits; bodies beyond this risk
# truncation in the browser. The builder truncates with a safety margin.
MAX_GMAIL_BODY_CHARS = 7000


def encode_field(value: str) -> str:
    """URL-encode a single field value (subject/body), preserving safe chars.

    quote() with safe='' percent-encodes everything except unreserved chars,
    so '&', '=', '?', '#', spaces, ₹ etc. survive round-tripping correctly.
    """
    return quote(str(value), safe="")


def build_gmail_compose_url(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
) -> str:
    """Build a Gmail compose URL pre-filled with recipient/subject/body.

    Clicking opens mail.google.com in compose mode with everything filled in.
    Returns a URL with the body truncated to MAX_GMAIL_BODY_CHARS.
    """
    to_str = ",".join(to) if isinstance(to, list) else str(to)
    cc_str = ",".join(cc) if isinstance(cc, list) else (str(cc) if cc else None)

    # Truncate long bodies to avoid browser/URL length issues
    safe_body = body if len(body) <= MAX_GMAIL_BODY_CHARS else body[:MAX_GMAIL_BODY_CHARS]

    params = {
        "view": "cm",
        "fs": "1",
        "to": to_str,
        "su": subject,
        "body": safe_body,
    }
    if cc_str:
        params["cc"] = cc_str

    query = urlencode(params, quote_via=quote)
    return f"https://mail.google.com/mail/?{query}"


def build_mailto_url(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
) -> str:
    """Build a mailto: link as a fallback (opens the user's default mail app)."""
    to_str = ",".join(to) if isinstance(to, list) else str(to)
    parts = [f"subject={encode_field(subject)}", f"body={encode_field(body)}"]
    if cc:
        cc_str = ",".join(cc) if isinstance(cc, list) else str(cc)
        parts.append(f"cc={encode_field(cc_str)}")
    return f"mailto:{to_str}?{'&'.join(parts)}"
