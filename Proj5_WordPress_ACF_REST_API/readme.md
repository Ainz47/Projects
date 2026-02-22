# ⚙️ CMS Data Pipeline: Apify JSON to WordPress ACF

### 📊 Project Architecture Demo
This repository demonstrates a robust, idempotent ETL (Extract, Transform, Load) pipeline. It takes scraped JSON payloads (e.g., from an Apify Actor) and safely injects them into a live WordPress staging environment hosted on Pantheon, mapping the data directly to Advanced Custom Fields (ACF Pro) via the WP REST API.

### 🏗️ Engineering Highlights
* **Idempotency (Duplicate Prevention):** The script generates a deterministic MD5 hash based on the raw business data. It queries the database before insertion to execute an `UPDATE` if it exists, or an `INSERT` if it is new, preventing database pollution on reruns.
* **Direct ACF Pro Mapping:** Bypasses heavy plugins like WP All Import by passing complex JSON schemas directly into the `acf` object payload via the REST API.
* **AI Enrichment Layer:** Features an extensible hook designed to pass raw scraped text to a Large Language Model (Gemini/OpenAI) for text cleanup and taxonomy classification *before* it touches the CMS.

### 🚀 Live Execution Log
Successfully tested against a live Pantheon WordPress staging server.
```text
--- Starting Pipeline for: Davao Central Tech Solutions ---
[LOG] Generated Unique Hash: 2dc8e44e2473b879c8c62ce57c4cc880
[AI] Enriching description via Gemini...
[*] Attempting real network call to Pantheon Staging...
[SUCCESS] Data live on site! Status: 201
````
