from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
import re
from pydantic import BaseModel
from backend.agents.mock_agents import OrchestratorAgent
from backend.agents.booking_agent import BookingAgent
from backend.agents.base_agent import AgentAPIError
from backend.ledger.ledger_service import LedgerService
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="DaddiesTrip API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TripRequest(BaseModel):
    prompt: str

class SettlementRequest(BaseModel):
    group_id: str
    user_id: str
    card_number: str

class AnalyzeRequest(BaseModel):
    prompt: str

class PlanRequest(BaseModel):
    prompt: str

class BookingRequest(BaseModel):
    itinerary_draft: dict
    trip_summary: dict
    participants: list
    num_participants: int

ledger_service = LedgerService()
orchestrator = OrchestratorAgent()
booking_agent = BookingAgent()

# ─── Original SSE endpoint (kept for backward compat / Pro tier) ────────────

@app.post("/api/plan-trip-stream")
async def plan_trip_stream(request: TripRequest):
    def event_stream():
        try:
            for event in orchestrator.process_prompt_stream(request.prompt):
                yield f"data: {json.dumps(event)}\n\n"
        except AgentAPIError as e:
            print(f"Orchestration API error: {e.detail or e.user_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.user_message})}\n\n"
        except Exception as e:
            print(f"Orchestration error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'An unexpected error occurred: {type(e).__name__}. Please try again.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ─── Split endpoints (each stays within Vercel Hobby 60s limit) ─────────────

@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    """Step 1: Validate the prompt. ~5-10s."""
    try:
        result = orchestrator.analyzer.analyze(request.prompt)
        return result or {"status": "valid", "missing_fields": [], "message": ""}
    except AgentAPIError as e:
        raise HTTPException(status_code=502, detail=e.user_message)
    except Exception as e:
        return {"status": "valid", "missing_fields": [], "message": ""}


@app.post("/api/plan")
async def plan(request: PlanRequest):
    """Step 2: Analyze + Plan. ~20-35s."""
    # Analyze first
    analyze_res = orchestrator.analyzer.analyze(request.prompt) or {}
    if analyze_res.get("status") == "invalid":
        return {
            "status": "clarification",
            "message": analyze_res.get("message", "Please provide more details about your trip."),
            "missing_fields": analyze_res.get("missing_fields", []),
        }

    # Plan
    try:
        itinerary_draft = orchestrator.planner.plan(request.prompt) or {"itinerary": []}
    except AgentAPIError as e:
        raise HTTPException(status_code=502, detail=e.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planner failed: {e}")

    participants_raw = itinerary_draft.get("participants", [])
    num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', request.prompt, re.IGNORECASE)
    if num_match:
        participants_raw = [f"Adult {i+1}" for i in range(int(num_match.group(1)))]
    elif not participants_raw:
        participants_raw = ["User"]
    num_participants = len(participants_raw)

    trip_summary = OrchestratorAgent._build_trip_summary(request.prompt, itinerary_draft)

    partial_days = [
        {
            "day": d.get("day") or (i + 1),
            "location": d.get("location") or "Destination",
            "activities": d.get("activities", []),
        }
        for i, d in enumerate(itinerary_draft.get("itinerary", []))
    ]

    return {
        "status": "success",
        "itinerary_draft": itinerary_draft,
        "trip_summary": trip_summary,
        "participants": participants_raw,
        "num_participants": num_participants,
        "partial_days": partial_days,
    }


@app.post("/api/booking")
async def booking(request: BookingRequest):
    """Step 3: Booking + Budget + Edge. ~20-35s. No LLM for budget/edge."""
    compressed = OrchestratorAgent._compress_for_booking(request.itinerary_draft)
    booking_result = {}
    booking_error = None

    try:
        booking_result = orchestrator.booking.get_details(compressed, request.trip_summary) or {}
    except AgentAPIError as e:
        booking_error = e.user_message
    except Exception as e:
        booking_error = f"Booking failed: {e}"
        print(f"Booking Agent error: {e}")

    if booking_error:
        print(f"Booking Agent error (graceful fallback): {booking_error}")

    # Merge planner + booking
    merged_itinerary = OrchestratorAgent._merge_itineraries(
        request.itinerary_draft.get("itinerary", []),
        booking_result.get("itinerary_details", []),
    )

    flight_options = booking_result.get("flight_options", [])
    cheapest_flight = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}

    # Budget (Python, instant)
    budget_limit_myr = request.trip_summary.get("budget_myr", 5000)
    budget_result = OrchestratorAgent._calculate_budget(
        merged_itinerary, flight_options, request.num_participants, budget_limit_myr
    )
    final_total = budget_result["estimated_total_cost_myr"]

    # Split
    dest_currency = booking_result.get("destination_currency", "MYR")
    fx_rates = {
        "JPY": 33.0, "KRW": 290.0, "THB": 7.5, "SGD": 0.29, "IDR": 3400.0,
        "VND": 5200.0, "TWD": 6.9, "PHP": 12.2, "USD": 0.21, "EUR": 0.20,
        "GBP": 0.17, "AUD": 0.33, "CNY": 1.55, "HKD": 1.66, "INR": 17.8,
        "AED": 0.78, "MYR": 1.0,
    }
    fx = fx_rates.get(dest_currency, 1.0)
    per_person_myr = round(final_total / max(request.num_participants, 1))
    per_person_local = round(per_person_myr * fx, 2)

    split = {
        "primary_currency": "MYR",
        "destination_currency": dest_currency,
        "total_myr": final_total,
        "split_per_person_myr": per_person_myr,
        "split_per_person_local": per_person_local,
    }

    # Edge (Python, instant)
    full_data = {
        "itinerary": merged_itinerary,
        "flight_options": flight_options,
        "flights": cheapest_flight,
        "num_participants": request.num_participants,
        "participants": request.participants,
        "destination_currency": dest_currency,
        "destination_iata": booking_result.get("destination_iata", ""),
        "destination_review": booking_result.get("destination_review"),
        "estimated_total_cost_myr": final_total,
        "budget_recommendation": budget_result.get("budget_recommendation", {}),
        "budget_myr": budget_limit_myr,
        "saving_tips": budget_result.get("saving_tips", []),
        "split": split,
    }

    validated_data = orchestrator.edge.validate(full_data)
    return {"status": "success", "data": validated_data}


@app.post("/api/settle")
async def settle_balance(request: SettlementRequest):
    success, message = ledger_service.settle_payment(
        request.user_id, request.card_number
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"status": "success", "message": message}

class AmendRequest(BaseModel):
    item_type: str  # "hotel", "food", "activity"
    current_item: dict
    user_preference: str
    trip_summary: dict

@app.post("/api/amend-item")
async def amend_item(request: AmendRequest):
    try:
        result = booking_agent.amend_item(
            item_type=request.item_type,
            current_item=request.current_item,
            user_preference=request.user_preference,
            trip_summary=request.trip_summary,
        )
        return {"status": "success", "data": result}
    except AgentAPIError as e:
        raise HTTPException(status_code=502, detail=e.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount the static frontend files
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
