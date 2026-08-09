# Setting up the WordPress MCP on a new site

Step-by-step process for wiring Claude Code's WordPress MCP server up to a
**fresh** WordPress install (e.g. moving off `containaftermath.s6-tastewp.com`
onto a different TasteWP site or a real production site). Follow this exactly
— every step here exists because skipping it caused a real, working failure
during initial setup.

## Prerequisites

- WordPress admin login (username + password) — **not** an Application
  Password. You need real admin access to upload plugins via the dashboard.
- Astra theme is assumed (the abilities plugin doesn't require it, but the CSS
  fixes referenced elsewhere in this project do).

## Step 1 — Create a WordPress Application Password

1. Log into `wp-admin` → **Users → Profile** (your own user, must be an
   Administrator).
2. Scroll to **Application Passwords** → enter a name (e.g. `claude-mcp`) →
   **Add New Application Password**.
3. Copy the generated password immediately (format: `xxxx xxxx xxxx xxxx xxxx
   xxxx`). This is **not** your login password — it's a separate token used
   only for REST API / Basic Auth.

> **Gotcha:** The Application Password does *not* work on the `/wp-login.php`
> form. If you need to log in via a browser (e.g. to upload a plugin), you
> need the real account password.

## Step 2 — Install the official `mcp-adapter` plugin

This is the WordPress.org plugin that bridges the **Abilities API** to MCP.
As of this writing it has no pre-built release ZIP on wordpress.org, so it
must be built from source.

1. Clone/download `https://github.com/WordPress/mcp-adapter` (use the
   `trunk` branch).
2. It's a Composer project — run `composer install --no-dev` inside it to
   pull production dependencies.
   - If PHP/Composer aren't available locally: install plain PHP from
     `windows.php.net` (the `winget` PHP package is often stripped of the
     `openssl`/`zip` extensions needed by Composer — enable both in
     `php.ini`), then install Composer via `php composer-setup.php`.
3. Zip the resulting plugin folder (must be named `mcp-adapter/` at the zip
   root, containing `mcp-adapter.php` at top level).
4. In `wp-admin` → **Plugins → Add Plugin → Upload Plugin**, upload the zip,
   install, then **Activate**.
5. Verify it's working:
   ```
   GET https://<site>/wp-json/mcp/mcp-adapter-default-server
   ```
   should return `{"code":"rest_forbidden",...}` (401) — that confirms the
   route exists and is auth-gated, which is correct.

## Step 3 — Install the `rr-wp-abilities` companion plugin

`mcp-adapter` only *bridges* abilities — it ships with zero abilities of its
own beyond a couple of read-only `core/*` diagnostics. Without a plugin that
registers abilities, `mcp-adapter-discover-abilities` will always return
`{"abilities":[]}` and there is nothing useful to call.

This project ships exactly that plugin: **`rr-wp-abilities/`** at the repo
root (synced to both `submission_repo` and `final_package`). It registers:

| Ability | Purpose |
|---|---|
| `rr/create-page` | Create a WP page from Gutenberg block markup. Auto-applies `site-post-title: disabled` + `_astra-site-sidebar-layout: no-sidebar` meta. |
| `rr/get-page` | Read back a page's raw block markup (`content.raw`) — used to inspect real live pages before converting them. |
| `rr/update-page` | Update an existing page's content/title. |
| `rr/list-pages` | List all pages with id/slug/status/url. |

To install on a new site:

1. Zip the `rr-wp-abilities/` folder (`Compress-Archive -Path rr-wp-abilities
   -DestinationPath rr-wp-abilities.zip`).
2. Upload via **Plugins → Add Plugin → Upload Plugin**, same as Step 2.
3. **Activate.**
4. No configuration needed — abilities self-register via the
   `wp_abilities_api_init` / `wp_abilities_api_categories_init` hooks as soon
   as the plugin is active.

### If you need to register new abilities later

The two hooks and the exact required ability schema (this caused a real bug —
abilities silently fail to register if any required key is missing):

