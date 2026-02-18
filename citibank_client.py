"""
citibank_client.py
Thin client for Citibank's OAuth 2.0 API (account info + bill payments).

Docs & registration: https://developer.citi.com
"""

import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional
from urllib.parse import urlencode

import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CITI_BASE_URLS = {
    "sandbox": "https://sandbox.apihub.citi.com",
    "production": "https://apihub.citi.com",
}

TOKEN_ENDPOINT = "/gcb/api/v1/oauth/token"
ACCOUNTS_ENDPOINT = "/gcb/api/v1/accounts"
PAYMENT_ENDPOINT = "/gcb/api/v1/payments/billpayment"


@dataclass
class CitiConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    account_id: str        # Citibank checking account ID to debit
    env: str = "sandbox"   # "sandbox" or "production"

    @property
    def base_url(self) -> str:
        return CITI_BASE_URLS[self.env]

    @classmethod
    def from_env(cls) -> "CitiConfig":
        """Load configuration from environment variables / .env file."""
        missing = []
        for var in ("CITI_CLIENT_ID", "CITI_CLIENT_SECRET",
                    "CITI_REDIRECT_URI", "CITI_ACCOUNT_ID"):
            if not os.getenv(var):
                missing.append(var)
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Copy .env.example to .env and fill in your Citibank API credentials."
            )
        return cls(
            client_id=os.environ["CITI_CLIENT_ID"],
            client_secret=os.environ["CITI_CLIENT_SECRET"],
            redirect_uri=os.environ["CITI_REDIRECT_URI"],
            account_id=os.environ["CITI_ACCOUNT_ID"],
            env=os.getenv("CITI_ENV", "sandbox"),
        )


# ---------------------------------------------------------------------------
# OAuth 2.0 helpers
# ---------------------------------------------------------------------------

class CitibankAuthError(Exception):
    pass


class CitibankPaymentError(Exception):
    pass


def get_authorization_url(config: CitiConfig) -> str:
    """
    Build the URL the user must visit to authorize the application.
    Open this URL in a browser; Citibank will redirect to redirect_uri with a code.
    """
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": "accounts_details_transactions payments",
    }
    return f"{config.base_url}/gcb/api/v1/oauth/authorize?{urlencode(params)}"


def exchange_code_for_token(config: CitiConfig, auth_code: str) -> dict:
    """
    Exchange the authorization code (from redirect) for an access token.
    Returns the full token response dict (access_token, refresh_token, expires_in).
    """
    url = config.base_url + TOKEN_ENDPOINT
    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    resp = requests.post(url, data=payload, timeout=30)
    if not resp.ok:
        raise CitibankAuthError(
            f"Token exchange failed [{resp.status_code}]: {resp.text}"
        )
    return resp.json()


def refresh_access_token(config: CitiConfig, refresh_token: str) -> dict:
    """Use a refresh token to obtain a new access token without user interaction."""
    url = config.base_url + TOKEN_ENDPOINT
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    resp = requests.post(url, data=payload, timeout=30)
    if not resp.ok:
        raise CitibankAuthError(
            f"Token refresh failed [{resp.status_code}]: {resp.text}"
        )
    return resp.json()


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


def get_account_balance(config: CitiConfig, access_token: str) -> dict:
    """
    Fetch current balance for the configured checking account.
    Returns a dict with at minimum: { "accountId": ..., "availableBalance": ... }
    """
    url = f"{config.base_url}{ACCOUNTS_ENDPOINT}/{config.account_id}/balance"
    resp = requests.get(url, headers=_auth_headers(access_token), timeout=30)
    if not resp.ok:
        raise CitibankPaymentError(
            f"Balance fetch failed [{resp.status_code}]: {resp.text}"
        )
    return resp.json()


def schedule_payment(
    config: CitiConfig,
    access_token: str,
    payee_name: str,
    amount: float,
    payment_date: date,
    memo: Optional[str] = None,
) -> dict:
    """
    Schedule a bill payment from the configured Citibank checking account.

    Parameters
    ----------
    config         : CitiConfig – API credentials and account info
    access_token   : str        – valid OAuth 2.0 access token
    payee_name     : str        – name of the biller / payee
    amount         : float      – payment amount in USD
    payment_date   : date       – date on which to send the payment
    memo           : str|None   – optional note / reference

    Returns
    -------
    dict  Citibank API response including a confirmationNumber.
    """
    url = config.base_url + PAYMENT_ENDPOINT
    payload = {
        "sourceAccountId": config.account_id,
        "payeeName": payee_name,
        "paymentAmount": {
            "amount": round(amount, 2),
            "currency": "USD",
        },
        "paymentDate": payment_date.strftime("%Y-%m-%d"),
    }
    if memo:
        payload["memo"] = memo[:140]  # Citibank memo field limit

    resp = requests.post(
        url,
        json=payload,
        headers={**_auth_headers(access_token), "Content-Type": "application/json"},
        timeout=30,
    )
    if not resp.ok:
        raise CitibankPaymentError(
            f"Payment scheduling failed [{resp.status_code}]: {resp.text}"
        )
    return resp.json()
