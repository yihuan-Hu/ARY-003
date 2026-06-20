import hashlib
import hmac
import os

PROTECTED_CONTENT = '[protected submission]'
PROTECTION_MODE = 'sealed_commitment_v1'


def _secret():
    return os.environ.get('ARY_SUBMISSION_SECRET', 'dev-only-change-me').encode('utf-8')


def normalize_content(content):
    return (content or '').replace('\r\n', '\n').strip()


def content_hash(content):
    normalized = normalize_content(content).encode('utf-8')
    return hashlib.sha256(normalized).hexdigest()


def content_commitment(content):
    normalized = normalize_content(content).encode('utf-8')
    return hmac.new(_secret(), normalized, hashlib.sha256).hexdigest()


def public_summary(summary=None):
    value = (summary or '').strip()
    return value[:80] if value else PROTECTED_CONTENT


def protect_content(content, summary=None):
    return {
        'content': public_summary(summary),
        'content_hash': content_hash(content),
        'content_commitment': content_commitment(content),
        'content_public_summary': public_summary(summary),
        'content_protection': PROTECTION_MODE,
    }


def verify_content(content, expected_commitment):
    if not expected_commitment:
        return False
    return hmac.compare_digest(content_commitment(content), expected_commitment)