```php
add_action( 'wp_abilities_api_categories_init', function () {
	wp_register_ability_category( 'my-category', array(
		'label'       => 'My Category',
		'description' => 'What abilities in this category do.',
	) );
} );

add_action( 'wp_abilities_api_init', function () {
	wp_register_ability( 'my-plugin/my-ability', array(
		'label'               => 'Human readable name',
		'description'         => 'What it does.',
		'category'            => 'my-category',   // REQUIRED — must reference a
		                                            // category registered above.
		                                            // Lowercase + hyphens only.
		'input_schema'         => array( 'type' => 'object', 'properties' => array(/*...*/) ),
		'output_schema'        => array(),          // REQUIRED, can be empty array.
		'execute_callback'     => function ( array $input ) { /* ... */ },
		'permission_callback'  => function () { return current_user_can( 'edit_pages' ); },
		'meta'                 => array( 'mcp' => array( 'public' => true ) ), // REQUIRED
		                                            // for the mcp-adapter to expose it.
	) );
} );
```

`wp_register_ability()` returns `null` silently on failure — there is no
exception, no warning. If an ability doesn't show up in
`mcp-adapter-discover-abilities`, the first thing to check is a missing
`category` or `output_schema` key.

## Step 4 — Configure `.mcp.json`

```json
{
  "mcpServers": {
    "wordpress": {
      "command": "npx",
      "args": ["-y", "@automattic/mcp-wordpress-remote"],
      "env": {
        "WP_API_URL": "https://<site>/wp-json/mcp/mcp-adapter-default-server",
        "WP_API_USERNAME": "<wp-username>",
        "WP_API_PASSWORD": "<application-password-from-step-1>",
        "OAUTH_ENABLED": "false"
      }
    }
  }
}
```

**This exact env var naming is critical** — getting it wrong is what broke
the connection the first time and took real debugging effort to find:

| ❌ Wrong (silently does nothing) | ✅ Correct |
|---|---|
| `WP_USERNAME` | `WP_API_USERNAME` |
| `WP_APP_PASSWORD` | `WP_API_PASSWORD` |
| *(omitted)* | `OAUTH_ENABLED: "false"` |

Without `OAUTH_ENABLED: "false"`, the package defaults to OAuth 2.1 — it
tries to open a browser for authorization. In a headless MCP server context
there's no browser, so it just hangs until connection timeout, and Claude
Code reports the server as **"Connection Failed"** with no further detail.

Add `.mcp.json` to `.gitignore` — it contains a credential.

## Step 5 — Install Node package globally (recommended)

`npx -y @automattic/mcp-wordpress-remote` re-resolves/downloads the package
on every MCP server launch unless it's cached. Install it globally once so
startup is fast and reliable:

```
npm install -g @automattic/mcp-wordpress-remote
```

## Step 6 — Restart Claude Code / reload MCP servers

After editing `.mcp.json`, the running session won't pick up the change —
restart Claude Code (or use `/mcp` to check status). Once connected, three
tools become available:

- `mcp__wordpress__mcp-adapter-discover-abilities`
- `mcp__wordpress__mcp-adapter-get-ability-info`
- `mcp__wordpress__mcp-adapter-execute-ability`

Confirm it's working:
```
mcp-adapter-discover-abilities  →  should list rr/create-page, rr/get-page, rr/update-page, rr/list-pages
```

## Quick diagnostic checklist (if it's not connecting)

1. Hit `GET /wp-json/mcp/mcp-adapter-default-server` unauthenticated — expect
   401 `rest_forbidden`, not 404. A 404 means `mcp-adapter` isn't active.
2. Verify the Application Password works at all:
   ```
   GET /wp-json/wp/v2/users/me   with Authorization: Basic base64(user:app-password)
   ```
   should return 200 with your user info.
3. Check `.mcp.json` env var names match exactly what's in Step 4's table.
4. Check `mcp-adapter-discover-abilities` returns a non-empty list — if
   empty, `rr-wp-abilities` isn't installed/active on this site.
5. **Don't test any of this from inside a Playwright browser tab that's
   logged into wp-admin** — the logged-in cookie session interferes with
   Basic Auth and produces misleading `401`/`rest_not_logged_in` errors that
   have nothing to do with the actual credentials. Test with a clean HTTP
   client (PowerShell `Invoke-WebRequest`, curl, etc.) instead.
