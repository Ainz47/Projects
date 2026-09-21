"""Builds the n8n workflow export for the Shopify order to stock sync.

The JavaScript in each Code node is read from code/*.js (minus the test-only
exports block), so the logic the unit tests cover is the logic that ships.
Run: py tools/build_exports.py   (writes order-stock-sync.workflow.json)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = ROOT / "code"
EXPORT_MARKER = "// --- exports"
PLACEHOLDER_ID = "REPLACE_IN_UI"

SHOP = "jhurald05"
API_VERSION = "2026-07"
BASE_ID = "appXXXXXXXXXXXXXX"  # replaced with the real base id when the workflow is imported
REPO = "Ainz47/Projects"
WORKFLOW_FILE = "refresh-catalog.yml"

# typeVersion per node type. Confirm at the first import: n8n rejects a version it does not know.
V = {"code": 2, "if": 2.2, "schedule": 1.2, "http": 4.2, "sheets": 4.7, "gmail": 2.1}

STOCK_LOG_SHEET_NAME = "StockLog"

SHOPIFY_URL = f"https://{SHOP}.myshopify.com/admin/api/{API_VERSION}/graphql.json"
TOKEN_URL = f"https://{SHOP}.myshopify.com/admin/oauth/access_token"
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/Variants"
GITHUB_URL = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"


def js(*modules, tail):
    parts = []
    for name in modules:
        source = (CODE_DIR / name).read_text(encoding="utf-8")
        parts.append(source.split(EXPORT_MARKER)[0].rstrip())
    return "\n\n".join(parts + [tail]) + "\n"


def node(name, type_, version, position, parameters, credentials=None, **extra):
    n = {"parameters": parameters, "type": type_, "typeVersion": version,
         "position": position, "name": name}
    if credentials:
        n["credentials"] = {k: {"id": PLACEHOLDER_ID, "name": v} for k, v in credentials.items()}
    n.update(extra)
    return n


def wire(edges):
    """edges: (source, target, output_port) triples -> n8n connections dict."""
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


def code_node(name, position, source, **extra):
    return node(name, "n8n-nodes-base.code", V["code"], position, {"jsCode": source}, **extra)


def if_node(name, position, left):
    return node(name, "n8n-nodes-base.if", V["if"], position, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
            "conditions": [{"id": f"{name}-cond", "leftValue": left, "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
            "combinator": "and",
        },
        "options": {},
    })


def http_node(name, position, url, *, method="POST", cred_type=None, cred_name=None, headers=None, json_body=None, **extra):
    parameters = {"method": method, "url": url, "options": {}}
    if cred_type:
        parameters["authentication"] = "genericCredentialType"
        parameters["genericAuthType"] = cred_type
    if headers:
        parameters["sendHeaders"] = True
        parameters["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers.items()]}
    if json_body is not None:
        parameters["sendBody"] = True
        parameters["specifyBody"] = "json"
        parameters["jsonBody"] = json_body
    credentials = {cred_type: cred_name} if cred_type else None
    return node(name, "n8n-nodes-base.httpRequest", V["http"], position, parameters, credentials=credentials, **extra)


def sheets_node(name, position, operation, sheet_name, **extra):
    parameters = {
        "operation": operation,
        "documentId": {"__rl": True, "mode": "url", "value": ""},
        "sheetName": {"__rl": True, "mode": "name", "value": sheet_name},
        "options": {"useAppend": True} if operation == "append" else {},
    }
    if operation == "append":
        parameters["columns"] = {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []}
    return node(name, "n8n-nodes-base.googleSheets", V["sheets"], position, parameters,
                credentials={"googleSheetsOAuth2Api": "Google Sheets account"}, **extra)


def gmail_node(name, position, to_expr, subject_expr, message_expr):
    return node(name, "n8n-nodes-base.gmail", V["gmail"], position, {
        "resource": "message", "operation": "send",
        "sendTo": to_expr, "subject": subject_expr, "emailType": "text", "message": message_expr,
        "options": {},
    }, credentials={"gmailOAuth2": "Gmail account"})


SHOPIFY_HEADERS = {
    "X-Shopify-Access-Token": "={{ $('Shopify token').first().json.access_token }}",
    "Content-Type": "application/json",
}


def order_stock_sync():
    nodes = [
        node("Every 5 minutes", "n8n-nodes-base.scheduleTrigger", V["schedule"], [0, 0],
             {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}}),
        code_node("Plan orders query", [240, 0], js("plan_orders_query.js", "queries.js", tail=(
            "const cursor = $getWorkflowStaticData('global').cursor ?? null;\n"
            "const plan = planOrdersQuery(cursor, Date.now());\n"
            "return [{ json: { query: ORDERS_QUERY, variables: { first: plan.first, search: plan.search } } }];"))),
        http_node("Shopify token", [480, 0], TOKEN_URL,
                  cred_type="httpCustomAuth", cred_name="Shopify client credentials"),
        http_node("Shopify orders", [720, 0], SHOPIFY_URL, headers=SHOPIFY_HEADERS,
                  json_body="={{ JSON.stringify({ query: $('Plan orders query').first().json.query, variables: $('Plan orders query').first().json.variables }) }}"),
        code_node("Plan stock lookup", [960, 0], js("guards.js", "collect_skus.js", "lookups.js", "queries.js", tail=(
            "const body = $input.first().json;\n"
            "assertNoGraphqlErrors(body, 'Shopify orders');\n"
            "const skus = collectSkus(body.data.orders.nodes);\n"
            "return [{ json: { hasSkus: skus.length > 0, skus, query: STOCK_QUERY, variables: { search: skusSearch(skus) }, formula: airtableFormula(skus) } }];"))),
        if_node("Any SKUs?", [1200, 0], "={{ $json.hasSkus }}"),
        http_node("Shopify stock", [1440, -120], SHOPIFY_URL, headers=SHOPIFY_HEADERS,
                  json_body="={{ JSON.stringify({ query: $('Plan stock lookup').first().json.query, variables: $('Plan stock lookup').first().json.variables }) }}"),
        http_node("Airtable rows", [1680, -120], f"{AIRTABLE_URL}/listRecords",
                  cred_type="httpHeaderAuth", cred_name="Airtable token",
                  json_body="={{ JSON.stringify({ filterByFormula: $('Plan stock lookup').first().json.formula, fields: ['SKU', 'Stock'] }) }}"),
        code_node("Plan updates", [1920, -120], js("guards.js", "shopify_stock.js", "plan_updates.js", tail=(
            "const plan = $('Plan stock lookup').first().json;\n"
            "const stockBody = $('Shopify stock').first().json;\n"
            "assertNoGraphqlErrors(stockBody, 'Shopify stock');\n"
            "const air = $input.first().json;\n"
            "if (air.offset) throw new Error('Airtable returned more than one page of affected variants; this workflow does not paginate');\n"
            "const rows = (air.records ?? []).map((r) => ({ id: r.id, sku: r.fields.SKU, stock: r.fields.Stock ?? null }));\n"
            "const variants = stockBody.data.productVariants.nodes;\n"
            "const stock = {};\n"
            "for (const sku of plan.skus) stock[sku] = stockFromVariants(variants, sku);\n"
            "const result = planUpdates(plan.skus, stock, rows);\n"
            "return [{ json: { ...result, hasUpdates: result.updates.length > 0 } }];"))),
        if_node("Any updates?", [2160, -120], "={{ $json.hasUpdates }}"),
        code_node("Chunk updates", [2400, -240], js("plan_updates.js", tail=(
            "const { updates } = $('Plan updates').first().json;\n"
            "return chunkUpdates(updates, 10).map((records) => ({ json: { records: records.map((u) => ({ id: u.recordId, fields: { Stock: u.newStock } })) } }));"))),
        http_node("Airtable update", [2640, -240], AIRTABLE_URL, method="PATCH",
                  cred_type="httpHeaderAuth", cred_name="Airtable token",
                  json_body="={{ JSON.stringify({ records: $json.records }) }}"),
        http_node("Dispatch refresh", [2880, -240], GITHUB_URL,
                  cred_type="httpHeaderAuth", cred_name="GitHub Actions token",
                  headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                  json_body='={{ JSON.stringify({ ref: "main" }) }}', executeOnce=True),
        code_node("Expand stock log rows", [2640, -480], js("collect_skus.js", "stock_log_rows.js", tail=(
            "const { updates } = $('Plan updates').first().json;\n"
            "const orders = $('Shopify orders').first().json.data.orders.nodes;\n"
            "const rows = stockLogRows(updates, skuOrderNames(orders), 'n8n', new Date().toISOString());\n"
            "return rows.map((row) => ({ json: row }));"))),
        sheets_node("Append stock log", [2880, -480], "append", STOCK_LOG_SHEET_NAME),
        code_node("Advance cursor", [3120, 0], js("next_cursor.js", tail=(
            "const orders = $('Shopify orders').first().json.data.orders.nodes;\n"
            "const store = $getWorkflowStaticData('global');\n"
            "store.cursor = nextCursor(store.cursor ?? null, orders, Date.now());\n"
            "return [{ json: { cursor: store.cursor, orders: orders.length } }];")), executeOnce=True),
        # Webhook self-heal branch, parallel to the orders/stock branch, off "Shopify token".
        # Each of "Plan webhook check" and "Plan webhook create" owns its own query text, the
        # same way "Plan orders query" and "Plan stock lookup" do, so every HTTP node's body
        # reads either $json or a single named predecessor, with no exceptions.
        code_node("Plan webhook check", [720, 240], js("queries.js", tail=(
            "return [{ json: { query: WEBHOOKS_QUERY, variables: { topics: ['ORDERS_CREATE'] } } }];"))),
        http_node("List webhooks", [960, 240], SHOPIFY_URL, headers=SHOPIFY_HEADERS,
                  json_body='={{ JSON.stringify({ query: $json.query, variables: $json.variables }) }}'),
        code_node("Plan webhook ensure", [1200, 240], js("guards.js", "ensure_webhook.js", tail=(
            "assertNoGraphqlErrors($input.first().json, 'Shopify webhooks');\n"
            "const nodes = $input.first().json.data.webhookSubscriptions.nodes;\n"
            "const subscriptions = nodes.map((n) => ({ callbackUrl: n.endpoint && n.endpoint.callbackUrl }));\n"
            "const callbackUrl = $vars.MAKE_WEBHOOK_URL;\n"
            "return [{ json: { needsWebhook: needsWebhookRegistration(subscriptions, callbackUrl), callbackUrl } }];"))),
        if_node("Needs webhook?", [1440, 240], "={{ $json.needsWebhook }}"),
        code_node("Plan webhook create", [1680, 240], js("queries.js", tail=(
            "return [{ json: { query: WEBHOOK_CREATE_MUTATION, variables: { callbackUrl: $('Plan webhook ensure').first().json.callbackUrl } } }];"))),
        http_node("Create webhook", [1920, 240], SHOPIFY_URL, headers=SHOPIFY_HEADERS,
                  json_body='={{ JSON.stringify({ query: $json.query, variables: $json.variables }) }}'),
        code_node("Confirm webhook", [2160, 240], js("guards.js", tail=(
            "assertNoGraphqlErrors($json, 'Shopify webhook create');\n"
            "assertNoUserErrors($json.data.webhookSubscriptionCreate.userErrors, 'Shopify webhook create');\n"
            "return [{ json: {} }];"))),
        # Thank-you email branch, parallel to the stock branch, off "Shopify orders".
        code_node("Plan thank-yous", [960, 480], js("guards.js", "thanks.js", tail=(
            "const body = $('Shopify orders').first().json;\n"
            "assertNoGraphqlErrors(body, 'Shopify orders');\n"
            "const allowList = String($vars.THANK_YOU_ALLOW_LIST ?? '').split(',').map((s) => s.trim()).filter(Boolean);\n"
            "const plan = planThankYous(body.data.orders.nodes, allowList);\n"
            "return [{ json: { hasToSend: plan.send.length > 0, toSend: plan.send } }];"))),
        if_node("Any to thank?", [1200, 480], "={{ $json.hasToSend }}"),
        code_node("Expand thank-yous", [1440, 480], js("queries.js", "thanks.js", tail=(
            "const { toSend } = $('Plan thank-yous').first().json;\n"
            "return toSend.map((o) => {\n"
            "  const email = thankYouEmail(o.name);\n"
            "  return { json: { query: TAG_ORDER_MUTATION, variables: { id: o.orderId, tags: [THANK_YOU_TAG] }, email: o.email, subject: email.subject, text: email.text } };\n"
            "});"))),
        http_node("Tag order", [1680, 480], SHOPIFY_URL, headers=SHOPIFY_HEADERS,
                  json_body="={{ JSON.stringify({ query: $json.query, variables: $json.variables }) }}"),
        code_node("Confirm tag", [1920, 480], js("guards.js", tail=(
            "for (const item of $input.all()) {\n"
            "  assertNoGraphqlErrors(item.json, 'Shopify tag order');\n"
            "  assertNoUserErrors(item.json.data.tagsAdd.userErrors, 'Shopify tag order');\n"
            "}\n"
            "return $input.all();"))),
        gmail_node("Send email", [2160, 480],
                   "={{ $('Expand thank-yous').item.json.email }}",
                   "={{ $('Expand thank-yous').item.json.subject }}",
                   "={{ $('Expand thank-yous').item.json.text }}"),
    ]
    edges = [
        ("Every 5 minutes", "Plan orders query", 0), ("Plan orders query", "Shopify token", 0),
        ("Shopify token", "Shopify orders", 0), ("Shopify orders", "Plan stock lookup", 0),
        ("Plan stock lookup", "Any SKUs?", 0),
        ("Any SKUs?", "Shopify stock", 0), ("Any SKUs?", "Advance cursor", 1),
        ("Shopify stock", "Airtable rows", 0), ("Airtable rows", "Plan updates", 0),
        ("Plan updates", "Any updates?", 0),
        ("Any updates?", "Chunk updates", 0), ("Any updates?", "Expand stock log rows", 0),
        ("Any updates?", "Advance cursor", 1),
        ("Chunk updates", "Airtable update", 0), ("Airtable update", "Dispatch refresh", 0),
        ("Dispatch refresh", "Advance cursor", 0),
        ("Expand stock log rows", "Append stock log", 0), ("Append stock log", "Advance cursor", 0),
        ("Shopify token", "Plan webhook check", 0), ("Plan webhook check", "List webhooks", 0),
        ("List webhooks", "Plan webhook ensure", 0), ("Plan webhook ensure", "Needs webhook?", 0),
        ("Needs webhook?", "Plan webhook create", 0), ("Needs webhook?", "Advance cursor", 1),
        ("Plan webhook create", "Create webhook", 0), ("Create webhook", "Confirm webhook", 0),
        ("Confirm webhook", "Advance cursor", 0),
        ("Shopify orders", "Plan thank-yous", 0), ("Plan thank-yous", "Any to thank?", 0),
        ("Any to thank?", "Expand thank-yous", 0), ("Any to thank?", "Advance cursor", 1),
        ("Expand thank-yous", "Tag order", 0), ("Tag order", "Confirm tag", 0),
        ("Confirm tag", "Send email", 0), ("Send email", "Advance cursor", 0),
    ]
    return workflow("Order stock sync", nodes, edges)


def build():
    files = {"order-stock-sync.workflow.json": order_stock_sync()}
    return {name: json.dumps(wf, indent=2, ensure_ascii=False) + "\n" for name, wf in files.items()}


def main():
    for name, text in build().items():
        (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
