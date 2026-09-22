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
    # GHL's webhook body nests the mapped custom-data fields under
    # body.customData (see the GHL workflow's Webhook action "Custom Data"
    # section); company isn't in customData at all, it's GHL's own top-level
    # body.company_name. Confirmed against a real live execution payload
    # (execution 87) - $json.name etc. at this node is always undefined.
    return node("Call backend /qualify", "n8n-nodes-base.httpRequest", V["http"], [240, 0], {
        "method": "POST", "url": "", "sendBody": True, "specifyBody": "json",
        "jsonBody": (
            "={{ JSON.stringify({ name: $json.body.customData.name, email: $json.body.customData.email, "
            "company: $json.body.company_name, message: $json.body.customData.message, "
            "budget: $json.body.customData.budget, timeline: $json.body.customData.timeline }) }}"
        ),
        "options": {"response": {"response": {"responseFormat": "json"}}},
    })


def merge_result_node():
    # n8n's HTTP Request node replaces $json with the response body, so the
    # lead's own fields (contactId, opportunityId, name, email, company,
    # message, budget, timeline) don't survive the "Call backend /qualify"
    # hop on their own - every downstream node needs them, so pull them back
    # in explicitly from the trigger node by name rather than relying on
    # pass-through.
    lead_fields = {
        "contactId": "$('GHL lead webhook').item.json.body.customData.contactId",
        "opportunityId": "$('GHL lead webhook').item.json.body.customData.opportunityId",
        "name": "$('GHL lead webhook').item.json.body.customData.name",
        "email": "$('GHL lead webhook').item.json.body.customData.email",
        "company": "$('GHL lead webhook').item.json.body.company_name",
        "message": "$('GHL lead webhook').item.json.body.customData.message",
        "budget": "$('GHL lead webhook').item.json.body.customData.budget",
        "timeline": "$('GHL lead webhook').item.json.body.customData.timeline",
    }
    assignments = [
        {"id": f, "name": f, "value": f"={{{{ {expr} }}}}", "type": "string"}
        for f, expr in lead_fields.items()
    ]
    text_fields = ["tier", "reason", "suggested_reply"]
    assignments += [{"id": f, "name": f, "value": f"={{{{ $json.{f} }}}}", "type": "string"} for f in text_fields]
    assignments.append({"id": "score", "name": "score", "value": "={{ $json.score }}", "type": "number"})
    return node("Merge qualification onto lead", "n8n-nodes-base.set", V["set"], [480, 0], {
        "assignments": {"assignments": assignments},
        "options": {"includeOtherFields": True},
    })


GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
MERGE_NODE = "Merge qualification onto lead"


def ref(field):
    # Every node downstream of the Merge step is a chain of HTTP Request
    # calls to GHL; each one replaces $json with ITS OWN response, dropping
    # the merged lead fields (contactId, opportunityId, tier, score, ...)
    # that later nodes need. Reference the Merge node by name explicitly
    # instead of relying on $json pass-through, which silently breaks two
    # or more hops downstream (confirmed live: "Add tier tag" resolved
    # contactId to '' because its $json was the previous node's GHL contact
    # response, not the merged lead).
    return f"$('{MERGE_NODE}').item.json.{field}"
# httpTemplatedCustomAuth, not plain httpHeaderAuth: n8n rejects creating a
# NEW plain generic credential on this node (confirmed live via n8n-mcp
# validation against all 5 GHL write-back nodes). The credential's own
# template is {"headers":{"Authorization":"Bearer {{api_key}}"}}, token goes
# in its api_key field - see docs/ghl-build-steps.md step 5.
GHL_CREDENTIAL = {"httpTemplatedCustomAuth": "GHL Private Integration Token"}


def ghl_request_node(name, position, method, url_expr, json_body_expr):
    return node(name, "n8n-nodes-base.httpRequest", V["http"], position, {
        "method": method, "url": url_expr,
        "authentication": "genericCredentialType", "genericAuthType": "httpTemplatedCustomAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Version", "value": GHL_VERSION}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": json_body_expr,
        "options": {},
    }, credentials=GHL_CREDENTIAL)


def write_custom_fields_node(position):
    body = (
        "={{ JSON.stringify({ customFields: ["
        f"{{ id: '', fieldValue: String({ref('score')}) }}, "
        f"{{ id: '', fieldValue: {ref('reason')} }}, "
        f"{{ id: '', fieldValue: {ref('suggested_reply')} }} "
        "] }) }}"
    )
    return ghl_request_node(
        "Write score/reason/reply to GHL", position, "PUT",
        "=" + GHL_BASE + "/contacts/{{ " + ref("contactId") + " }}", body,
    )


def add_tier_tag_node(position):
    body = f"={{{{ JSON.stringify({{ tags: [{ref('tier')}] }}) }}}}"
    return ghl_request_node(
        "Add tier tag", position, "POST",
        "=" + GHL_BASE + "/contacts/{{ " + ref("contactId") + " }}/tags", body,
    )


