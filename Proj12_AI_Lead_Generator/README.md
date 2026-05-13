# AI Lead Generator for Web Services

End-to-end B2B lead generation and qualification system for web design agencies. Identifies potential clients from Google Maps, scores website quality with AI, generates redesign concepts, and produces personalized outreach campaigns ready for sales teams.

## Overview

This system automates the entire prospecting workflow for agencies targeting service-based businesses:

1. **Discovery**: Scrape service businesses from Google Maps by category, location
2. **Qualification**: Analyze each business website's quality and identify redesign opportunities
3. **Enrichment**: Generate AI-powered redesign concepts and mockups tailored to each prospect
4. **Outreach**: Create personalized, data-backed sales emails highlighting specific improvements
5. **Export**: Produce CSV output with all lead data, analysis, and outreach materials for CRM integration

## Key Features

- **Bulk prospecting**: Scrape hundreds of qualified leads in a single run
- **Multi-model AI analysis**: Claude and Gemini integration with auto-detection and fallback support
- **Website quality scoring**: Evaluates modernity, mobile-friendliness, design patterns, SEO fundamentals
- **Personalized previews**: AI-generated redesign concepts and HTML mockups for each lead
- **Sales-ready output**: CSV export with contact info, analysis, previews, and customized email copy
- **Async processing**: Concurrent API calls and web scraping for performance at scale
- **Full audit trail**: Timestamped logs for compliance, debugging, and reproducibility

## Architecture

```
Google Maps (via Apify)
    ↓
scraper.py (extraction)
    ↓
demonstrate_enhancement_fallback.py (AI routing)
    ↓
pipeline_processor.py (website analysis & scoring)
    ↓
image_generator.py (redesign preview generation)
    ↓
wp_importer.py / CSV export (lead output)
    ↓
data/leads_*.csv (sales-ready results)
```

### Core Components

| Module | Responsibility |
|--------|----------------|
| `scraper.py` | Extracts business data from Google Maps results |
| `pipeline_processor.py` | Fetches websites, scores quality, identifies opportunities |
| `image_generator.py` | Generates redesign concepts and mockup descriptions |
| `demonstrate_enhancement_fallback.py` | Routes requests to available AI models (Claude/Gemini) with fallback |
| `main.py` | Orchestrator: runs full pipeline end-to-end |

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Set required variables:
   - `ANTHROPIC_API_KEY` - Anthropic Claude API key
   - `GEMINI_API_KEY` - Google Gemini API key (fallback model)
   - `APIFY_API_TOKEN` - Apify platform token for Google Maps scraping

## Usage

**Basic usage:**
```bash
python src/main.py "bathroom remodeler" "Farmington Hills" "MI" --max_results 10
```

**Parameters:**
- Service category (e.g., "bathroom remodeler", "plumber", "roofing contractor")
- City name
- State code (2-letter abbreviation)
- `--max_results`: Number of leads to process (default: 10, max: 100)
- `--model`: Force specific model (`claude` or `gemini`; default: auto-detect)

## Output

- **CSV Export**: `data/leads_<timestamp>.csv` contains all leads with:
  - Business contact information
  - Website quality scores
  - Redesign recommendations
  - Personalized outreach email
- **Logs**: `logs/` directory with execution summaries and error tracking

## Configuration

Tune scoring thresholds in `pipeline_processor.py`:
- Minimum quality score for lead qualification
- Design modernization scoring weights
- SEO factor importance

## Security Notes

- Never commit `.env` with real credentials
- Use `.env.example` as a template for sharing
- API keys are injected at runtime from environment variables
- All external API calls are rate-limited and logged