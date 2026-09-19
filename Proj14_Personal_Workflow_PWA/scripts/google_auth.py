"""One-time interactive helper: exchange an OAuth consent for a refresh token.

Run by hand, never from Task Scheduler. Google only returns a refresh token
when access_type=offline and prompt=consent are both sent, so this forces
both rather than relying on the default.

Security notes, both required by RFC 8252 for a native/desktop client:

* `state` is minted before the redirect and verified on the callback. Without
  it the loopback server accepts any GET carrying a `code`, so any page the
  browser visits while this is listening could feed us an attacker's code and
  we would print a refresh token for the attacker's account.
* PKCE binds the authorisation code to this specific process. An intercepted
  code is useless without the verifier, which never leaves this program.
"""
import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

PORT = 8731
REDIRECT_URI = f"http://127.0.0.1:{PORT}/"
SCOPE = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_received = {}
_expected_state = None


def _pkce_pair():
    """Return (verifier, S256 challenge), base64url without padding."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

        # Reject anything that did not originate from this run. Compared with
        # compare_digest so a mismatch cannot be probed by timing.
        got_state = params.get("state", "")
        if not secrets.compare_digest(got_state, _expected_state or ""):
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"State mismatch. Request rejected.")
            _received["error"] = "state_mismatch"
            return

        _received.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        done = "code" in _received
        message = "Authorised. Close this tab and return to the terminal." if done \
            else "No authorisation code received. Check the terminal."
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, *args):
        pass


def main():
    global _expected_state
    sys.stdout.reconfigure(encoding="utf-8")
    client_id = input("GOOGLE_CLIENT_ID: ").strip()
    client_secret = input("GOOGLE_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("both values are required")

    _expected_state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": _expected_state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    url = f"{AUTH_URL}?{params}"

    server = http.server.HTTPServer(("127.0.0.1", PORT), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print(f"\nOpening the consent screen. If nothing opens, visit:\n{url}\n")
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()

    if _received.get("error") == "state_mismatch":
        raise SystemExit(
            "the callback carried the wrong state and was rejected. "
            "Nothing was exchanged. Run this again."
        )
    if "code" not in _received:
        raise SystemExit("timed out waiting for the authorisation code")

    body = urllib.parse.urlencode({
        "code": _received["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    token = payload.get("refresh_token")
    if not token:
        raise SystemExit(
            "no refresh_token in the response. Revoke the app's access at "
            "https://myaccount.google.com/permissions and run this again."
        )
    print("\nPaste these into schedule-app/.env:\n")
    print(f"GOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={token}")


if __name__ == "__main__":
    main()
