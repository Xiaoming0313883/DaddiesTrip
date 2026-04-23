from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.agents.mock_agents import OrchestratorAgent
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

ledger_service = LedgerService()
orchestrator = OrchestratorAgent()

@app.post("/api/plan-trip-stream")
async def plan_trip_stream(request: TripRequest):
    def event_stream():
        try:
            for event in orchestrator.process_prompt_stream(request.prompt):
                if event.get("type") == "complete":
                    # add split calculation
                    try:
                        split_data = ledger_service.calculate_split(
                            total_cost_myr=event["data"].get('estimated_total_cost_myr', 0),
                            destination_currency=event["data"].get('destination_currency', 'MYR'),
                            participants=event["data"].get('participants', [])
                        )
                        event["data"]["split"] = split_data
                    except Exception as split_err:
                        print(f"Split calculation error: {split_err}")
                        event["data"]["split"] = {
                            "primary_currency": "MYR",
                            "destination_currency": event["data"].get('destination_currency', 'MYR'),
                            "total_myr": event["data"].get('estimated_total_cost_myr', 0),
                            "split_per_person_myr": 0,
                            "split_per_person_local": 0
                        }
                yield f"data: {json.dumps(event)}\n\n"
        except AgentAPIError as e:
            print(f"Orchestration API error: {e.detail or e.user_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.user_message})}\n\n"
        except Exception as e:
            print(f"Orchestration error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'An unexpected error occurred: {type(e).__name__}. Please try again.'})}\n\n"
            
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/plan-trip")
async def plan_trip(request: TripRequest):
    try:
        # Step 1: Agent parses the prompt into itinerary and finds costs
        itinerary_data = orchestrator.process_prompt(request.prompt)
        
        # Step 2: Budget splits expenses
        split_data = ledger_service.calculate_split(
            total_cost_myr=itinerary_data['estimated_total_cost_myr'],
            destination_currency=itinerary_data['destination_currency'],
            participants=itinerary_data['participants']
        )
        
        return {
            "status": "success",
            "itinerary": itinerary_data['itinerary'],
            "flights": itinerary_data.get('flights'),
            "flight_options": itinerary_data.get('flight_options', []),
            "budget_recommendation": itinerary_data.get('budget_recommendation'),
            "destination_currency": itinerary_data.get('destination_currency', 'MYR'),
            "split": split_data
        }
    except ValueError as e:
        # Edge Case handling fallback
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/settle")
async def settle_balance(request: SettlementRequest):
    # Simulate payment settlement (TC-02)
    success, message = ledger_service.settle_payment(
        request.user_id, request.card_number
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "success", "message": message}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount the static frontend files
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
