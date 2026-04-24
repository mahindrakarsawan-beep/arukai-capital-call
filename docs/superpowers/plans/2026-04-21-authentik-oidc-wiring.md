# Authentik OIDC Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan pairs with `2026-04-21-por158-replan.md` and closes the §B1 deferred item from that slice.

**Goal:** replace the backend's JWT+bcrypt login path with Authentik OIDC while keeping every existing auth-guarded test passing. Concretely: `/auth/oidc/authorize` and `/auth/oidc/callback` become the documented production login path; `/auth/login` (password) remains behind a feature flag (`AUTH_MODE`) so staging can run dual-mode and production can disable it after the first pilot.

**Architecture:** stay on existing stack (FastAPI + Next.js + Cloud Run backend + GCE VM for Authentik). Use the Authentik instance already live on GCE VM `34.12.153.46:9000` (POR-162, merged PR #5). New code lives in `backend/app/auth.py`, `backend/app/routers/auth.py`, and a new `backend/app/oidc.py` helper module. No schema migration — `User.role` and `User.password_hash` already exist; the OIDC path reuses them. No net-new infra — HTTPS termination for Authentik is §C1 of the POR-158 replan (pre-req, see Dependencies).

**Tech Stack:** Python 3.12 + SQLAlchemy async + FastAPI + pytest + `httpx>=0.27.0` (already a dep — replaces hand-rolled `urllib.request` in `oidc_callback`) + `python-jose` (already a dep, used for JWT) + Authentik 2024.12 (GCE VM). No frontend work — the Next.js app already calls `/auth/oidc/authorize` via a redirect button when the env gate is on.

---

## Dependencies and preconditions

### Hard pre-req — §C1 Cloudflare tunnel (or equivalent TLS)

Authentik on the GCE VM is currently reachable only at `http://34.12.153.46:9000`. Running the OIDC discovery + token-exchange handshake over plain HTTP means:

- The backend fetches `http://.../.well-known/openid-configuration` in clear text — MITM can swap `token_endpoint` and `jwks_uri` to attacker-controlled hosts.
- The `client_secret` travels in the `POST /token` body over plain HTTP.
- The ID token (a signed JWT containing the user's email + groups) returns over plain HTTP.

None of the above is acceptable even for staging with real user data. Executing this plan against raw HTTP is a bad idea — flag loudly and **do not merge** without the tunnel in place. Concurring with the original sketch: I concur with the pre-req §C1 blocker and found no safe way around it. (A local-only `OIDC_INSECURE_HTTP=1` dev flag is acceptable for the test-mode path in Task 5, but MUST default to off and MUST fail a boot-time self-check if set in any environment whose `OIDC_ISSUER_URL` starts with `http://` and is not `localhost` / `127.0.0.1`.)

Cutover order:
1. §C1 lands — `authentik.staging.arukai.example` terminates TLS via Cloudflare tunnel, cert is valid, `curl https://authentik.staging.arukai.example/-/health/live/` returns 200.
2. This plan executes — uses `OIDC_ISSUER_URL=https://authentik.staging.arukai.example/application/o/arukai-capital-call-backend/` (the exact slug depends on Task 1's Authentik app slug).
3. Cutover PR merges to main with `AUTH_MODE=dual` on staging.

### Schema migration — none

`User.role` already has the `admin | reviewer | approver` enum (from `backend/app/models.py` line 55). `User.password_hash` is `NOT NULL`; first-login OIDC user creation in Task 3 sets it to a random 24-byte hex string (same strategy the existing stubbed `oidc_callback` uses at `backend/app/routers/auth.py:293`). No Alembic revision needed.

If Authentik sends additional claims we want to persist per-user (e.g., `sub` from the IdP, MFA method, last-login IP), that is out of scope for this plan. Follow-up: add a `user_identity` table keyed on `(idp_issuer, idp_sub)` so an email change in Authentik doesn't orphan the local row.

### Breaking change surface — follow-up tasks

`/auth/login` keeps working in `AUTH_MODE=dual`, so existing integration tests, `docs/runbook-gce-staging.md`, and `docs/OPERATIONAL_RUNBOOK.md` continue to work. BUT once staging flips to `AUTH_MODE=oidc_only`:

- The bootstrap admin seeder (`backend/app/seed.py` if present, or whatever seeds `admin@arukai.example`) will still create the row but the password will never be usable.
- `docs/runbook-gce-staging.md` bootstrap section needs a new "first login via Authentik" path.
- `docs/OPERATIONAL_RUNBOOK.md` incident-response section referring to password reset needs to point at Authentik's password-reset flow instead.

Flagged as Task 7 (documentation follow-up) below; gated on the real cutover happening, so it ships after staging has run in `dual` for at least a week.

---

## Scope decomposition

| ID | Subsystem | Status |
|---|---|---|
| Task 1 | Authentik UI/API — provider + application + scope mapping for `arukai-capital-call-backend` | **Manual, documented** |
| Task 2 | Backend discovery + token exchange + ID-token signature verification via JWKS | **Code, TDD** |
| Task 3 | Role mapping (IdP groups → local `User.role`) + first-login user creation policy | **Code, TDD** |
| Task 4 | Session bridge — mint local JWT + `Session` row after OIDC callback succeeds | **Code, TDD** |
| Task 5 | Test suite survival — `OIDC_TEST_MODE=bypass` flag + new `test_oidc_real_flow.py` using mocked discovery doc | **Code, TDD** |
| Task 6 | `AUTH_MODE=oidc_only\|dual\|password_only` config gate | **Code, TDD** |
| Task 7 | Docs sweep — runbook-gce-staging + OPERATIONAL_RUNBOOK after cutover proven | **Doc-only, deferred** |

Sequential dependency: Task 1 must land before Task 2 (client_id/secret needed). Tasks 2-5 are a TDD chain on the same branch. Task 6 can run in parallel with Task 4-5 by a different subagent. Task 7 deferred to post-cutover.

### File structure

Created:
- `backend/app/oidc.py` — discovery + JWKS + token-exchange helper module (pulls the OIDC plumbing out of `routers/auth.py` so it's unit-testable)
- `backend/tests/test_oidc_real_flow.py` — new, covers discovery + code→token + ID-token signature verification against a mocked Authentik
- `backend/tests/test_oidc_role_mapping.py` — new, extends existing `test_oidc.py` with groups-claim → role mapping invariants
- `backend/tests/test_auth_mode_gate.py` — new, covers `AUTH_MODE` gating behavior
- `docs/authentik-oidc-setup.md` — step-by-step "how Task 1 was performed" (exact clicks + curl commands) so it's reproducible by someone else

Modified:
- `backend/app/routers/auth.py` — rewrite `oidc_callback` to call `oidc.exchange_code()` + `oidc.verify_id_token()`; honor `OIDC_TEST_MODE`; honor `AUTH_MODE`
- `backend/app/auth.py` — add boot-time self-check that rejects `http://` issuer URLs outside localhost
- `backend/tests/test_oidc.py` — stays as-is; the three "returns 501 when not configured" tests continue to guard the gate
- `backend/app/main.py` (or wherever routers are included) — ensure boot-time self-check runs on startup

Modified only if audit finds gaps:
- `frontend/src/...` login page — only if the OIDC "Sign in with Authentik" button is not already wired; audit in Task 1 Step 3 decides

---

## Task 1 — Authentik UI/API configuration

**Goal:** produce a working OIDC provider + application inside Authentik named `arukai-capital-call-backend`, scope `openid email profile`, redirect URI `https://api.staging.arukai.example/auth/oidc/callback`. Capture `client_id`, `client_secret`, issuer URL. This is a manual step but must be written down exactly so it's reproducible.

**Files:**
- Create: `docs/authentik-oidc-setup.md`
- No code changes in this task.

### Task 1.1 — Fetch Authentik admin credentials

- [ ] **Step 1: Pull the bootstrap admin password from the VM**

```bash
gcloud compute ssh arukai-staging --zone=us-central1-a \
  --command='sudo grep AUTHENTIK_BOOTSTRAP_PASSWORD /opt/arukai/staging.env'
```

Expected: a line like `AUTHENTIK_BOOTSTRAP_PASSWORD=<~30 chars>`. Save to a password manager. Do NOT paste into this doc.

- [ ] **Step 2: Log in to Authentik**

Open `https://authentik.staging.arukai.example/if/flow/initial-setup/` (post §C1) or `http://34.12.153.46:9000/if/flow/initial-setup/` (pre §C1 — read-only audit only, do NOT create the provider over plain HTTP).

Email: `admin@arukai.example`. Password: the value from Step 1.

- [ ] **Step 3: Audit existing objects**

In Authentik admin UI, visit `Applications → Providers` and `Applications → Applications`. Screenshot or write down whether any object named `arukai-capital-call-backend` already exists. If it does, reconcile manually before proceeding (rename or delete).

### Task 1.2 — Create the OIDC provider

- [ ] **Step 1: Create a new OIDC provider**

`Applications → Providers → Create → OAuth2/OpenID Provider`. Fields:
- Name: `arukai-capital-call-backend-provider`
- Authorization flow: `default-provider-authorization-explicit-consent` (Authentik ships this flow by default)
- Client type: `Confidential`
- Client ID: **leave auto-generated, capture the value**
- Client Secret: **leave auto-generated, capture the value**
- Redirect URIs / Origins (RegEx):
  - `https://api.staging.arukai.example/auth/oidc/callback`
  - (Optional second line for local dev, behind `OIDC_INSECURE_HTTP=1`): `http://localhost:8000/auth/oidc/callback`
- Signing Key: default (`authentik Self-signed Certificate`)
- Scopes: `openid`, `email`, `profile` (all three must be checked)

- [ ] **Step 2: Save and record**

After save, the Provider detail page shows:
- OpenID Configuration URL: `https://authentik.staging.arukai.example/application/o/<app-slug>/.well-known/openid-configuration`
- Client ID (shown masked; click to reveal)
- Client Secret (shown masked; click to reveal)

Record these three values in the password manager under `arukai/authentik-oidc/provider`. The OpenID Configuration URL is the `OIDC_ISSUER_URL` env var the backend will read (Note: Authentik's issuer string is the URL WITHOUT the `/.well-known/openid-configuration` suffix — the backend helper appends that itself, matching `routers/auth.py:208-209`).

### Task 1.3 — Create the Application

- [ ] **Step 1: Create the Authentik Application object**

`Applications → Applications → Create`. Fields:
- Name: `Arukai Capital Call Backend`
- Slug: `arukai-capital-call-backend`
- Provider: select `arukai-capital-call-backend-provider` from Task 1.2
- Policy engine mode: `any`
- UI settings → Launch URL: `https://app.staging.arukai.example/` (Next.js frontend)

- [ ] **Step 2: Create the three groups**

`Directory → Groups → Create`, three times:
- Name: `admin`
- Name: `reviewer`
- Name: `approver`

(These names MUST match the role enum in `backend/app/models.py:55` verbatim — `_map_oidc_role` at `routers/auth.py:189-196` matches against the set `{"admin", "reviewer", "approver"}`.)

- [ ] **Step 3: Create a test user in each group**

For each of the three groups, `Directory → Users → Create`:
- Username: `oidc-test-<role>@arukai.example`
- Name: `OIDC Test <Role>`
- Email: same as username
- Add to the matching group via the Groups column.

Set a password for each (via the "Reset password" admin action). Record in password manager.

### Task 1.4 — Write the setup doc

- [ ] **Step 1: Write `docs/authentik-oidc-setup.md`** capturing every click above, with a "Values captured" section at the bottom listing what was written down (without pasting secrets — reference the password-manager vault path).

- [ ] **Step 2: Commit**

```bash
cd ~/src/arukai-capital-call/.worktrees/por-158-operational-reality
git add docs/authentik-oidc-setup.md
git commit -m "docs(authentik): OIDC provider + application setup runbook (POR-158 B1)"
```

---

## Task 2 — Discovery, token exchange, ID-token signature verification

**Goal:** replace the hand-rolled `urllib.request` plumbing in `oidc_callback` with a tested helper module that uses `httpx` (already a dep) and `python-jose` (already a dep) for JWKS-backed ID-token signature verification.

**Files:**
- Create: `backend/app/oidc.py`
- Create: `backend/tests/test_oidc_real_flow.py`
- Modify: `backend/app/routers/auth.py`

### Task 2.1 — Write the failing test first

- [ ] **Step 1: Write `test_oidc_real_flow.py` with a mocked Authentik**

```python
# backend/tests/test_oidc_real_flow.py
"""POR-158 B1 — end-to-end OIDC flow against a mocked Authentik.

We mock three HTTP endpoints:
  1. GET  /.well-known/openid-configuration  (discovery)
  2. POST /token                              (code → access_token + id_token)
  3. GET  /jwks.uri                           (public keys for verifying id_token sig)

The id_token is signed with a test RSA key we control, so the signature
verification in oidc.verify_id_token() is exercised end-to-end.
"""
import json
import time
from unittest.mock import patch

import httpx
import pytest
from jose import jwk, jwt


TEST_ISSUER = "https://authentik.test/application/o/arukai-capital-call-backend/"
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_REDIRECT = "https://api.test/auth/oidc/callback"


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate one RSA keypair to sign test id_tokens."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_jwk = jwk.construct(
        priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        algorithm="RS256",
    ).to_dict()
    pub_jwk["kid"] = "test-key-1"
    pub_jwk["use"] = "sig"
    pub_jwk["alg"] = "RS256"
    return priv_pem, pub_jwk


def _sign_id_token(priv_pem, claims):
    return jwt.encode(claims, priv_pem, algorithm="RS256", headers={"kid": "test-key-1"})


@pytest.fixture
def mock_authentik(rsa_keypair, monkeypatch):
    priv_pem, pub_jwk = rsa_keypair
    discovery = {
        "issuer": TEST_ISSUER.rstrip("/"),
        "authorization_endpoint": f"{TEST_ISSUER}authorize/",
        "token_endpoint": f"{TEST_ISSUER}token/",
        "userinfo_endpoint": f"{TEST_ISSUER}userinfo/",
        "jwks_uri": f"{TEST_ISSUER}jwks/",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    jwks = {"keys": [pub_jwk]}
    id_token = _sign_id_token(priv_pem, {
        "iss": TEST_ISSUER.rstrip("/"),
        "sub": "authentik-user-uuid-1",
        "aud": TEST_CLIENT_ID,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "email": "alice@arukai.example",
        "groups": ["reviewer"],
    })

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json=discovery)
        if url == discovery["jwks_uri"]:
            return httpx.Response(200, json=jwks)
        if url == discovery["token_endpoint"]:
            return httpx.Response(200, json={
                "access_token": "access-token-abc",
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 300,
            })
        if url == discovery["userinfo_endpoint"]:
            return httpx.Response(200, json={
                "sub": "authentik-user-uuid-1",
                "email": "alice@arukai.example",
                "groups": ["reviewer"],
            })
        return httpx.Response(404, text=f"unmocked {url}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setenv("OIDC_ISSUER_URL", TEST_ISSUER.rstrip("/"))
    monkeypatch.setenv("OIDC_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", TEST_CLIENT_SECRET)
    monkeypatch.setenv("OIDC_REDIRECT_URI", TEST_REDIRECT)
    return transport


def test_discovery_loads(mock_authentik):
    from app.oidc import discover
    config = discover(transport=mock_authentik)
    assert config["token_endpoint"].endswith("/token/")
    assert config["jwks_uri"].endswith("/jwks/")


def test_exchange_code_returns_tokens(mock_authentik):
    from app.oidc import discover, exchange_code
    config = discover(transport=mock_authentik)
    tokens = exchange_code(config, code="dummy-auth-code", transport=mock_authentik)
    assert "access_token" in tokens
    assert "id_token" in tokens


def test_verify_id_token_signature_passes(mock_authentik):
    from app.oidc import discover, exchange_code, verify_id_token
    config = discover(transport=mock_authentik)
    tokens = exchange_code(config, code="dummy", transport=mock_authentik)
    claims = verify_id_token(config, tokens["id_token"], transport=mock_authentik)
    assert claims["email"] == "alice@arukai.example"
    assert claims["groups"] == ["reviewer"]


def test_verify_id_token_rejects_bad_signature(mock_authentik):
    """Flip one char in the JWT signature segment; must raise."""
    from app.oidc import discover, exchange_code, verify_id_token
    from jose.exceptions import JWSError
    config = discover(transport=mock_authentik)
    tokens = exchange_code(config, code="dummy", transport=mock_authentik)
    parts = tokens["id_token"].split(".")
    # Flip the last char of the signature
    tampered = parts[0] + "." + parts[1] + "." + parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
    with pytest.raises((JWSError, ValueError)):
        verify_id_token(config, tampered, transport=mock_authentik)
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd ~/src/arukai-capital-call/.worktrees/por-158-operational-reality/backend
source venv/bin/activate && SKIP_WINDMILL_TESTS=1 python -m pytest tests/test_oidc_real_flow.py -x -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.oidc'`. That's the right failure mode.

### Task 2.2 — Implement `backend/app/oidc.py`

- [ ] **Step 1: Create the module**

```python
# backend/app/oidc.py
"""OIDC helper — discovery, code-for-token exchange, id_token signature verification.

All HTTP I/O is funneled through httpx so tests can inject a MockTransport.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from jose import jwt
from jose.exceptions import JWSError, JWTError


class OIDCError(RuntimeError):
    pass


def _client(transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
    return httpx.Client(transport=transport, timeout=10.0)


def discover(transport: Optional[httpx.BaseTransport] = None) -> dict:
    issuer = os.environ["OIDC_ISSUER_URL"].rstrip("/")
    url = f"{issuer}/.well-known/openid-configuration"
    with _client(transport) as c:
        resp = c.get(url)
    if resp.status_code != 200:
        raise OIDCError(f"discovery failed: {resp.status_code}")
    return resp.json()


def exchange_code(config: dict, code: str, transport: Optional[httpx.BaseTransport] = None) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
        "client_id": os.environ["OIDC_CLIENT_ID"],
        "client_secret": os.environ["OIDC_CLIENT_SECRET"],
    }
    with _client(transport) as c:
        resp = c.post(config["token_endpoint"], data=data)
    if resp.status_code != 200:
        raise OIDCError(f"token exchange failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _fetch_jwks(config: dict, transport: Optional[httpx.BaseTransport] = None) -> dict:
    with _client(transport) as c:
        resp = c.get(config["jwks_uri"])
    if resp.status_code != 200:
        raise OIDCError(f"jwks fetch failed: {resp.status_code}")
    return resp.json()


def verify_id_token(config: dict, id_token: str, transport: Optional[httpx.BaseTransport] = None) -> dict:
    jwks = _fetch_jwks(config, transport=transport)
    audience = os.environ["OIDC_CLIENT_ID"]
    issuer = config.get("issuer") or os.environ["OIDC_ISSUER_URL"].rstrip("/")
    try:
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=config.get("id_token_signing_alg_values_supported", ["RS256"]),
            audience=audience,
            issuer=issuer,
        )
    except (JWSError, JWTError) as exc:
        raise OIDCError(f"id_token verification failed: {exc}") from exc
    return claims


def fetch_userinfo(config: dict, access_token: str, transport: Optional[httpx.BaseTransport] = None) -> dict:
    with _client(transport) as c:
        resp = c.get(
            config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise OIDCError(f"userinfo failed: {resp.status_code}")
    return resp.json()
```

- [ ] **Step 2: Re-run the test**

```bash
python -m pytest tests/test_oidc_real_flow.py -x -v
```

Expected: 4/4 pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/oidc.py backend/tests/test_oidc_real_flow.py
git commit -m "feat(oidc): httpx-based discovery + JWKS verification helper (POR-158 B1)"
```

### Task 2.3 — Swap `oidc_callback` to use the helper

- [ ] **Step 1: Rewrite `backend/app/routers/auth.py` `oidc_callback`**

Replace lines ~229-315 (the current `urllib.request`-based body) with calls to `oidc.discover()`, `oidc.exchange_code()`, `oidc.verify_id_token()`, and `oidc.fetch_userinfo()`. Keep the same HTTPException surface so the existing `test_oidc.py` 501/422 tests remain green.

Minimal target shape:

```python
from app import oidc

@router.post("/oidc/callback")
async def oidc_callback(body: OIDCCallbackRequest, db: AsyncSession = Depends(get_db)):
    if not _oidc_configured():
        raise HTTPException(status_code=501, detail="OIDC integration not configured")
    try:
        config = oidc.discover()
        tokens = oidc.exchange_code(config, code=body.code)
        id_claims = oidc.verify_id_token(config, tokens["id_token"])
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # ... role mapping + session bridge in Tasks 3-4
```

- [ ] **Step 2: Run the full auth suite**

```bash
python -m pytest tests/test_auth.py tests/test_oidc.py tests/test_oidc_real_flow.py -v
```

Expected: all green. The three original `test_oidc.py` "not configured" tests still pass because `_oidc_configured()` is unchanged.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth.py
git commit -m "refactor(auth): oidc_callback uses app.oidc helper (POR-158 B1)"
```

---

## Task 3 — Role mapping + first-login user creation

**Goal:** turn verified ID-token claims into a local `User` row with the right `role`, with a conservative first-login policy.

**Decision — policy (a) with allowlist:** create the user on first login if the IdP email's domain is in `OIDC_ALLOWED_EMAIL_DOMAINS` (comma-separated env, default `arukai.example`). Rejects random google-login drive-bys. `groups` claim from Authentik maps 1:1 to `User.role` using the existing `_map_oidc_role` helper.

**Files:**
- Create: `backend/tests/test_oidc_role_mapping.py`
- Modify: `backend/app/routers/auth.py`

### Task 3.1 — Write the failing test

- [ ] **Step 1: Write `test_oidc_role_mapping.py`**

```python
# backend/tests/test_oidc_role_mapping.py
"""POR-158 B1 — verified-claims → local User row.

Invariants:
  1. Email not in allowed domains → 403 (even if claims verify).
  2. Email in allowed domain, groups=["admin"] → user created with role=admin.
  3. Existing user, groups=["approver"] → role is updated to approver.
  4. Missing groups claim → role defaults to "reviewer".
"""
import pytest
from sqlalchemy import select


@pytest.fixture
def allowlist(monkeypatch):
    monkeypatch.setenv("OIDC_ALLOWED_EMAIL_DOMAINS", "arukai.example,trusted-partner.test")


def _fake_verified_claims(email, groups=None):
    return {
        "iss": "https://authentik.test",
        "sub": "authentik-uuid-1",
        "aud": "test-client-id",
        "email": email,
        "groups": groups or [],
    }


async def test_rejects_email_outside_allowlist(allowlist, db_session):
    from app.routers.auth import _apply_oidc_claims
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await _apply_oidc_claims(db_session, _fake_verified_claims("rando@attacker.com", ["admin"]))
    assert exc.value.status_code == 403


async def test_creates_user_on_first_login_with_admin_group(allowlist, db_session):
    from app.routers.auth import _apply_oidc_claims
    from app.models import User
    user = await _apply_oidc_claims(db_session, _fake_verified_claims("alice@arukai.example", ["admin"]))
    assert user.role == "admin"
    # Stored in DB
    row = (await db_session.execute(select(User).where(User.email == "alice@arukai.example"))).scalar_one()
    assert row.id == user.id


async def test_updates_role_on_existing_user(allowlist, db_session, seed_user):
    """seed_user fixture seeds bob@arukai.example with role='reviewer'."""
    from app.routers.auth import _apply_oidc_claims
    user = await _apply_oidc_claims(db_session, _fake_verified_claims(seed_user.email, ["approver"]))
    assert user.role == "approver"


async def test_default_role_when_groups_missing(allowlist, db_session):
    from app.routers.auth import _apply_oidc_claims
    user = await _apply_oidc_claims(db_session, _fake_verified_claims("carol@arukai.example"))
    assert user.role == "reviewer"
```

Note: `db_session` and `seed_user` are shared fixtures. If `seed_user` does not yet exist in `backend/tests/conftest.py`, add it in Step 2.

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_oidc_role_mapping.py -v
```

Expected: FAIL — `_apply_oidc_claims` does not exist yet.

### Task 3.2 — Implement `_apply_oidc_claims`

- [ ] **Step 1: Extract the user create/update block from `oidc_callback` into a helper**

In `backend/app/routers/auth.py`, add:

```python
async def _apply_oidc_claims(db: AsyncSession, claims: dict) -> User:
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="IdP did not return an email claim")

    allowed = {d.strip().lower() for d in os.environ.get("OIDC_ALLOWED_EMAIL_DOMAINS", "arukai.example").split(",") if d.strip()}
    domain = email.split("@", 1)[1].lower() if "@" in email else ""
    if domain not in allowed:
        raise HTTPException(status_code=403, detail=f"Email domain '{domain}' is not permitted")

    role = _map_oidc_role(claims)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, password_hash=hash_password(os.urandom(24).hex()), role=role)
        db.add(user)
        await db.flush()
    else:
        user.role = role
    return user
```

Then inside `oidc_callback`, after `id_claims = oidc.verify_id_token(...)`, call:

```python
user = await _apply_oidc_claims(db, id_claims)
```

- [ ] **Step 2: Run the role-mapping test + full auth suite**

```bash
python -m pytest tests/test_oidc_role_mapping.py tests/test_auth.py tests/test_oidc.py tests/test_oidc_real_flow.py -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/test_oidc_role_mapping.py
git commit -m "feat(oidc): role mapping + allowlisted first-login user creation (POR-158 B1)"
```

---

## Task 4 — Session bridge

**Goal:** after `_apply_oidc_claims` returns a `User`, mint the same local JWT + `Session` row that `/auth/login` mints today, so `get_current_user` keeps working downstream. No frontend or router-guard changes.

### Task 4.1 — Write the failing integration test

- [ ] **Step 1: Extend `test_oidc_real_flow.py`** with an integration test that wires the mocked Authentik all the way through to a successful `POST /auth/oidc/callback` request and asserts the response has `access_token` + `refresh_token`, and that a subsequent `GET /auth/me` using that token returns the right user.

```python
def test_oidc_callback_end_to_end(client, mock_authentik, monkeypatch):
    """Hit POST /auth/oidc/callback with a valid code and verify the returned
    access_token is usable on GET /auth/me."""
    # Patch the httpx transport inside app.oidc so the router uses our mock.
    monkeypatch.setattr("app.oidc._client", lambda transport=None: httpx.Client(transport=mock_authentik, timeout=10.0))
    monkeypatch.setenv("OIDC_ALLOWED_EMAIL_DOMAINS", "arukai.example")

    resp = client.post("/auth/oidc/callback", json={"code": "dummy-code"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "alice@arukai.example"
    assert body["role"] == "reviewer"
    assert body["access_token"]
    # Should include a refresh_token like /auth/login does
    assert body.get("refresh_token"), "session bridge must mint refresh_token same as /auth/login"

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@arukai.example"
```

- [ ] **Step 2: Run to confirm failure**

Expected: FAIL because the current `oidc_callback` does NOT mint a refresh_token (compare lines 301-315 of `routers/auth.py` — only mints access_token). That's exactly the gap this task closes.

### Task 4.2 — Mint refresh token + session in oidc_callback

- [ ] **Step 1: Update `oidc_callback`** to use the same `create_refresh_token` + `Session(refresh_token_hash=..., refresh_expires_at=...)` pattern as `/auth/login` (see `routers/auth.py:61-83`). Emit the `oidc_login` audit event (already present at `routers/auth.py:306-311`, keep it). Return the same `LoginResponse` shape as `/auth/login`.

- [ ] **Step 2: Run full auth suite**

```bash
python -m pytest tests/test_auth.py tests/test_oidc.py tests/test_oidc_real_flow.py tests/test_oidc_role_mapping.py -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/test_oidc_real_flow.py
git commit -m "feat(oidc): session bridge — mint local JWT + refresh + Session row (POR-158 B1)"
```

---

## Task 5 — Test-mode bypass

**Goal:** `test_auth.py` uses hardcoded bcrypt logins (`reviewer@arukai.example / reviewer123`, `admin@arukai.example / admin123`). These 8 tests must keep passing after cutover. Introduce `OIDC_TEST_MODE=bypass` that short-circuits discovery + token exchange + ID-token verification by accepting a crafted fake code (e.g., `test-code:alice@arukai.example:admin`) and fabricating claims directly.

**Rationale:** cleaner than leaving `/auth/login` perpetually on. It's a single env-var-gated code path, easy to verify OFF in prod (`AUTH_MODE=oidc_only` + `OIDC_TEST_MODE` unset). Document loudly.

### Task 5.1 — Write the failing test

- [ ] **Step 1: Add a test in `test_oidc_real_flow.py`**

```python
def test_oidc_test_mode_bypass(client, monkeypatch, db_session):
    """With OIDC_TEST_MODE=bypass, a well-formed fake code skips Authentik
    and fabricates claims directly. For local dev and CI only."""
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://dummy.test")  # _oidc_configured() still True
    monkeypatch.setenv("OIDC_CLIENT_ID", "x")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "y")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://dummy.test/cb")
    monkeypatch.setenv("OIDC_ALLOWED_EMAIL_DOMAINS", "arukai.example")
    monkeypatch.setenv("OIDC_TEST_MODE", "bypass")

    resp = client.post("/auth/oidc/callback", json={"code": "test-code:carol@arukai.example:approver"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "carol@arukai.example"
    assert body["role"] == "approver"
```

- [ ] **Step 2: Run to confirm failure**

Expected: FAIL — test mode not implemented.

### Task 5.2 — Implement the bypass

- [ ] **Step 1: Branch at the top of `oidc_callback`**

```python
if os.environ.get("OIDC_TEST_MODE") == "bypass":
    # Format: "test-code:<email>:<group>"
    try:
        _, email, group = body.code.split(":", 2)
    except ValueError:
        raise HTTPException(status_code=400, detail="OIDC_TEST_MODE=bypass expects test-code:<email>:<group>")
    id_claims = {"email": email, "groups": [group]}
else:
    try:
        config = oidc.discover()
        tokens = oidc.exchange_code(config, code=body.code)
        id_claims = oidc.verify_id_token(config, tokens["id_token"])
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

The rest of the handler is identical.

- [ ] **Step 2: Add boot-time safety check**

In `backend/app/auth.py` or `backend/app/main.py` startup hook:

```python
def _oidc_safety_check() -> None:
    issuer = os.environ.get("OIDC_ISSUER_URL", "")
    if issuer.startswith("http://") and "localhost" not in issuer and "127.0.0.1" not in issuer:
        raise RuntimeError(
            f"OIDC_ISSUER_URL={issuer!r} is plain HTTP against a non-loopback host — refusing to start. "
            "Set up TLS termination (see POR-158 §C1) before enabling OIDC."
        )
    if os.environ.get("OIDC_TEST_MODE") == "bypass" and os.environ.get("AUTH_MODE") == "oidc_only" and os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError("OIDC_TEST_MODE=bypass is forbidden in production.")
```

Call it from the FastAPI app's `startup` event.

- [ ] **Step 3: Run full suite**

```bash
python -m pytest tests/test_auth.py tests/test_oidc*.py -v
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/auth.py backend/app/auth.py backend/app/main.py
git commit -m "feat(oidc): OIDC_TEST_MODE=bypass for CI + HTTP-issuer safety check (POR-158 B1)"
```

---

## Task 6 — `AUTH_MODE` config gate

**Goal:** single env var `AUTH_MODE={password_only|dual|oidc_only}` decides whether `/auth/login` and `/auth/oidc/*` endpoints are active. Default `password_only` (unchanged behavior — nothing breaks if unset). Staging flips to `dual` once Task 5 ships. Production flips to `oidc_only` after first-pilot success.

**Files:**
- Create: `backend/tests/test_auth_mode_gate.py`
- Modify: `backend/app/routers/auth.py`

### Task 6.1 — Write the failing test

- [ ] **Step 1: Write `test_auth_mode_gate.py`**

```python
# backend/tests/test_auth_mode_gate.py
"""POR-158 B1 — AUTH_MODE gates which auth paths are reachable."""
import pytest


@pytest.mark.parametrize("mode,path,method,expected_status", [
    ("password_only", "/auth/login", "post", 200),  # existing behavior
    ("password_only", "/auth/oidc/authorize", "get", 404),
    ("password_only", "/auth/oidc/callback", "post", 404),
    ("dual", "/auth/login", "post", 200),
    ("dual", "/auth/oidc/authorize", "get", (307, 501)),  # 307 if configured, 501 if not
    ("oidc_only", "/auth/login", "post", 404),
    ("oidc_only", "/auth/oidc/authorize", "get", (307, 501)),
])
def test_auth_mode_gate(client, monkeypatch, mode, path, method, expected_status):
    monkeypatch.setenv("AUTH_MODE", mode)
    body = {"email": "reviewer@arukai.example", "password": "reviewer123"} if path == "/auth/login" else {"code": "x"}
    if method == "get":
        resp = client.get(path)
    else:
        resp = client.post(path, json=body)
    expected = expected_status if isinstance(expected_status, tuple) else (expected_status,)
    assert resp.status_code in expected, f"{mode} {path}: got {resp.status_code}"
```

- [ ] **Step 2: Run to confirm failure** — will FAIL because neither endpoint is gated.

### Task 6.2 — Implement the gate

- [ ] **Step 1: Add a dependency**

```python
def _require_auth_mode(*allowed: str):
    def _check():
        mode = os.environ.get("AUTH_MODE", "password_only")
        if mode not in allowed:
            raise HTTPException(status_code=404)
    return _check

# On /auth/login:
@router.post("/login", response_model=LoginResponse, dependencies=[Depends(_require_auth_mode("password_only", "dual"))])

# On /auth/oidc/authorize and /auth/oidc/callback:
dependencies=[Depends(_require_auth_mode("dual", "oidc_only"))]
```

- [ ] **Step 2: Run full suite + the new gate test**

```bash
python -m pytest tests/ -v -k 'auth or oidc'
```

Expected: all green. `test_auth.py`'s 8 existing tests still pass because `AUTH_MODE` defaults to `password_only` when unset.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/test_auth_mode_gate.py
git commit -m "feat(auth): AUTH_MODE gate (password_only|dual|oidc_only) (POR-158 B1)"
```

---

## Task 7 — Docs sweep (deferred, post-cutover)

**Goal:** once staging has run in `AUTH_MODE=dual` for a week with no incidents and the first pilot user has successfully logged in via Authentik, sweep the operational docs.

**Files:**
- Modify: `docs/runbook-gce-staging.md` — replace the password-reset section for backend users with an Authentik-password-reset flow. Add "how to create a new reviewer" steps.
- Modify: `docs/OPERATIONAL_RUNBOOK.md` — incident-response playbook: "revoke a compromised account" now means "deactivate the user in Authentik + revoke sessions in `/auth/logout` flow".
- Modify: `docs/ACCESS_CREDENTIALS.md` — remove the bcrypt-password seeding table for staging; link to Authentik admin instead.

Deferred because (a) it depends on real operational data from cutover, and (b) committing docs that describe an OIDC-only world before the cutover actually happens is a foot-gun for any operator reading the repo.

---

## Execution order

Sequential within this plan (all tasks touch the same branch):

1. Task 1 (manual Authentik config + doc) — blocks everything else. Can start once §C1 lands.
2. Task 2.1 → 2.2 → 2.3 (helper + rewire `oidc_callback`).
3. Task 3.1 → 3.2 (role mapping + allowlist).
4. Task 4.1 → 4.2 (session bridge).
5. Task 5.1 → 5.2 (test-mode bypass + boot safety check).
6. Task 6.1 → 6.2 (AUTH_MODE gate). Can be dispatched in parallel with Task 5 by a second subagent — no file-level conflict if Task 5 only touches the top of `oidc_callback` and Task 6 only adds a dependency.
7. Open `savnya/authentik-oidc-wiring` branch PR → review → merge with staging `AUTH_MODE=dual`.
8. Task 7 (docs sweep) — after ≥7 days of staging observation.

**Estimated effort:** ~5-7 hours of focused backend work for Tasks 2-6 (the Task 1 manual config adds ~45 min once §C1 is live). Does not count PR review window or the 7-day dual-mode soak.

---

## Self-review

### 1. Spec coverage

| POR-158 §B1 sketch item | Task |
|---|---|
| Authentik provider + application for `arukai-capital-call-backend` | Task 1 |
| Scope `openid email profile` | Task 1.2 |
| Redirect URI `https://api.staging.arukai.example/auth/oidc/callback` | Task 1.2 |
| Capture `client_id`, `client_secret`, issuer URL | Task 1.2 Step 2 |
| Complete `/auth/oidc/authorize` and `/auth/oidc/callback` stubs | Tasks 2.3, 4.2 |
| Fetch `.well-known/openid-configuration` | Task 2.2 (`oidc.discover`) |
| Code → access_token + id_token exchange | Task 2.2 (`oidc.exchange_code`) |
| Verify ID token signature via JWKS | Task 2.2 (`oidc.verify_id_token`) |
| IdP groups ("admin", "reviewer", "approver") → local User.role | Tasks 1.3 Step 2, 3.2 |
| Policy (a) first-login create + allowlist | Task 3.2 |
| Session bridge — local JWT + Session row | Task 4.2 |
| `OIDC_TEST_MODE=bypass` | Task 5.2 |
| `test_auth.py` + `test_oidc.py` survive the swap | Tasks 5, 6 (existing tests stay green under `AUTH_MODE=password_only` default) |
| `AUTH_MODE=oidc_only\|dual\|password_only` | Task 6 |
| Breaking change surface in `docs/runbook-gce-staging.md` + `docs/OPERATIONAL_RUNBOOK.md` | Task 7 (deferred) |
| Pre-req §C1 Cloudflare tunnel | Dependencies section at top |
| No migration expected | Dependencies section at top |

No gaps against the B1 sketch.

### 2. Placeholder scan

All tasks have concrete code blocks, exact file paths, exact commands. Exceptions with justification:
- Task 1 captures `client_id`, `client_secret`, issuer URL — these are runtime values the operator fills in and stores in a password manager; acceptable, documented inline.
- Task 1.2 Step 2 references `<app-slug>` in the OpenID Configuration URL — Authentik generates this from the Application name; known after Task 1.3 creates the Application. Documented as "the exact slug depends on Task 1's Authentik app slug".
- Task 5.2 Step 2 references `ENVIRONMENT=production` — assumes the project already has an `ENVIRONMENT` env var. If it doesn't, the safety-check condition should be weakened to `AUTH_MODE=oidc_only AND OIDC_TEST_MODE=bypass → fail`. Flagged for the executor to audit.

### 3. Type consistency

- The helper module exports three functions used across tests and the router: `discover() -> dict`, `exchange_code(config, code) -> dict`, `verify_id_token(config, id_token) -> dict` (claims). Signatures are consistent between `test_oidc_real_flow.py` and `backend/app/oidc.py`.
- `_apply_oidc_claims(db, claims) -> User` signature is used in Task 3.1 tests and Task 3.2 implementation — identical.
- `_map_oidc_role(claims) -> str` — already exists at `routers/auth.py:189-196`; Task 3 reuses it as-is.
- Env-var naming: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` match the existing `_oidc_configured()` check at `routers/auth.py:180-186`. New vars `OIDC_ALLOWED_EMAIL_DOMAINS`, `OIDC_TEST_MODE`, `AUTH_MODE` are documented in the task that introduces them.

One naming risk: `OIDC_TEST_MODE` is a string enum (`bypass`) but could grow (`replay`, `record`). Leaving as string rather than bool so it's extensible.

### 4. Ambiguity flagged for the executor

- **`ENVIRONMENT` env var** (Task 5.2 Step 2) — I didn't audit whether this variable exists in the codebase. The executor should check `backend/app/main.py` or `backend/app/config.py` and either reuse the existing pattern or drop the `ENVIRONMENT=production` condition from the safety check.
- **Bootstrap seeder location** (Task 7) — I referenced `backend/app/seed.py` speculatively. The executor should confirm where the `admin@arukai.example / admin123` + `reviewer@arukai.example / reviewer123` fixtures are created (likely a test conftest fixture, not a prod seeder) before rewriting docs.
- **`python-jose` + `cryptography` for the test RSA keypair** (Task 2.1) — `python-jose` is a dep but `cryptography` is a transitive one. If the test fails to import `cryptography.hazmat`, add `cryptography` explicitly to the test extras.
- **Frontend login-button wiring** (listed as "Modified only if audit finds gaps" in the File structure table) — I did not audit the Next.js login page in this plan. If the "Sign in with Authentik" button is missing, the executor should add a small task 6.5 for it; otherwise skip.

### 5. Concurrence with the §C1 pre-req blocker

I concur. Every OIDC step other than the `OIDC_TEST_MODE=bypass` path requires TLS on the Authentik endpoint — token-exchange alone sends `client_secret` in a POST body, and the ID-token response contains signed claims asserting a user's email and groups. Running any of that over plain HTTP on a public IP is a clear showstopper. The boot-time safety check in Task 5.2 Step 2 enforces this at runtime so the executor cannot accidentally ship an HTTP configuration. No safe workaround found.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-04-21-authentik-oidc-wiring.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task. Good fit because Task 1 is manual-only (Holden/Sawan in the Authentik UI) while Tasks 2-6 are pure backend TDD that Drummer can handle, and Task 6 can parallelize with Task 5 using `isolation:worktree`.
2. **Inline Execution** — `superpowers:executing-plans` in this session, checkpoint after each task.

Which approach?
