# Restaurant OS: Multi-Source ETL & Alerting Microservice ⚙️

**Full-Stack Data Engineering Pipeline (FastAPI + PostgreSQL + Webhooks)**

A high-performance backend microservice designed to ingest asynchronous data from multiple restaurant SaaS platforms (Toast POS & 7shifts), calculate real-time profitability metrics, and trigger threshold-based alerts for operations teams.

### 🏗️ Architecture Overview

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md) | [docs/architecture-diagram.svg](./docs/architecture-diagram.svg) | [docs/architecture-diagram.png](./docs/architecture-diagram.png)

Restaurant operators often struggle because their Sales data and Labor data live in separate silos. This microservice solves that by acting as a central Aggregator and Logic Engine:

1. **Asynchronous Ingestion (The Webhooks):** FastAPI endpoints receive daily JSON payloads from POS and Labor scheduling systems.
2. **State Management (The Database):** Stores the fragmented data in a structured PostgreSQL database (Supabase) using idempotent UPSERT operations.
3. **Decoupled Business Logic (The Math):** The raw data is passed to a dedicated `transformations.py` module to calculate the Cost Per Labor Hour (CPLH) and Labor as a % of Sales.
4. **Actionable Alerting (The Notifier):** If the labor percentage exceeds a profitable threshold (>25%), the system instantly pushes an alert to the Operations Team via a Discord/Slack webhook.

### 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | FastAPI (Python) | High-speed, async API routing and Background Tasks |
| **Data Validation** | Pydantic | Strict type-checking to prevent dirty data ingestion |
| **Database** | Supabase (PostgreSQL) | Cloud-native relational data storage |
| **Alerting** | HTTP Webhooks | Real-time push notifications (Discord/Slack integration) |

### 🚀 Key Engineering Features

* **Separation of Concerns:** Core business math is strictly isolated in `transformations.py`, keeping the API routing (`main.py`) clean, lightweight, and scalable.
* **Event-Driven Processing:** Uses FastAPI `BackgroundTasks` to perform ETL calculations *after* responding to the API, ensuring the webhooks never block external services.
* **Idempotent Storage:** Uses intelligent Upsert logic. If 7shifts sends updated labor data later in the day, the database updates the existing row and recalculates metrics rather than creating duplicate entries.
* **Schema-Driven API:** Automatically generates interactive Swagger UI documentation (`/docs`) based on Pydantic models.

### 📂 Project Structure
```text
Proj7_FastAPI_ETL_Alerts/
├── .env                  # Environment variables (Supabase Keys, Alert Webhooks)
├── main.py               # FastAPI application, routing, and Background Tasks
├── database.py           # PostgreSQL connection pool and Upsert logic
├── transformations.py    # Isolated business math (CPLH & Labor %)
├── notifier.py           # Alerting logic for Discord/Slack
└── mock_data_sender.py   # Test simulator to fire JSON payloads at the local server
```

## 📥 Local Setup & Testing
1. Install Dependencies

```bash
pip install fastapi uvicorn supabase python-dotenv requests pydantic
```

2. Boot the Server

```bash
uvicorn main:app --reload
```

3. Run the Simulator
In a separate terminal, run the mock data script to fire simulated Toast and 7shifts data at the API:

```bash
python mock_data_sender.py
```

**Observe the Uvicorn terminal for the background calculations and check your configured webhook channel for the alert!**
