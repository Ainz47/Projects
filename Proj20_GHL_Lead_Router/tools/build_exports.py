"""Builds the GHL lead router n8n workflow export.

Run: py tools/build_exports.py   (writes ghl-lead-router.workflow.json)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

V = {"webhook": 2, "http": 4.2, "set": 3.4}


def node(name, type_, version, position, parameters, **extra):
    n = {"parameters": parameters, "type": type_, "typeVersion": version,
         "position": position, "name": name}
    n.update(extra)
    return n


def wire(edges):
    out = {}
    for source, target, port in edges:
        ports = out.setdefault(source, {"main": []})["main"]
        while len(ports) <= port:
            ports.append([])
        ports[port].append({"node": target, "type": "main", "index": 0})
    return out


def workflow(name, nodes, edges):
    return {"name": name, "nodes": nodes, "connections": wire(edges),
            "active": False, "settings": {"executionOrder": "v1"}}


def webhook_node():
    return node("GHL lead webhook", "n8n-nodes-base.webhook", V["webhook"], [0, 0], {
        "httpMethod": "POST", "path": "ghl-lead-router", "responseMode": "onReceived", "options": {},
    }, webhookId="ghl-lead-router")


def qualify_request_node():
    return node("Call backend /qualify", "n8n-nodes-base.httpRequest", V["http"], [240, 0], {
        "method": "POST", "url": "", "sendBody": True, "specifyBody": "json",
        "jsonBody": (
            "={{ JSON.stringify({ name: $json.name, email: $json.email, company: $json.company, "
            "message: $json.message, budget: $json.budget, timeline: $json.timeline }) }}"
        ),
        "options": {"response": {"response": {"responseFormat": "json"}}},
    })


def merge_result_node():
    text_fields = ["tier", "reason", "suggested_reply"]
    assignments = [{"id": f, "name": f, "value": f"={{{{ $json.{f} }}}}", "type": "string"} for f in text_fields]
    assignments.append({"id": "score", "name": "score", "value": "={{ $json.score }}", "type": "number"})
    return node("Merge qualification onto lead", "n8n-nodes-base.set", V["set"], [480, 0], {
        "assignments": {"assignments": assignments},
        "options": {"includeOtherFields": True},
    })


def ghl_lead_router():
    nodes = [webhook_node(), qualify_request_node(), merge_result_node()]
    edges = [
        ("GHL lead webhook", "Call backend /qualify", 0),
        ("Call backend /qualify", "Merge qualification onto lead", 0),
    ]
    return workflow("GHL lead router", nodes, edges)


def build():
    files = {"ghl-lead-router.workflow.json": ghl_lead_router()}
    return {name: json.dumps(wf, indent=2, ensure_ascii=False) + "\n" for name, wf in files.items()}


def main():
    for name, text in build().items():
        (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
