import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps

from flask import current_app, g, request

from utils.errors import AppError, ValidationError

ROLE_CONTESTANT = 0
ROLE_ORGANIZER = 1
ROLE_ADMIN = 2


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data):
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('ascii'))


def hash_password(password, salt=None):
    if not password:
        raise ValidationError('password is required')
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        120000,
    ).hex()
    return f'pbkdf2_sha256${salt}${digest}'


def verify_password(password, stored_hash):
    try:
        scheme, salt, expected = stored_hash.split('$', 2)
    except ValueError:
        return False
    if scheme != 'pbkdf2_sha256':
        return False
    actual = hash_password(password, salt).split('$', 2)[2]
    return hmac.compare_digest(actual, expected)


def jwt_secret():
    return current_app.config['JWT_SECRET'].encode('utf-8')


def issue_token(user, ttl_seconds=86400):
    header = {'alg': 'HS256', 'typ': 'JWT'}
    now_ts = int(time.time())
    payload = {
        'sub': user['id'],
        'username': user['username'],
        'role': user['role'],
        'iat': now_ts,
        'exp': now_ts + ttl_seconds,
    }
    signing_input = '.'.join([
        _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8')),
        _b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8')),
    ])
    signature = hmac.new(jwt_secret(), signing_input.encode('ascii'), hashlib.sha256).digest()
    return signing_input + '.' + _b64url_encode(signature)


def decode_token(token):
    try:
        header_b64, payload_b64, signature_b64 = token.split('.', 2)
        signing_input = f'{header_b64}.{payload_b64}'
        expected = hmac.new(jwt_secret(), signing_input.encode('ascii'), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(actual, expected):
            raise AppError('Invalid token', 401)
        payload = json.loads(_b64url_decode(payload_b64))
    except AppError:
        raise
    except Exception as exc:
        raise AppError('Invalid token', 401) from exc

    if payload.get('exp', 0) < int(time.time()):
        raise AppError('Token expired', 401)
    return payload


def current_token_payload():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise AppError('Authorization token is required', 401)
    return decode_token(auth_header.removeprefix('Bearer ').strip())


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            payload = current_token_payload()
            if payload.get('role') not in roles:
                raise AppError('Forbidden', 403)
            g.current_user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator


require_contestant = require_roles(ROLE_CONTESTANT, ROLE_ORGANIZER, ROLE_ADMIN)
require_organizer = require_roles(ROLE_ORGANIZER, ROLE_ADMIN)
require_admin = require_roles(ROLE_ADMIN)