def opportunity_lookup_node(position):
    # GHL's own webhook Custom Data sends opportunityId: '' for a contact even
    # though its opportunity already exists at send time (confirmed live via
    # the GHL API: the opportunity for the hot test contact existed seconds
    # after form submission, but executions 90-93 still saw an empty
    # opportunityId in the webhook payload - a GHL-side merge-field issue, not
    # an n8n bug). Rather than depend on that merge field resolving correctly,
    # look the opportunity up directly from GHL by contactId once tagging is
    # done, the same API call that confirmed the bug.
    # GHL's actual REST API (v2021-07-28) rejects camelCase contactId on this
    # endpoint with a 422 ("property contactId should not exist") - confirmed
    # live (execution 94). It wants snake_case contact_id, unlike the MCP
    # tool's own documented (camelCase) param name for the same operation.
    return node("Look up opportunity by contact", "n8n-nodes-base.httpRequest", V["http"], position, {
        "method": "GET", "url": GHL_BASE + "/opportunities/search",
        "authentication": "genericCredentialType", "genericAuthType": "httpTemplatedCustomAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Version", "value": GHL_VERSION}]},
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "contact_id", "value": "={{ " + ref("contactId") + " }}"},
            {"name": "location_id", "value": ""},
        ]},
        "options": {"response": {"response": {"responseFormat": "json"}}},
    }, credentials=GHL_CREDENTIAL)


OPPORTUNITY_LOOKUP_NODE = "Look up opportunity by contact"


def ref_opportunity():
    return f"$('{OPPORTUNITY_LOOKUP_NODE}').item.json.opportunities[0].id"


def move_stage_node(name, position):
    body = "={{ JSON.stringify({ pipelineStageId: '' }) }}"
    return ghl_request_node(
        name, position, "PUT",
        "=" + GHL_BASE + "/opportunities/{{ " + ref_opportunity() + " }}", body,
    )


def leadlog_node(position):
    # Same column shape as Proj16's Leads sheet (code/rows.js's SHEET_COLUMNS),
    # so Proj16's weekly-summary can summarize() this tab with no new code.
    columns = {
        "timestamp": "={{ $now.toISO() }}", "name": f"={{{{ {ref('name')} }}}}",
        "email": f"={{{{ {ref('email')} }}}}", "company": f"={{{{ {ref('company')} }}}}",
        "message": f"={{{{ {ref('message')} }}}}", "budget": f"={{{{ {ref('budget')} }}}}",
        "timeline": f"={{{{ {ref('timeline')} }}}}", "status": "accepted",
        "tier": f"={{{{ {ref('tier')} }}}}", "score": f"={{{{ {ref('score')} }}}}",
        "reason": f"={{{{ {ref('reason')} }}}}", "suggested_reply": f"={{{{ {ref('suggested_reply')} }}}}",
    }
    # This n8n version rejects mappingMode "defineBelow" without a matching
    # columns.schema entry per column (confirmed live: "Provide a
    # columns.schema array ... alongside columns.value" - Proj19's own
    # append node sidesteps this by using autoMapInputData instead, which
    # isn't an option here since columns.value's expressions pull from the
    # Merge node by name rather than from the item's own top-level fields).
    schema = [
        {"id": col, "displayName": col, "required": False, "defaultMatch": False,
         "display": True, "type": "string", "canBeUsedToMatch": True, "removed": False}
        for col in columns
    ]
    return node("Append lead log", "n8n-nodes-base.googleSheets", V["sheets"], position, {
        "operation": "append",
        "documentId": {"__rl": True, "mode": "url", "value": ""},
        "sheetName": {"__rl": True, "mode": "name", "value": "LeadLog"},
        "columns": {"mappingMode": "defineBelow", "value": columns, "matchingColumns": [], "schema": schema},
        "options": {"useAppend": True},
    }, credentials={"googleSheetsOAuth2Api": "Google Sheets account"})


def whatsapp_hot_alert_node(position):
    text = ("={{ 'Hot GHL lead (' + " + ref("score") + " + '/10): ' + " + ref("name") + " + ', ' "
            "+ (" + ref("company") + " || 'no company') + '. ' + " + ref("reason") + " }}")
    # A notification-channel failure (e.g. an expired WhatsApp/Meta token,
    # a known pre-existing issue on this instance - see Proj19 Plan 2)
    # shouldn't block the CRM write-back running in parallel from it.
    return node("WhatsApp hot lead alert", "n8n-nodes-base.whatsApp", V["whatsapp"], position, {
        "operation": "send", "phoneNumberId": "", "recipientPhoneNumber": "", "textBody": text,
    }, credentials={"whatsAppApi": "WhatsApp account"}, onError="continueRegularOutput")


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
        opportunity_lookup_node([1200, 0]),
        if_node("Is hot?", [1440, 0], f"={{{{ {ref('tier')} }}}}",
                {"type": "string", "operation": "equals"}, "hot"),
        move_stage_node("Move to Hot stage", [1680, -160]),
        if_node("Is warm?", [1680, 160], f"={{{{ {ref('tier')} }}}}",
                {"type": "string", "operation": "equals"}, "warm"),
        move_stage_node("Move to Warm stage", [1920, 80]),
        move_stage_node("Move to Cold stage", [1920, 240]),
        leadlog_node([1200, -320]),
        whatsapp_hot_alert_node([1920, -320]),
    ]
    edges = [
        ("GHL lead webhook", "Call backend /qualify", 0),
        ("Call backend /qualify", "Merge qualification onto lead", 0),
        ("Merge qualification onto lead", "Write score/reason/reply to GHL", 0),
        ("Write score/reason/reply to GHL", "Add tier tag", 0),
        ("Add tier tag", "Look up opportunity by contact", 0),
        ("Add tier tag", "Append lead log", 0),
        ("Look up opportunity by contact", "Is hot?", 0),
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
