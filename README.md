# Agentic Financial Intelligence System

An intelligent, autonomous personal finance assistant accessible via Telegram. This system leverages an Agentic AI Architecture (powered by LangGraph and OpenRouter) to understand natural language, securely manage PostgreSQL databases, and provide actionable financial insights.

## Key Features
* **Agentic Workflow:** Utilizes a state-graph architecture with specialized AI agents (Router, Extractor, Database Agent, and Analyst) working in harmony.
* **Natural Language Interface:** Users can log expenses, query financial data, or delete entries using everyday language via Telegram.
* **Secure SQL Generation:** Employs strict parameterized queries and validation layers to prevent SQL injection and unauthorized destructive commands.
* **Human-in-the-Loop:** Requires explicit user confirmation via Telegram inline buttons before executing any deletion commands.
* **High Performance:** Built with asynchronous Python (`asyncio`, `FastAPI`, `asyncpg`, `httpx`) to handle concurrent requests seamlessly.
* **Structured Data Extraction:** Uses Pydantic and JSON-mode LLM extraction to ensure data integrity before database insertion.

## System Architecture (LangGraph)
The system operates on a state machine logic:
1.  **Router Agent:** Classifies user intent (`log_expense`, `query_finance`, `delete_entry`).
2.  **Extractor Agent:** Parses natural language into structured JSON based on a predefined `ExpenseSchema` and strict categories.
3.  **Database Agent:** Generates and executes safe PostgreSQL queries.
4.  **Analyst Agent:** Summarizes the database output into friendly, natural language responses.

## Tech Stack
* **Core:** Python 3.10+
* **AI/LLM:** LangGraph, OpenRouter API (GPT-4o-mini)
* **Backend:** FastAPI, Uvicorn
* **Database:** PostgreSQL, SQLAlchemy (Async), asyncpg
* **Interface:** python-telegram-bot

## Installation & Setup

**1. Clone the repository**
```bash
git clone [https://github.com/AhmIsmail88/Agentic-Financial-Intelligence-System.git](https://github.com/AhmIsmail88/Agentic-Financial-Intelligence-System.git)
cd Agentic-Financial-Intelligence-System

```

**2. Set up a virtual environment**

```bash
python -m venv venv
source venv/Scripts/activate  # On Windows
# source venv/bin/activate    # On Linux/Mac

```

**3. Install dependencies**

```bash
pip install -r requirements.txt

```

**4. Configure Environment Variables**
Create a `.env` file in the root directory and add the following:

```env
TELEGRAM_TOKEN="your_telegram_bot_token"
OPENROUTER_API_KEY="your_openrouter_api_key"
BACKEND_URL="http://localhost:8000/api/chat"
POSTGRES_URL="postgresql+asyncpg://postgres:yourpassword@localhost:5432/finance_db"

```

**5. Database Setup**
Ensure PostgreSQL is running locally and create a database named `finance_db`. The system will automatically create the required tables (`users`, `categories`, `expenses`) upon startup.

**6. Run the Application**

```bash
python main.py

```

*The system will initialize the database, start the Telegram polling client, and spin up the FastAPI backend simultaneously.*

## Future Enhancements

* Export financial reports to Excel (`pandas`, `openpyxl`).
* Implement LangSmith for automated LLM evaluation and tracing.
* Add short-term memory (Checkpointers) for context-aware conversations.

---

**Developed by Phoenix Team**

