# WordPress-ACF-Data-Pipeline ⚡
Idempotent REST API Ingestion & AI Enrichment Hook
A production-grade Data Engineering pipeline designed to automate the synchronization of scraped JSON datasets with a WordPress CMS. This project bridges the gap between raw data extraction and content management by utilizing the WordPress REST API and Advanced Custom Fields (ACF) for structured data storage.

## 🏗️ Architecture Overview
Managing large-scale data imports into WordPress often results in database bloat and duplicate records. This pipeline implements a Stateful Ingestion Strategy:

Deterministic Hashing (Idempotency): Generates a unique MD5 fingerprint for every record using hashlib, based on immutable business identifiers.

Pre-Flight Conflict Resolution: Queries the WordPress database via the REST API to check for existing hashes before execution.

AI Enrichment Layer (The Hook): Intercepts raw data to pass it through a simulated Gemini AI function for SEO optimization and summary generation.

Schema Mapping: Maps JSON keys directly to ACF Pro field names (business_address, contact_phone) to populate custom metadata without manual entry.

## 🛠️ Tech Stack
Component	Technology	Purpose
Language	Python 3.12	Core logic and data orchestration
CMS	WordPress (Pantheon Hosted)	Headless CMS for data storage
Data Schema	ACF (Advanced Custom Fields)	Structured custom field management
Security	Python-Dotenv	Professional environment variable management
Networking	Requests	Synchronous communication with WP REST API

## 🚀 Key Engineering Features
Idempotent Updates: Instead of simple "blind" posting, the script intelligently switches between POST (Insert) and PUT (Update) based on the presence of the record hash.

Production-Grade Security: Utilizes .env masking and .gitignore protocols to prevent the leakage of WordPress Application Passwords in version control.

REST API Reverse-Engineering: Bypasses standard UI-based imports in favor of direct API interaction, allowing for integration with CI/CD pipelines and automated scraping actors.

Staging Environment: Fully tested and deployed on a live Pantheon WebOps staging server.

## 📥 Installation & Usage
1. Clone the Repository
```bash
git clone https://github.com/Ainz47/Projects.git
cd Projects/Proj5_WordPress_ACF_REST_API
```
2. Configure Environment
Create a .env file based on the provided .env.example and add your WordPress Application Password.

```bash
WP_API_URL=https://your-site.pantheonsite.io/wp-json/wp/v2
WP_USERNAME=your_admin_user
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

3. Run the Pipeline
```bash
pip install requests python-dotenv
python wp_acf_importer.py
```

## 📊 Output
Successfully processed records appear in the WordPress dashboard with ACF fields automatically populated:

Title: Business Name

ACF Field: business_address

ACF Field: contact_phone

Meta: source_hash (Used for deduplication)