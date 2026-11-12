"""
The few parts of Razorpay's API this app uses: payment links, and checking signatures.

Students pay on Razorpay's hosted page, so the app never sees card or UPI details. A plain
HTTPS client with timeouts (like the SMS code) keeps this small and dependency-free.
Docs: https://razorpay.com/docs/api/payments/payment-links/
"""

import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


class RazorpayError(Exception):
    """Razorpay could not be reached or refused the request."""


def configured() -> bool:
    return bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and settings.RAZORPAY_WEBHOOK_SECRET
    )


def test_mode() -> bool:
    return settings.RAZORPAY_KEY_ID.startswith("rzp_test_")


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = settings.RAZORPAY_API_URL.rstrip("/") + "/" + path.lstrip("/")
    token = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()
    ).decode()
    request = urllib.request.Request(  # noqa: S310 (fixed https URL from settings)
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}").get("error", {}).get("description", "")
        except ValueError:
            detail = ""
        raise RazorpayError(f"Razorpay refused the request ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RazorpayError(f"Razorpay could not be reached: {exc}") from exc


def create_payment_link(
    *,
    amount_paise: int,
    reference: str,
    description: str,
    customer: dict,
    callback_url: str,
    expire_by: int,
    notes: dict,
) -> dict:
    return _request(
        "POST",
        "payment_links",
        {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "reference_id": reference,
            "description": description[:2048],
            "customer": customer,
            # The student is sent straight to the page; Razorpay need not message them.
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "callback_url": callback_url,
            "callback_method": "get",
            "expire_by": expire_by,
            "notes": notes,
        },
    )


def fetch_payment_link(link_id: str) -> dict:
    return _request("GET", f"payment_links/{link_id}")


def cancel_payment_link(link_id: str) -> dict:
    return _request("POST", f"payment_links/{link_id}/cancel")


def _signature(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def callback_signature_valid(
    *, link_id: str, reference: str, status: str, payment_id: str, signature: str
) -> bool:
    """The signature on the redirect back from Razorpay's page (made with the key secret)."""
    message = f"{link_id}|{reference}|{status}|{payment_id}".encode()
    return hmac.compare_digest(
        _signature(settings.RAZORPAY_KEY_SECRET, message).encode(), (signature or "").encode()
    )


def webhook_signature_valid(body: bytes, signature: str) -> bool:
    """The X-Razorpay-Signature header on a webhook (made with the webhook secret)."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    return hmac.compare_digest(
        _signature(settings.RAZORPAY_WEBHOOK_SECRET, body).encode(), (signature or "").encode()
    )
