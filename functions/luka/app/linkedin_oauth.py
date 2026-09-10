"""LinkedIn "Sign In with LinkedIn using OpenID Connect" — flusso self-serve.

Scope self-serve: openid, profile, email.
Per pubblicare a nome dell'utente serve `w_member_social` (prodotto
"Share on LinkedIn", self-serve). Per le Company Pages serve la
"Community Management API" (soggetta ad approvazione LinkedIn): in quel
caso aggiungere gli scope org e gestire la selezione della Pagina.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from .config import get_settings
from .crypto import decrypt, encrypt

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

STATE_TTL_SECONDS = 600


@dataclass
class LinkedInIdentity:
    sub: str
    name: str
    email: str | None
    picture: str | None
    locale: str | None


def make_state(account_type: str) -> str:
    payload = json.dumps({"t": account_type, "ts": int(time.time())})
    return encrypt(payload)


def read_state(state: str) -> str | None:
    raw = decrypt(state or "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if int(time.time()) - int(data.get("ts", 0)) > STATE_TTL_SECONDS:
        return None
    return data.get("t") or "personal"


def build_authorize_url(account_type: str) -> str:
    s = get_settings()
    query = httpx.QueryParams(
        {
            "response_type": "code",
            "client_id": s.linkedin_client_id or "",
            "redirect_uri": s.linkedin_redirect_uri,
            "scope": " ".join(s.scope_list),
            "state": make_state(account_type),
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


async def exchange_code(code: str) -> str:
    s = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": s.linkedin_redirect_uri,
                "client_id": s.linkedin_client_id,
                "client_secret": s.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    r.raise_for_status()
    return r.json()["access_token"]


async def fetch_identity(access_token: str) -> LinkedInIdentity:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    r.raise_for_status()
    d = r.json()
    return LinkedInIdentity(
        sub=d.get("sub", ""),
        name=d.get("name") or d.get("given_name") or "Profilo LinkedIn",
        email=d.get("email"),
        picture=d.get("picture"),
        locale=(d.get("locale") or {}).get("language")
        if isinstance(d.get("locale"), dict)
        else d.get("locale"),
    )
