# Rank and Rent SEO Automation Pipeline

End-to-end Python automation system for bulk-generating SEO-optimized local content with AI and publishing to WordPress at scale. Designed for the "rank and rent" business model where service-based landing pages are automatically created, ranked, and monetized through lead generation.

## Overview

This pipeline orchestrates a three-stage workflow:

1. **Content Generation**: Reads target service/city combinations from a CSV fleet file and generates unique, SEO-optimized content using Google Gemini with structured JSON validation
2. **Transformation & Cleanup**: Normalizes HTML, injects location-specific landmarks, validates required fields, and prepares payloads for WordPress
3. **Publishing**: Deploys draft pages to WordPress via REST API with hierarchical organization (parent category → child location pages) and full audit trail logging

## Key Features

- **Scalable batch processing**: Load unlimited service/city combinations from CSV
- **AI-powered content generation**: Gemini integration with fallback model support and strict JSON enforcement
- **Location intelligence**: Validates local landmark references and geographic context
- **WordPress automation**: Creates hierarchical page structures with Application Password authentication
- **Audit trail**: Timestamped logs, run summaries, and raw JSON artifacts for compliance and debugging
- **Error handling**: Validates all JSON output before publishing; logs failures separately for review
- **Production-ready**: Environment-based configuration, dependency management, and containerizable design

## Architecture

```
data/source_fleet.csv
    ↓
pipeline_processor.py (AI generation)
    ↓
transformations.py (SEO cleanup & validation)
    ↓
wp_importer.py (WordPress REST API publish)
    ↓
logs/ (audit trail & artifacts)
```

### Core Components

| Module | Responsibility |
|--------|----------------|
| `run_pipeline.py` | Orchestrator: reads CSV, calls processors, manages state |
| `pipeline_processor.py` | Gemini API integration, JSON parsing, fallback model handling, validation |
| `transformations.py` | HTML cleanup, SEO checks, internal link preparation, WordPress payload building |
| `wp_importer.py` | WordPress REST API authentication, page hierarchy creation, upsert logic |
| `gemini_diagnostics.py` | Model availability checks and API connectivity testing |

## Installation

1. **Install dependencies:**
   ```powershell
   python -m pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```powershell
   copy .env.example .env
   ```
   
   Set required variables:
   - `GEMINI_API_KEY` - Google Gemini API credentials
   - `WP_URL` - WordPress site URL
   - `WP_USERNAME` - WordPress account username
   - `WP_APP_PASSWORD` - WordPress Application Password

## Usage

```powershell
python src\run_pipeline.py
```

The pipeline will:
1. Read all rows from `data/source_fleet.csv`
2. Generate unique SEO content for each service/city pair
3. Validate and transform content
4. Publish as draft pages to WordPress
5. Write detailed logs to `logs/`

## Configuration

Edit `data/source_fleet.csv` to define your fleet:
```csv
service,city,state
Concrete Driveways,Troy,MI
Stamped Concrete Patios,Farmington Hills,MI
```

Optional model override in `.env`:
```
GEMINI_MODEL=gemini-2.0-flash
```

## Output

- **Logs**: `logs/run_summary_*.json` - execution metrics and page creation results
- **Artifacts**: `logs/*.json` - raw Gemini responses for each generated page
- **WordPress**: Draft pages created under hierarchical category structure

## Security Notes

- Never commit `.env` with real credentials
- Use `.env.example` as a template for sharing
- WordPress Application Passwords are safer than storing plain-text credentials
- All API interactions are logged for audit purposes
