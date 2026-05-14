# Agentic Financial Intelligence System

An autonomous, multi-agent personal finance assistant delivered through a Telegram interface. The system uses a LangGraph state machine to orchestrate specialized AI agents that understand natural language, extract structured financial data, interact with a PostgreSQL database, and respond in natural conversational language â€” all without performing any arithmetic in the LLM layer.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Agent Descriptions](#agent-descriptions)
- [Data Flow](#data-flow)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Tech Stack](#tech-stack)
- [Installation and Setup](#installation-and-setup)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)
- [Known Limitations and Future Enhancements](#known-limitations-and-future-enhancements)

---

## Overview

This project implements a production-oriented agentic AI system for personal expense tracking. Users interact with a Telegram bot in plain language â€” logging expenses, querying their spending history, or deleting entries â€” and the system routes each request through the appropriate pipeline of specialized agents.

The core orchestration engine is LangGraph, which compiles a stateful directed graph of agent nodes. State is checkpointed per user (keyed by `telegram_id`), enabling multi-turn clarification loops and Human-in-the-Loop confirmation flows without losing context between messages.

A strict "No LLM Math" principle is enforced throughout: all aggregations (totals, averages, counts) are computed by PostgreSQL via pre-defined parameterized query templates. The LLM layer is responsible only for intent classification, data extraction, query key selection, and natural language response generation.

---

## Key Features

**Agentic Workflow**
A state graph with four specialized agents â€” Router, Extractor, Database Agent, and Analyst â€” each handling a distinct concern with no cross-contamination of responsibilities.

**Natural Language Interface**
Users interact in free-form text over Telegram. The system handles varied phrasing, incomplete inputs, and multi-turn clarification without requiring structured commands.

**Human-in-the-Loop Confirmation**
Delete operations are interrupted before execution. The system sends the user an inline keyboard confirmation prompt. The graph resumes only after explicit user approval via a callback button, using LangGraph's native `interrupt()` and `Command(resume=...)` pattern.

**Structured Data Extraction**
PydanticAI extracts expense data into a validated `ExpenseSchema` (item, amount, currency, category) with a fixed category enumeration. Invalid or incomplete inputs trigger targeted clarification questions rather than errors.

**SQL Injection Prevention**
All database queries use parameterized SQLAlchemy templates with `:param` bindings. No SQL is ever generated or interpolated from user input or LLM output.

**Fully Asynchronous Runtime**
Built on `asyncio` throughout: FastAPI for the webhook server, `asyncpg` for database access, and `python-telegram-bot` v21 async API for Telegram communication.

**Conversation History**
Each agent node receives and appends to a shared `conversation_history` list carried in the `AgentState`, enabling context-aware clarification and multi-turn interactions.

---

## System Architecture

The system follows a webhook-driven architecture. Telegram routes incoming messages to a FastAPI server, which dispatches them to the LangGraph workflow. Each graph invocation is scoped to a user-specific thread via a checkpointer.

```
Telegram User
     |
     | (message / callback)
     v
python-telegram-bot (PTB Application)
     |
     | (dispatches to handlers)
     v
FastAPI Webhook Server  (/webhook endpoint)
     |
     | (ainvoke with thread_id config)
     v
LangGraph StateGraph
     |
     +---> Router Agent
     |         |
     |         +-- log_expense  --> Extractor Agent --> Database Agent --> Analyst Agent
     |         |
     |         +-- query_finance --------------> Database Agent --> Analyst Agent
     |         |
     |         +-- delete_entry --> confirm_delete (interrupt) --> Database Agent --> Analyst Agent
     |         |
     |         +-- unknown / clarification --> END
     |
     v
AgentState (checkpointed per user thread_id)
     |
     v
PostgreSQL (expenses, users, categories)
```

The graph is compiled once at startup with a `MemorySaver` checkpointer attached. For production deployments, this should be replaced with `AsyncPostgresSaver` to persist state across server restarts.

---

## Agent Descriptions

### Router Agent

**File:** `agents/router.py`

Classifies the user's intent into one of four categories: `log_expense`, `query_finance`, `delete_entry`, or `unknown`. Uses a structured LLM output (`RouterOutput` via Pydantic) to enforce a valid classification. If the message is ambiguous or off-topic, the agent sets `needs_clarification=True` and provides a targeted clarification question. The user message is appended to `conversation_history` before the LLM call to maintain multi-turn context.

### Extractor Agent

**File:** `agents/extractor.py`

Parses the user's natural language description of an expense into a structured `ExpenseSchema` containing `item`, `amount`, `currency`, and `category`. The category must be one of ten fixed values enforced via a Pydantic `Literal` type. Uses a PydanticAI `Agent` with `result_type=ExpenseSchema` for validated structured output. If `amount` is absent from the message, the agent triggers a clarification request rather than failing silently.

**Fixed Categories:** Food, Transport, Utilities, Entertainment, Electronics, Health, Education, Shopping, Housing, Other

### Database Agent

**File:** `agents/db_agent.py`

Handles all database interactions for all three intent types.

For `log_expense`: resolves the category by name from the `categories` table, upserts the user record by `telegram_id`, and inserts a new `Expense` row via SQLAlchemy ORM.

For `query_finance`: selects a pre-defined query template from `QUERY_TEMPLATES` based on keyword matching against the user message, then executes it with parameterized bindings. Available templates include `total_all_time`, `total_today`, `total_this_week`, `total_this_month`, `total_by_category`, `average_per_transaction`, `average_by_category`, and `recent_expenses`.

For `delete_entry`: executes a DELETE only after the HITL confirmation flag has been cleared by a successful `Command(resume=True)` graph resume.

### Analyst Agent

**File:** `agents/analyst.py`

Transforms raw database results or operation statuses into warm, natural language responses. Does not perform any arithmetic. Receives `sql_result` (list of dicts from DB rows), `intent`, `operation_status`, and `extracted_data` from the state, and crafts an appropriate response. Appends the assistant reply to `conversation_history` for continuity.

---

## Data Flow

**Logging an Expense**

1. User sends: `"spent 150 on lunch"`
2. Router classifies: `log_expense`
3. Extractor produces: `{item: "lunch", amount: 150.0, currency: "EGP", category: "Food"}`
4. Database Agent inserts the expense row into PostgreSQL
5. Analyst generates: `"Your lunch expense of 150.00 EGP has been recorded under Food."`
6. Response sent to Telegram

**Querying Finance**

1. User sends: `"how much did I spend this month?"`
2. Router classifies: `query_finance`
3. Database Agent selects template `total_this_month`, executes against PostgreSQL
4. Analyst formats the result: `"You've spent a total of 4,250.00 EGP this month."`
5. Response sent to Telegram

**Deleting an Entry**

1. User sends: `"delete my last expense"`
2. Router classifies: `delete_entry`
3. Graph hits the `confirm_delete` node, which calls `interrupt()`
4. Telegram sends an inline keyboard: `[Yes, delete it] [No, keep it]`
5. User taps a button; callback fires
6. Graph resumes via `ainvoke(Command(resume=True/False), config)`
7. If confirmed, Database Agent deletes the most recent expense
8. Analyst confirms: `"Your last expense has been successfully deleted."`

---

## Project Structure

```
Agentic-Financial-Intelligence-System/
|
+-- main.py                         # Application entry point (Uvicorn launcher)
+-- config.py                       # Pydantic Settings with .env loading
+-- requirements.txt                # All Python dependencies
+-- implementation_plan.md          # Detailed internal architecture reference
+-- __init__.py
|
+-- agents/
|   +-- __init__.py
|   +-- router.py                   # Intent classification agent
|   +-- extractor.py                # Structured data extraction agent (PydanticAI)
|   +-- db_agent.py                 # Database operations agent (parameterized SQL)
|   +-- analyst.py                  # Natural language response generation agent
|
+-- graph/
|   +-- __init__.py
|   +-- state.py                    # AgentState TypedDict definition
|   +-- workflow.py                 # LangGraph StateGraph construction and compilation
|
+-- api/
|   +-- __init__.py
|   +-- server.py                   # FastAPI app with lifespan, /webhook, /health endpoints
|
+-- database/
|   +-- __init__.py
|   +-- connection.py               # Async SQLAlchemy engine, session factory, init_db()
|   +-- models.py                   # ORM models: User, Category, Expense
|
+-- interface/
    +-- __init__.py
    +-- telegram_handler.py         # PTB message handler, callback handler, HITL resume
```

---

## Database Schema

### Table: `users`

| Column | Type | Description |
|---|---|---|
| `telegram_id` | BigInteger (PK) | Telegram user ID (must be BigInteger to handle large IDs) |
| `username` | String (nullable) | Telegram username |
| `created_at` | DateTime | Account creation timestamp |

### Table: `categories`

| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-incremented ID |
| `name` | String (unique) | Category name (seeded on startup) |

### Table: `expenses`

| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-incremented ID |
| `user_id` | BigInteger (FK) | References `users.telegram_id` |
| `category_id` | Integer (FK) | References `categories.id` |
| `item` | Text | Description of the purchased item or service |
| `amount` | Numeric(12, 2) | Expense amount |
| `currency` | String | Currency code, defaults to `EGP` |
| `created_at` | DateTime | Timestamp of the expense |

Categories are seeded automatically on first startup via `init_db()` using an `INSERT ... ON CONFLICT DO NOTHING` pattern, making repeated startups idempotent.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph >= 0.2, LangChain Core |
| LLM Provider | OpenRouter API (default: Qwen3) / OpenAI-compatible |
| Data Extraction | PydanticAI >= 0.0.18 |
| LLM Interface | LangChain OpenAI |
| Backend API | FastAPI, Uvicorn |
| Database | PostgreSQL, SQLAlchemy (Async), asyncpg |
| Telegram Interface | python-telegram-bot >= 21.0 (webhook mode) |
| Configuration | Pydantic Settings, python-dotenv |
| State Validation | Pydantic >= 2.0 |

---

## Installation and Setup

**Prerequisites**

- Python 3.10 or higher
- PostgreSQL instance (local or hosted, e.g., Supabase)
- A Telegram bot token from BotFather
- An OpenRouter API key (or a standard OpenAI API key)
- A publicly accessible HTTPS URL for the Telegram webhook (e.g., via ngrok for local development or a cloud deployment)

**Step 1 â€” Clone the repository**

```bash
git clone https://github.com/AhmIsmail88/Agentic-Financial-Intelligence-System.git
cd Agentic-Financial-Intelligence-System
```

**Step 2 â€” Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
source venv/Scripts/activate

# Linux / macOS
source venv/bin/activate
```

**Step 3 â€” Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 4 â€” Configure environment variables**

Create a `.env` file in the project root. See the [Environment Variables](#environment-variables) section for all required fields.

**Step 5 â€” Provision the database**

Ensure your PostgreSQL server is running and that the `finance_db` database (or the database specified in `POSTGRES_URL`) exists. The application will create all required tables and seed the `categories` table automatically on startup. No manual schema migrations are required.

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token

# Webhook â€” must be a publicly accessible HTTPS URL
WEBHOOK_URL=https://your-domain.com/webhook

# PostgreSQL
POSTGRES_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/finance_db

# LLM â€” provide at least one
OPENROUTER_API_KEY=your_openrouter_api_key
OPENAI_API_KEY=your_openai_api_key

# Model names (optional overrides â€” defaults shown below)
ROUTER_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
EXTRACTOR_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
ANALYST_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
```

If both `OPENROUTER_API_KEY` and `OPENAI_API_KEY` are provided, OpenRouter takes precedence. The three model name variables allow independent model selection per agent, which is useful for balancing cost and capability.

---

## Running the Application

```bash
python main.py
```

On startup, the application performs the following steps in order:

1. Loads environment variables from `.env`
2. Connects to PostgreSQL and runs `init_db()` â€” creating tables and seeding categories
3. Initializes the PTB (python-telegram-bot) application
4. Registers the Telegram webhook by calling `bot.set_webhook(url=WEBHOOK_URL)`
5. Starts the FastAPI server on `0.0.0.0:8000` (port overridable via `PORT` env var)

For local development, use a tunneling tool such as ngrok to expose port 8000 over HTTPS before setting the webhook URL.

```bash
# Example with ngrok
ngrok http 8000
# Copy the HTTPS forwarding URL to WEBHOOK_URL in .env before running main.py
```

---

## Usage Examples

The following examples illustrate supported natural language inputs.

**Logging an expense**

```
spent 200 EGP on groceries
bought a book for 85 pounds
taxi to the airport, 350
lunch for 60 bucks
```

If the amount is missing, the bot will ask: `"How much did you spend on [item]?"`

**Querying spending**

```
how much did I spend today?
show me my last 5 expenses
what did I spend this month?
total by category
average per transaction
how much have I spent on food this month?
```

**Deleting an entry**

```
delete my last expense
remove the last entry
undo my last log
```

The bot will respond with a confirmation prompt. The expense is only deleted after the user taps the confirmation button.

---

## Design Decisions

**No LLM Math**
All numerical aggregations (SUM, AVG, COUNT, MIN, MAX) are executed exclusively in PostgreSQL using pre-defined, parameterized query templates. The LLM never generates SQL and never performs arithmetic. This eliminates both SQL injection risk and LLM hallucination in numerical outputs.

**Human-in-the-Loop via LangGraph `interrupt()`**
The delete confirmation flow uses LangGraph's native `interrupt()` to suspend the graph mid-execution. The graph state is persisted in the checkpointer. When the user responds via the inline keyboard callback, the graph resumes via `graph.ainvoke(Command(resume=confirmed_bool), config)`. This is the correct pattern for HITL in LangGraph v0.2+ and avoids stateful flag polling.

**Checkpointing is Mandatory for HITL**
A `MemorySaver` checkpointer is attached to the compiled graph. Without it, `interrupt()` cannot persist the paused state and `Command(resume=...)` has nothing to restore. For production deployments, `MemorySaver` should be replaced with `AsyncPostgresSaver` to survive server restarts.

**`thread_id` equals `str(telegram_id)`**
Each Telegram user maps to a single LangGraph thread. Using the Telegram user ID as the `thread_id` ensures that all checkpointed state, conversation history, and HITL interrupts are correctly scoped per user with zero additional session management.

**Conversation History in State**
The `conversation_history` list is carried through every node in `AgentState`. Each agent appends its contribution before returning updated state. This allows the Router and Extractor to be context-aware during multi-turn clarification flows, where the user's follow-up message must be interpreted in light of the previous exchange.

**`telegram_id` as `BigInteger`**
Telegram user IDs can exceed the 32-bit integer range (2,147,483,647). The SQLAlchemy column type for `User.telegram_id` is explicitly `BigInteger` to prevent silent overflow or insertion failures for users with large IDs.

**Modular Agent Separation**
Each agent file is responsible for a single concern. `extractor.py` contains no SQL. `db_agent.py` contains no natural language parsing. `analyst.py` contains no database access. Configuration and session management are injected from shared modules (`config.py`, `database/connection.py`), not imported laterally between agents.

**Async Throughout**
The entire call chain is non-blocking: FastAPI handles HTTP concurrently, `asyncpg` executes database queries without blocking the event loop, and `python-telegram-bot` v21 dispatches handlers asynchronously. This allows the server to handle multiple simultaneous users efficiently.

---

## Known Limitations and Future Enhancements

**Current Limitations**

- Query selection in `db_agent.py` uses keyword matching on the user message rather than LLM-based template selection, which can fail for unconventional phrasing.
- The `MemorySaver` checkpointer does not survive server restarts. In-progress HITL flows (e.g., a pending delete confirmation) are lost on restart.
- There is no authentication layer on the FastAPI `/webhook` endpoint. It accepts any POST request without verifying the Telegram secret token header.
- Expense categories are hardcoded in both the Pydantic model and the database seed. Adding a new category requires a code change and a database migration.

**Planned Enhancements**

- Replace `MemorySaver` with `AsyncPostgresSaver` for durable checkpointing across restarts.
- Add Telegram webhook secret token validation to the `/webhook` endpoint.
- Implement LLM-based query key selection to replace brittle keyword matching in the Database Agent.
- Add export functionality for financial reports to Excel using `pandas` and `openpyxl`.
- Integrate LangSmith for LLM tracing, evaluation, and observability.
- Support multi-currency conversion and reporting.
- Add user-configurable category management via Telegram commands.

---

**Developed by Phoenix Team**