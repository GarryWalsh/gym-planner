from __future__ import annotations

import os
import urllib.parse
import hmac
import hashlib
import json
import time
import base64
from typing import Optional, Dict, Any

import streamlit as st
import requests


def _get_secret(key: str) -> Optional[str]:
    """Safely get a secret key from Streamlit secrets, returning None if secrets.toml is missing
    or the key is absent. This avoids StreamlitSecretNotFoundError when no secrets file exists.
    """
    try:
        sec = getattr(st, "secrets", None)
        if not sec:
            return None
        try:
            # Access within its own try, since .get may trigger parsing
            return sec.get(key, None)  # type: ignore[no-any-return]
        except Exception:
            return None
    except Exception:
        return None


class AuthSettings:
    def __init__(self) -> None:
        self.domain: Optional[str] = os.environ.get("AUTH0_DOMAIN") or _get_secret("AUTH0_DOMAIN")
        self.client_id: Optional[str] = os.environ.get("AUTH0_CLIENT_ID") or _get_secret("AUTH0_CLIENT_ID")
        self.client_secret: Optional[str] = os.environ.get("AUTH0_CLIENT_SECRET") or _get_secret("AUTH0_CLIENT_SECRET")
        # Default callback to the same app base URL with / if not provided
        self.callback_url: Optional[str] = os.environ.get("AUTH0_CALLBACK_URL") or _get_secret("AUTH0_CALLBACK_URL")
        self.dev_password: Optional[str] = os.environ.get("DEV_LOGIN_PASSWORD") or _get_secret("DEV_LOGIN_PASSWORD")
        self.cookie_secret: Optional[str] = (
            os.environ.get("AUTH_COOKIE_SECRET")
            or _get_secret("AUTH_COOKIE_SECRET")
            or os.environ.get("AUTH0_CLIENT_SECRET")
            or _get_secret("AUTH0_CLIENT_SECRET")
            or os.environ.get("DEV_LOGIN_PASSWORD")
            or _get_secret("DEV_LOGIN_PASSWORD")
        )

    @property
    def auth0_enabled(self) -> bool:
        return bool(self.domain and self.client_id and self.client_secret and self.callback_url)


# ===== Cookie / Token helpers (signed, short-lived) =====

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_json(obj: Dict[str, Any]) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _jwt_sign(secret: str, header: Dict[str, Any], payload: Dict[str, Any]) -> str:
    signing_input = f"{_b64url_json(header)}.{_b64url_json(payload)}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{signing_input.decode('ascii')}.{_b64url(sig)}"


def _jwt_decode(secret: str, token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        sig = base64.urlsafe_b64decode(parts[2] + "==")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload_json = base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8")
        data = json.loads(payload_json)
        if "exp" in data and int(time.time()) > int(data["exp"]):
            return None
        return data
    except Exception:
        return None


def _issue_cookie_token(settings: AuthSettings, user: Dict[str, Any], ttl_seconds: int = 30 * 24 * 3600) -> Optional[str]:
    if not settings.cookie_secret:
        return None
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.get("sub"),
        "name": user.get("name"),
        "provider": user.get("provider", "unknown"),
        "iat": int(time.time()),
        "exp": int(time.time()) + int(ttl_seconds),
    }
    return _jwt_sign(settings.cookie_secret, header, payload)


