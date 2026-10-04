"""Call an EMCP tool from a script, through the same WordPress MCP endpoint the
pinned EMCP proxy uses (/wp-json/mcp/emcp-tools-server, basic auth, Mcp-Session-Id).

Used for payloads too big to paste through a chat tool call, e.g. pushing the
generated stylesheet into the header template:

  py emcp_call.py push-css          # tm-css.min.html -> header template style widget
  py emcp_call.py push-a11y         # a11y_fixes.html -> header template script widget
  py emcp_call.py tools <filter>    # list tool names containing <filter>
"""
import json
import sys
from pathlib import Path

from wp_api import BASE, SESSION

HERE = Path(__file__).parent
ENDPOINT = f"{BASE}/wp-json/mcp/emcp-tools-server"
HEADER_POST, CSS_WIDGET = 176, "40a983b"  # Trailmark header template, tm-css html widget
A11Y_WIDGET = "4ec6148"  # same template, a11y fixes script widget


class Mcp:
    def __init__(self):
        self.sid = None
        self.n = 0
        init = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "trailmark-script", "version": "1"}})
        self.version = init.get("result", {}).get("protocolVersion")
        self.rpc("notifications/initialized", notify=True)

    def rpc(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        headers = {"Accept": "application/json"}
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        r = SESSION.post(ENDPOINT, json=msg, headers=headers, timeout=120)
        self.sid = r.headers.get("mcp-session-id", self.sid)
        if notify:
            return None
        r.raise_for_status()
        return r.json()

    def call(self, tool, args):
        res = self.rpc("tools/call", {"name": tool, "arguments": args})
        if "error" in res:
            raise SystemExit(f"{tool}: {res['error']}")
        result = res["result"]
        text = result["content"][0]["text"] if result.get("content") else json.dumps(result)
        if result.get("isError"):
            raise SystemExit(f"{tool} failed: {text[:400]}")
        return text


def main():
    cmd = sys.argv[1]
    m = Mcp()
    if cmd == "tools":
        flt = sys.argv[2] if len(sys.argv) > 2 else ""
        names = [t["name"] for t in m.rpc("tools/list")["result"]["tools"]]
        print([n for n in names if flt in n])
    elif cmd == "push-css":
        html = (HERE / "tm-css.min.html").read_text(encoding="utf-8")
        out = m.call("emcp-tools-update-element",
                     {"post_id": HEADER_POST, "element_id": CSS_WIDGET, "settings": {"html": html}})
        print(out[:200], f"| pushed {len(html)} bytes")
    elif cmd == "push-a11y":
        html = (HERE / "a11y_fixes.html").read_text(encoding="utf-8")
        out = m.call("emcp-tools-update-element",
                     {"post_id": HEADER_POST, "element_id": A11Y_WIDGET, "settings": {"html": html}})
        print(out[:200], f"| pushed {len(html)} bytes")


if __name__ == "__main__":
    main()
