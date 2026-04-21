<p align="center">
  <img src="frontend/logo.jpeg" alt="DaddiesTrip Logo" width="150" style="border-radius:20px;">
</p>

<h1 align="center">DaddiesTrip</h1>

**DaddiesTrip** is an AI-enabled cross-border travel orchestration and multi-currency group accounting application. Planning group travel and managing shared expenses across different currencies is a highly fragmented, stressful process. Users currently switch between multiple apps for itineraries, flight bookings, and manual spreadsheets for conversions.

**The Purpose**: DaddiesTrip automates the entire lifecycle of group travel—from conversational itinerary generation to exact multi-currency expense splitting. Our mission is to facilitate frictionless, secure digital planning to ensure absolute financial accuracy and beautiful trip organization.

## 🚀 Features

- **Conversational Planning (Z.AI Integration)**
  Turn unstructured travel blogs, text boundaries, or ideas into structured 5-day itineraries using advanced AI inference. If your prompt is invalid or budget too low, our AI safely halts and converses with you to resolve the constraint.
- **Flight & Hotel API Orchestration**
  Provides accurate data routing with dynamically loaded airline logos based on verified IATA codes. Smart routing detects local vs. international travel and bypasses unnecessary flight steps.
- **Smart Multi-Currency Ledger**
  Split costs seamlessly using real-time currency conversions powered by the open, keyless Fawaz Ahmed Exchange API (`@fawazahmed0/currency-api`).
- **Interactive Google Maps integration**
  Every generated activity is dynamically embedded as a rich local HTML iframe showing the explicit region and routing context.
- **Apple-Style Minimalist UI**
  Frosted glass aesthetics with real-time budget warnings, responsive mapping interfaces, and Server-Sent Event (SSE) micro-animations.
- **PDF Generation**
  One-click itinerary export powered by `html2pdf.js` for beautiful offline reading.

## 🧠 Multi-Agent Architecture

DaddiesTrip utilizes a localized multi-agent workflow where each sub-agent handles a uniquely focused task, eliminating hallucination cross-contamination.

1. **Analyzer Agent** 
   - **Task**: The first line of defense. Scans the user's conversational input to ensure the request is physically possible. Checks for missing locations, participant counts, and ensures the budget isn't impossibly low. Acts as a conversational chatbot to ask the user for clarity if input fails.
2. **Planner Agent** 
   - **Task**: Drafts chronological routes. Ensures morning/afternoon/evening schedule blocks are enforced with exact duration estimates. Correlates attraction names to accurate map locations.
3. **Booking Agent** 
   - **Task**: Finds flights, accommodations, and verifies if the distance strictly requires flights. If travel is local, intelligently bypassed. Formats IATA codes for UI components.
4. **Budget Agent** 
   - **Task**: Acts as the financial optimizer. It takes the gross sums, pulls live conversion rates, and trims or approves the trip cost against the user's absolute maximum budget.
5. **Edge Agent** 
   - **Task**: Quality assurance checking data integrity across JSON responses and edge scenarios.
6. **Translation Agent** 
   - **Task**: Final localization and formatting.

## 🛠 Setup Instructions

1. **Install Python Environment:**
    Ensure you have Python 3.10+ installed.
    ```bash
    pip install -r backend/requirements.txt
    ```

2. **Configure Environment Variables:**
    To run the app with active AI orchestration, create the `.env` file (if not present) and add your Z.AI / LLM API key:
    ```env
    Z_AI_API_KEY=your_key_here
    Z_AI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
    Z_AI_MODEL=glm-4
    ```

3. **Start the Application:**
    Navigate to the root directory and start the FastAPI server using Server-Sent Event support.
    ```bash
    uvicorn backend.main:app --reload
    ```

4. **Open the Application:**
    Navigate to `http://localhost:8000` in your web browser.

## ⚙️ Testing

The application ships with a PyTest suite based on the provided Quality Assurance Testing Documentation (QATD).
- Run `pytest backend/tests/test_agents.py` to verify:
  - **TC-01:** System outputs correct payload and split mechanics.
  - **TC-02:** System accurately flags negative/failed terminal payments.
  - **AI-01:** System correctly handles massive wall-of-text prompts exceeding 1500 tokens using algorithmic array chunking.
