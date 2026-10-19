import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


RAZORPAY_API_URL = 'https://api.razorpay.com/v1'
REQUEST_TIMEOUT_SECONDS = 10


class PaymentProviderError(Exception):
    pass


def get_credentials():
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not key_id or not key_secret:
        raise ImproperlyConfigured(
            'Online payments are not configured. Set the Razorpay key ID and secret.'
        )
    return key_id, key_secret


def get_public_key_id():
    return get_credentials()[0]


def assert_configured():
    get_credentials()
    if not getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', ''):
        raise ImproperlyConfigured(
            'Online payments are not configured. Set the Razorpay webhook secret.'
        )


def verify_checkout_signature(*, order_id, payment_id, signature):
    if not isinstance(signature, str) or not signature:
        return False
    _, key_secret = get_credentials()
    message = f'{order_id}|{payment_id}'.encode('utf-8')
    expected = hmac.new(
        key_secret.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(*, body, signature):
    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
    if not secret:
        raise ImproperlyConfigured(
            'Payment webhooks are not configured. Set the Razorpay webhook secret.'
        )
    if not isinstance(signature, str) or not signature:
        return False
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _request(method, path, *, payload=None):
    key_id, key_secret = get_credentials()
    credentials = base64.b64encode(
        f'{key_id}:{key_secret}'.encode('utf-8')
    ).decode('ascii')
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    request = Request(
        f'{RAZORPAY_API_URL}{path}',
        data=body,
        method=method,
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise PaymentProviderError(
            f'Razorpay rejected the request (HTTP {exc.code}).'
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise PaymentProviderError(
            'Razorpay could not be reached. Please try again.'
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentProviderError(
            'Razorpay returned an invalid response.'
        ) from exc
    if not isinstance(result, dict):
        raise PaymentProviderError('Razorpay returned an invalid response.')
    return result


def create_order(*, amount, currency, receipt, notes):
    return _request(
        'POST',
        '/orders',
        payload={
            'amount': amount,
            'currency': currency,
            'receipt': receipt,
            'notes': notes,
        },
    )


def fetch_payment(payment_id):
    return _request('GET', f'/payments/{payment_id}')
