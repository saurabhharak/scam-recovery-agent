"""Tests for recovery_engine JSON robustness.

LLMs often wrap JSON in markdown fences or drop braces. These tests define
the contract: parse_json_response must extract valid JSON from messy output.
"""

import json

import pytest

from bodyguard.recovery_engine import parse_json_response


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"intent": "NEW_SCAM_REPORT", "confidence": 0.95}',
         {"intent": "NEW_SCAM_REPORT", "confidence": 0.95}),
        ('```json\n{"intent": "STATUS_CHECK"}\n```',
         {"intent": "STATUS_CHECK"}),
        ('Here is the result: {"intent": "INFO_RESPONSE", "confidence": 0.8}',
         {"intent": "INFO_RESPONSE", "confidence": 0.8}),
        # The exact failure we saw with DeepSeek on Featherless
        ('intent": "NEW_SCAM_REPORT", "confidence": 0.95}',
         {"intent": "NEW_SCAM_REPORT", "confidence": 0.95}),
        # Empty result
        ("", {}),
        # Garbage
        ("not json at all", {}),
    ],
)
def test_parse_json_response_extracts_valid_json(raw, expected):
    assert parse_json_response(raw) == expected
