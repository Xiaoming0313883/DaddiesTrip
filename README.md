<p align="center">
  <img src="frontend/logo.jpeg" alt="DaddiesTrip Logo" width="150" style="border-radius:20px;">
</p>

<h1 align="center">DaddiesTrip</h1>

<p align="center">
  <strong>An Enterprise-Grade, AI-Enabled Cross-Border Travel Orchestration & Group Accounting Platform</strong>
</p>

## 📌 Overview

**DaddiesTrip** is an AI-enabled cross-border travel orchestration and multi-currency group accounting application. Planning group travel and managing shared expenses across different currencies is a highly fragmented, stressful process. Users typically switch between multiple apps for itineraries, flight bookings, and manual spreadsheets for conversions.

**Our Mission**: DaddiesTrip automates the entire lifecycle of group travel—from conversational itinerary generation to precise multi-currency expense splitting. We aim to facilitate frictionless, secure digital planning to ensure absolute financial accuracy and beautiful trip organization.

---

## 🚀 Key Features

- **Conversational Planning & Validation**
  Turn unstructured travel ideas into structured 5-day itineraries using advanced AI inference. If a prompt is invalid or the budget is too low, our AI safely halts and converses with the user to resolve the constraint.
- **Flight & Hotel API Orchestration**
  Provides accurate data routing with dynamically loaded airline logos based on verified IATA codes. Smart routing detects local vs. international travel and bypasses unnecessary flight steps. Each flight option is paired with a direct deep-link to Skyscanner.
- **Enhanced POI (Point of Interest) Enrichment**
  Aggregates real Google Reviews, star ratings, and accurate real-world cost metrics for both daily activities and food recommendations.
- **Smart Multi-Currency Ledger**
  Split costs seamlessly using real-time currency conversions powered by the open, keyless Fawaz Ahmed Exchange API (`@fawazahmed0/currency-api`).
- **Interactive Map Integration**
  Every generated activity is dynamically embedded as a rich local HTML iframe showing the explicit region and routing context.
- **Enterprise UX & High-Performance Output**
  Features a frosted-glass minimalist aesthetic, real-time Server-Sent Events (SSE) streaming with active response time telemetry, and optimized PDF generation for offline access.

---

## 🧠 Enterprise Multi-Agent Architecture

DaddiesTrip utilizes a highly modular **Localized Multi-Agent Workflow**. Each sub-agent is strictly constrained to a single functional domain, drastically reducing hallucination cross-contamination and improving overall execution speed.

### 1. Analyzer Agent (The Gatekeeper)
- **Role:** The first line of defense.
- **Usage:** Scans the user's conversational input to ensure the request is physically possible.
- **Prompt Logic:** Analyzes the prompt to verify 1) Destination, 2) Participants, 3) Trip dates (start to end), and 4) Minimum viable budget. If any component is missing, it outputs a strict JSON `{ "status": "invalid", "message": "..." }` and acts as a chatbot to request clarification.

### 2. Planner Agent (The Navigator)
- **Role:** Drafts the chronological structure.
- **Usage:** Creates a high-level logical itinerary based on the user's validated request.
- **Prompt Logic:** Enforces accurate time estimates (e.g., "09:00 - 11:30") and determines the `requires_flight` boolean flag by evaluating if the destination is international or >300km away. Generates precise map query strings.

### 3. Booking Agent (The Concierge)
- **Role:** Aggregates real-world bookings and POI metadata.
- **Usage:** Finds flights, accommodations, tickets, and dining options.
- **Prompt Logic:** Must provide exactly 3 flight options with distinct airline IATA codes and Skyscanner deep-links. For Activities and Food, it is explicitly instructed to source real Google review scores (e.g., "4.8/5"), short descriptive comments, and exact `cost_myr`. Ensures no placeholder costs (like "RM25") are used.

### 4. Budget Agent (The Financial Controller)
- **Role:** Optimizes expenses.
- **Usage:** Takes the gross sums, pulls live conversion rates, and trims or approves the trip cost against the user's absolute maximum budget.
- **Prompt Logic:** Receives the fully mapped itinerary and cheapest flight option. Iterates over the total sum, compares it to the parsed budget string, and generates boolean flags (`is_sufficient`) and contextual saving tips if the budget is breached.

### 5. Edge Agent (The QA Engineer)
- **Role:** Quality Assurance and Data Integrity.
- **Usage:** Runs deterministic Python-side heuristic checks on the final JSON before output.
- **Prompt Logic:** Receives the errors detected by Python logic (e.g., Departure and Return airports are identical, or all ticket prices hallucinated to the exact same number) and forces the LLM to patch the JSON.

### 6. Translation Agent (The Localizer)
- **Role:** Final localization formatting.
- **Usage:** Ensures the output is correctly formatted in the requested language while preserving JSON structural integrity and markdown formatting.

---

## 🛠 Setup & Deployment Instructions

### 1. Install Python Environment
Ensure you have **Python 3.10+** installed.
```bash
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory. Configure your preferred AI model API keys.
```env
Z_AI_API_KEY=your_api_key_here
Z_AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
Z_AI_MODEL=glm-4
```

### 3. Start the Server
Navigate to the root directory and start the FastAPI server with Server-Sent Event (SSE) stream support.
```bash
uvicorn backend.main:app --reload
```

### 4. Access the Client
Open your web browser and navigate to:
```text
http://localhost:8000
```

---

## ⚙️ Testing & QA

The application ships with a PyTest suite based on the provided Quality Assurance Testing Documentation (QATD).

Run the testing module to verify system integrity:
```bash
pytest backend/tests/test_agents.py
```

**Test Coverage Includes:**
- **TC-01:** System outputs correct payload schema and verifies internal ledger split mechanics.
- **TC-02:** System accurately flags negative/failed terminal payments using simulated mock cards.
- **AI-01:** System correctly handles massive wall-of-text prompts exceeding 1500 tokens using algorithmic array chunking, ensuring the LLM context window does not overflow.
