# Dominance Report Engine ⚙️

**Cloud-Native Backend: JSON Ingestion to Dynamic PDF Generator & PostgreSQL**

A high-performance, decoupled backend prototype designed to calculate diagnostic scores, assign marketing tiers, store lead data in the cloud, and dynamically generate branded PDF reports for a lead-generation web application.



### 🏗️ Architecture Overview

Most quiz-based lead funnels fail because the frontend attempts to handle heavy logic and PDF rendering, leading to slow load times and browser crashes. This project implements a **Decoupled Backend Strategy**:

1. **JSON Ingestion (The Hook):** Accepts structured payload data from a frontend SPA (React/Vue) containing lead info and raw quiz answers.
2. **Rules Engine (The Brain):** Calculates a normalized score (0-100), assigns a competitive tier, and runs conditional logic to identify specific "Growth Leaks."
3. **Cloud Storage (The Database):** Securely pushes the structured lead data and calculated scores to a cloud-hosted PostgreSQL database (Supabase) using a REST API wrapper.
4. **Asset Generation (The Output):** Merges the calculated data with a Jinja2 HTML/CSS template and renders a high-fidelity PDF report using WeasyPrint.

### 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Logic Core** | Python 3 | Core mathematical and conditional routing |
| **Database** | Supabase (PostgreSQL) | Cloud-native data storage and REST API |
| **Templating** | Jinja2 | Separation of layout (HTML) from Python logic |
| **PDF Rendering** | WeasyPrint | High-fidelity HTML/CSS to PDF conversion |
| **Security** | `python-dotenv` | Environment variable masking for API keys |

### 🚀 Key Engineering Features

* **Separation of Concerns:** The HTML/CSS layout is strictly isolated in a `templates/` folder, ensuring the Python data pipeline remains untouched when UI changes are required.
* **Diagnostic Rules Engine:** Automatically maps quiz answer patterns to predefined insights without hardcoding massive `if/else` UI blocks.
* **Secure Cloud Integration:** Utilizes `.env` files and `.gitignore` to ensure database credentials are never exposed to version control.
* **Microservice Ready:** Modularized into `engine.py`, `db_client.py`, and `pdf_generator.py` so it can be easily wrapped in a FastAPI route or deployed as an AWS Lambda / GCP Cloud Function.

### 📂 Project Structure
```text
Proj6_Cloud_Report_Engine/
├── .env                  # Environment variables (Ignored in Git)
├── main.py               # The Orchestrator (runs the pipeline)
├── engine.py             # Business logic & scoring
├── db_client.py          # Supabase PostgreSQL integration
├── pdf_generator.py      # WeasyPrint PDF renderer
└── templates/
    └── report.html       # Jinja2 HTML layout
```
📥 Installation & Usage

1. Clone the Repository

```bash
git clone https://github.com/Ainz47/Projects.git
cd Projects/Proj6_Cloud_Report_Engine
```
2. Install Dependencies

```bash
git clone [https://github.com/Ainz47/Projects.git](https://github.com/Ainz47/Projects.git)
cd Projects/Proj6_Cloud_Report_Engine
```

3. Configure Environment
Create a .env file in the root directory and add your Supabase credentials:

```bash
SUPABASE_URL="your-supabase-project-url"
SUPABASE_KEY="your-supabase-anon-key"
```

4. Run the Pipeline

```bash
python main.py
```

📊 Output Verification
1. Database: Check your Supabase leads table to verify the new record was inserted securely.
2. Asset: The script generates a local PDF (e.g., Apex_Engineering_Group_Report.pdf).
Note: A sample PDF output (Sample_Dominance_Report.pdf) has been included in this repository for demonstration purposes.