def _set_cookie_js(name: str, value: str, max_age: int = 30 * 24 * 3600) -> None:
    # Set cookie for path=/; SameSite=Lax; Secure where available
    js = f"""
    <script>
      try {{
        var parts = [
          '{name}=' + encodeURIComponent('{value}'),
          'path=/',
          'max-age={max_age}',
          'samesite=Lax'
        ];
        if (window.location.protocol === 'https:') parts.push('secure');
        document.cookie = parts.join('; ');
      }} catch (e) {{ console.warn('cookie set failed', e); }}
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)


def _inject_cookie_to_query(name: str) -> None:
    # If cookie exists and no auth param, reload with ?auth=<token> so Python can read/verify it.
    js = f"""
    <script>
      try {{
        const qs = new URLSearchParams(window.location.search);
        if (!qs.has('auth')) {{
          const m = document.cookie.match(new RegExp('(?:^|; )' + '{name}'.replace(/([.$?*|{{}}\(\)\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
          if (m) {{
            const tok = decodeURIComponent(m[1]);
            const url = new URL(window.location.href);
            url.searchParams.set('auth', tok);
            window.location.replace(url.toString());
          }}
        }}
      }} catch (e) {{ console.warn('cookie->query failed', e); }}
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)


def _authenticate_via_query(settings: AuthSettings) -> bool:
    try:
        qp = st.query_params
        tok = qp.get("auth") if isinstance(qp.get("auth"), str) else (qp.get("auth", [None])[0] if qp else None)
        if tok and settings.cookie_secret:
            data = _jwt_decode(settings.cookie_secret, tok)
            if data and data.get("sub"):
                st.session_state["user"] = {
                    "sub": data.get("sub"),
                    "name": data.get("name") or "User",
                    "email": "",
                    "provider": data.get("provider") or "cookie",
                }
                # Clear the auth param to keep the URL clean
                st.query_params.clear()
                return True
    except Exception:
        pass
    return False


# ===== OAuth helpers (Auth0) and DEV login =====

def _auth0_login_button(settings: AuthSettings) -> None:
    auth_url = (
        f"https://{settings.domain}/authorize?" + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": settings.client_id or "",
                "redirect_uri": settings.callback_url or "",
                "scope": "openid profile email",
                "audience": None,
            },
            doseq=True,
        )
    )
    st.link_button("Sign in with Auth0 (Google, etc.)", auth_url, use_container_width=True)
    st.info("Use the button above to sign in. After login, you will be redirected back here.")


def _auth0_exchange_code(settings: AuthSettings, code: str) -> Optional[dict]:
    token_url = f"https://{settings.domain}/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "code": code,
        "redirect_uri": settings.callback_url,
    }
    try:
        resp = requests.post(token_url, data=data, timeout=15)
        resp.raise_for_status()
        token = resp.json()
    except Exception:
        return None
    access_token = token.get("access_token")
    if not access_token:
        return None
    try:
        userinfo_url = f"https://{settings.domain}/userinfo"
        r2 = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
        r2.raise_for_status()
        userinfo = r2.json()
        return {
            "sub": userinfo.get("sub"),
            "name": userinfo.get("name") or userinfo.get("nickname") or "User",
            "email": userinfo.get("email") or "",
            "provider": "auth0",
        }
    except Exception:
        return None


def _dev_login(settings: AuthSettings) -> Optional[dict]:
    st.write("Developer login (temporary)")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Sign in", type="primary"):
        expected = settings.dev_password or ""
        if expected and pw == expected:
            return {"sub": "dev:user", "name": "Developer", "email": "dev@example.com", "provider": "dev"}
        st.error("Invalid password.")
    return None

# ===== Main flow =====

def _after_login_success(settings: AuthSettings, user: Dict[str, Any]) -> None:
    st.session_state["user"] = user
    tok = _issue_cookie_token(settings, user)
    if tok:
        _set_cookie_js("gp_auth", tok)
    st.query_params.clear()  # clear any code/auth leftovers
    st.rerun()


def require_login() -> None:
    """Gate the entire app behind authentication.
    If Auth0 is configured, use OAuth Code Flow. Otherwise, use a DEV password gate.
    On success, st.session_state["user"] is set; otherwise the app halts.
    Also supports a signed cookie (`gp_auth`) so returning users are auto-signed in.
    """
    # Already signed in
    if "user" in st.session_state and st.session_state["user"]:
        return

    settings = AuthSettings()

    # Try cookie via query param first (silent auth)
    if _authenticate_via_query(settings):
        return

    # If not signed in, try to promote cookie -> query on the client
    _inject_cookie_to_query("gp_auth")

    st.markdown("## 🔒 Sign in to continue")

    if settings.auth0_enabled:
        # Handle OAuth redirect callback
        qp = st.query_params
        code = qp.get("code") if isinstance(qp.get("code"), str) else (qp.get("code", [None])[0] if qp else None)
        if code:
            st.caption("Completing sign-in…")
            user = _auth0_exchange_code(settings, code)
            if user:
                _after_login_success(settings, user)
            else:
                st.error("Sign-in failed. Please try again.")
                _auth0_login_button(settings)
                st.stop()
        else:
            _auth0_login_button(settings)
            st.stop()
    else:
        # DEV fallback
        user = _dev_login(settings)
        if user:
            _after_login_success(settings, user)
        else:
            st.stop()
