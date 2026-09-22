"""Builds the GHL lead router n8n workflow export.

Run: py tools/build_exports.py   (writes ghl-lead-router.workflow.json)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER_ID = "REPLACE_IN_UI"

V = {"webhook": 2, "http": 4.2, "set": 3.4, "if": 2.2, "sheets": 4.7, "whatsapp": 1.1}

# Shared with Proj16/Proj19 in the same local n8n instance (see README's
# "Cross-project links" section): Proj20 writes a LeadLog tab into the same
# spreadsheet Proj19 already writes StockLog to, so Proj16's weekly digest can
# read both. The document ID itself is left blank below, same as Proj16's own
# sheets_node() convention - it identifies a real account's spreadsheet, so it
# goes in at import time, never committed (see NoSecrets' google_doc_id check).
SHARED_ERROR_WORKFLOW_ID = "BHscSap9QKZQruIu"


def node(name, type_, version, position, parameters, credentials=None, **extra):
    n = {"parameters": parameters, "type": type_, "typeVersion": version,
         "position": position, "name": name}
    if credentials:
        n["credentials"] = {k: {"id": PLACEHOLDER_ID, "name": v} for k, v in credentials.items()}
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


def workflow(name, nodes, edges, extra_settings=None):
    settings = {"executionOrder": "v1"}
    if extra_settings:
        settings.update(extra_settings)
    return {"name": name, "nodes": nodes, "connections": wire(edges),
            "active": False, "settings": settings}


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


GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
GHL_CREDENTIAL = {"httpHeaderAuth": "GHL Private Integration Token"}


def ghl_request_node(name, position, method, url_expr, json_body_expr):
    return node(name, "n8n-nodes-base.httpRequest", V["http"], position, {
        "method": method, "url": url_expr,
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Version", "value": GHL_VERSION}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": json_body_expr,
        "options": {},
    }, credentials=GHL_CREDENTIAL)


def write_custom_fields_node(position):
    body = (
        "={{ JSON.stringify({ customFields: ["
        "{ id: '', fieldValue: String($json.score) }, "
        "{ id: '', fieldValue: $json.reason }, "
        "{ id: '', fieldValue: $json.suggested_reply } "
        "] }) }}"
    )
    return ghl_request_node(
        "Write score/reason/reply to GHL", position, "PUT",
        "=" + GHL_BASE + "/contacts/{{ $json.contactId }}", body,
    )


def add_tier_tag_node(position):
    body = "={{ JSON.stringify({ tags: [$json.tier] }) }}"
    return ghl_request_node(
        "Add tier tag", position, "POST",
        "=" + GHL_BASE + "/contacts/{{ $json.contactId }}/tags", body,
    )


def move_stage_node(name, position):
    body = "={{ JSON.stringify({ pipelineStageId: '' }) }}"
    return ghl_request_node(
        name, position, "PUT",
        "=" + GHL_BASE + "/opportunities/{{ $json.opportunityId }}", body,
    )


def leadlog_node(position):
    # Same column shape as Proj16's Leads sheet (code/rows.js's SHEET_COLUMNS),
    # so Proj16's weekly-summary can summarize() this tab with no new code.
    columns = {
        "timestamp": "={{ $now.toISO() }}", "name": "={{ $json.name }}",
        "email": "={{ $json.email }}", "company": "={{ $json.company }}",
        "message": "={{ $json.message }}", "budget": "={{ $json.budget }}",
        "timeline": "={{ $json.timeline }}", "status": "accepted",
        "tier": "={{ $json.tier }}", "score": "={{ $json.score }}",
        "reason": "={{ $json.reason }}", "suggested_reply": "={{ $json.suggested_reply }}",
    }
    return node("Append lead log", "n8n-nodes-base.googleSheets", V["sheets"], position, {
        "operation": "append",
        "documentId": {"__rl": True, "mode": "url", "value": ""},
        "sheetName": {"__rl": True, "mode": "name", "value": "LeadLog"},
        "columns": {"mappingMode": "defineBelow", "value": columns, "matchingColumns": [], "schema": []},
        "options": {"useAppend": True},
    }, credentials={"googleSheetsOAuth2Api": "Google Sheets account"})


def whatsapp_hot_alert_node(position):
    text = ("={{ 'Hot GHL lead (' + $json.score + '/10): ' + $json.name + ', ' "
            "+ ($json.company || 'no company') + '. ' + $json.reason }}")
    return node("WhatsApp hot lead alert", "n8n-nodes-base.whatsApp", V["whatsapp"], position, {
        "operation": "send", "phoneNumberId": "", "recipientPhoneNumber": "", "textBody": text,
    }, credentials={"whatsAppApi": "WhatsApp account"})


def if_node(name, position, left, operator, right=""):
    return node(name, "n8n-nodes-base.if", V["if"], position, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
            "conditions": [{"id": f"{name}-cond", "leftValue": left, "rightValue": right, "operator": operator}],
            "combinator": "and",
        },
        "options": {},
    })


def ghl_lead_router():
    nodes = [
        webhook_node(), qualify_request_node(), merge_result_node(),
        write_custom_fields_node([720, 0]),
        add_tier_tag_node([960, 0]),
        if_node("Is hot?", [1200, 0], "={{ $json.tier }}",
                {"type": "string", "operation": "equals"}, "hot"),
        move_stage_node("Move to Hot stage", [1440, -160]),
        if_node("Is warm?", [1440, 160], "={{ $json.tier }}",
                {"type": "string", "operation": "equals"}, "warm"),
        move_stage_node("Move to Warm stage", [1680, 80]),
        move_stage_node("Move to Cold stage", [1680, 240]),
        leadlog_node([1200, -320]),
        whatsapp_hot_alert_node([1680, -320]),
    ]
    edges = [
        ("GHL lead webhook", "Call backend /qualify", 0),
        ("Call backend /qualify", "Merge qualification onto lead", 0),
        ("Merge qualification onto lead", "Write score/reason/reply to GHL", 0),
        ("Write score/reason/reply to GHL", "Add tier tag", 0),
        ("Add tier tag", "Is hot?", 0),
        ("Add tier tag", "Append lead log", 0),
        ("Is hot?", "Move to Hot stage", 0),
        ("Is hot?", "WhatsApp hot lead alert", 0),
        ("Is hot?", "Is warm?", 1),
        ("Is warm?", "Move to Warm stage", 0),
        ("Is warm?", "Move to Cold stage", 1),
    ]
    return workflow("GHL lead router", nodes, edges,
                     extra_settings={"errorWorkflow": SHARED_ERROR_WORKFLOW_ID})


def build():
    files = {"ghl-lead-router.workflow.json": ghl_lead_router()}
    return {name: json.dumps(wf, indent=2, ensure_ascii=False) + "\n" for name, wf in files.items()}


def main():
    for name, text in build().items():
        (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
