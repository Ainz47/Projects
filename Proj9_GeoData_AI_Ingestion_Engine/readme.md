# Intelligent Directory ETL Pipeline

An automated, AI-enriched ETL (Extract, Transform, Load) pipeline designed to aggregate business data, enrich it via generative AI, and ingest it into a WordPress-headless architecture. 

This project demonstrates robust data engineering principles, including pipeline resilience, data validation gates, AI-driven asset enhancement, and idempotent API ingestion.

## 🏗 System Architecture

The pipeline follows a structured three-phase ETL workflow:

1.  **Extraction (Scraping):** Utilizes Playwright to dynamically scrape "ground truth" data (name, address, high-resolution cover photos) directly from Google Maps.
2.  **Transformation & Enrichment (AI Processing):** * **Text:** Leverages the Gemini API to generate engaging, unique business descriptions.
    * **Vision & Assets:** Validates scraped images using Gemini Vision. Low-resolution images trigger an AI upscaling/enhancement process, while missing gallery assets are dynamically generated using Gemini's image generation capabilities.
3.  **Loading (Ingestion):** Pushes the structured JSON payload and media assets to a WordPress REST API. It utilizes an MD5 hash of the business name and address as a `place_id` to ensure idempotent operations (updating existing records instead of duplicating).

## ✨ Key Features

* **Idempotent Data Loading:** Prevents duplicate entries in the target database by checking custom metadata (`place_id`) before creating new Custom Post Types (CPTs).
* **Intelligent Fallbacks:** Built-in resilience for AI API quotas. If image generation or enhancement fails, the pipeline seamlessly falls back to utilizing copies of the original scraped assets to ensure the pipeline does not break.
* **Quality Gates:** Implements an "Image Relevance" filter using AI vision to discard irrelevant scraped photos (e.g., blurry menus or parking lots) before ingestion.
* **Local Mocking Environment:** Includes a FastAPI-based Mock WordPress server to test ingestion logic without needing a live CMS.

## 📂 Repository Structure

* **`run_pipeline.py`**: The primary orchestration script for the "happy path" execution.
* **`demonstrate_enhancement_fallback.py`**: A specialized execution script designed to test and demonstrate the system's fault-tolerance and fallback mechanisms when AI endpoints fail.
* **`scraper.py`**: Playwright-based extraction module targeting Google Maps DOM elements.
* **`pipeline_processor.py`**: Core transformation logic; handles data structuring into the required schema and triggers LLM text generation.
* **`transformations.py`**: Contains the visual quality gates (resolution checks and AI relevance filtering).
* **`image_generator_demo.py`**: Interfaces with the Gemini image models to generate or re-imagine visual assets, containing the core exception handling for API limits.
* **`wp_importer.py`**: The ingestion module handling multipart media uploads and JSON payload deployment to the REST API.
* **`mock_wp.py`**: A lightweight FastAPI server simulating WordPress media and directory listing endpoints.
* **`check_models.py`**: Utility script to verify available Gemini models linked to the current API key.

## ⚙️ Setup & Installation

**1. Environment Setup**
Ensure you have Python installed, then install the required dependencies:
`bash
pip install requests python-dotenv playwright google-genai pillow fastapi uvicorn
`

**2. Initialize Playwright**
Install the necessary browser binaries for the scraping module:
`bash
playwright install chromium
`

**3. Environment Variables**
Create a `.env` file in the project root with the following variables:
`env
GEMINI_API_KEY=your_gemini_api_key_here
WP_BASE_URL=http://127.0.0.1:8000
WP_USERNAME=mock_admin
WP_APP_PASSWORD=mock_password
`

## 🚀 Execution Guide

### Option A: Testing the Full Pipeline (Happy Path)

1. **Start the Target Server:** First, spin up the Mock WordPress API in a separate terminal:
   `bash
   uvicorn mock_wp:app --reload
   `
2. **Run the Orchestrator:** Execute the main pipeline script.
   `bash
   python run_pipeline.py
   `

### Option B: Testing Pipeline Resilience (Fallback Demonstration)

This script is designed to simulate API failures (e.g., hitting rate limits) to prove the pipeline's fault tolerance.

1. Ensure the Mock WP server is running (`uvicorn mock_wp:app --reload`).
2. Run the fallback demonstration:
   `bash
   python demonstrate_enhancement_fallback.py
   `
   *Watch the console output to observe the pipeline intercepting exceptions and routing to the original scraped fallback images, ultimately ensuring the JSON payload is successfully delivered.*