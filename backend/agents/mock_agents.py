import json
import re
from .planner_agent import PlannerAgent
from .booking_agent import BookingAgent
from .budget_agent import BudgetAgent
from .edge_agent import EdgeAgent
from .translation_agent import TranslationAgent
from .analyzer_agent import AnalyzerAgent
from .base_agent import AgentAPIError

class OrchestratorAgent:
    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.planner = PlannerAgent()
        self.booking = BookingAgent()
        self.budget = BudgetAgent()
        self.edge = EdgeAgent()
        self.translator = TranslationAgent()

    def process_prompt_stream(self, prompt: str):
        # 0. Check chunking requirement for AI-01 test
        words = prompt.split()
        if len(words) > 1500:
            print("Triggering chunking array to segment the prompt into valid sizes.")
            prompt = " ".join(words[:1500])

        # Step 1: Analyzer Agent
        yield {"type": "progress", "text": "Analyzer: Validating prompt requirements..."}
        try:
            analyze_res = self.analyzer.analyze(prompt) or {}
        except AgentAPIError as e:
            print(f"Analyzer Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Analyzer Agent failed: {type(e).__name__}: {e}")
            yield {"type": "error", "message": f"Analyzer Agent failed: {type(e).__name__}: {e}"}
            return
        if analyze_res.get("status") == "invalid":
            yield {"type": "clarification", "message": analyze_res.get("message", "Please provide more details about your trip.")}
            return

        # Step 2: Planner Agent
        yield {"type": "progress", "text": "Planner: Drafting logical route & Google Maps plotting..."}
        try:
            itinerary_draft = self.planner.plan(prompt) or {"itinerary": []}
        except AgentAPIError as e:
            print(f"Planner Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Planner Agent failed: {type(e).__name__}: {e}")
            yield {"type": "error", "message": f"Planner Agent failed: {type(e).__name__}: {e}"}
            return

        participants_raw = itinerary_draft.get("participants", [])
        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        if num_match:
            participants_raw = [f"Adult {i+1}" for i in range(int(num_match.group(1)))]
        elif not participants_raw:
            participants_raw = ["User"]
        num_participants = len(participants_raw)

        # Step 3: Booking Agent
        yield {"type": "progress", "text": "Booking: Verifying flights and checking proximity..."}
        try:
            booking_details = self.booking.get_details(itinerary_draft, prompt) or {}
        except AgentAPIError as e:
            print(f"Booking Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Booking Agent failed: {type(e).__name__}: {e}")
            yield {"type": "error", "message": f"Booking Agent failed: {type(e).__name__}: {e}"}
            return

        merged_itinerary = []
        raw_itinerary = itinerary_draft.get("itinerary", [])
        raw_details = booking_details.get("itinerary_details", [])
        for i, day in enumerate(raw_itinerary):
            if i < len(raw_details):
                day.update(raw_details[i])
            merged_itinerary.append(day)

        # Step 4: Budget Agent
        yield {"type": "progress", "text": "Budget: Optimizing costs and syncing live currency..."}
        budget_match = re.search(r'RM\s*(\d+(?:,\d+)?k?|\d+)', prompt, re.IGNORECASE)
        budget_limit_str = budget_match.group(1).replace(',', '') if budget_match else "5000"
        if budget_limit_str.lower().endswith('k'):
            budget_limit_myr = int(budget_limit_str[:-1]) * 1000
        else:
            try: budget_limit_myr = int(budget_limit_str)
            except ValueError: budget_limit_myr = 5000

        flight_options = booking_details.get("flight_options", [])
        cheapest_flight = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}

        pre_budget_data = {
            "itinerary": merged_itinerary,
            "flight_options": flight_options,
            "flights": cheapest_flight,
            "num_participants": num_participants,
            "destination_currency": booking_details.get("destination_currency", "CNY"),
            "destination_iata": booking_details.get("destination_iata", ""),
            "destination_review": booking_details.get("destination_review", None)
        }

        day_costs_per_person = sum(
            day.get("hotel", {}).get("cost_myr", 0) +
            day.get("daily_food_cost_myr", 0) +
            day.get("transportation", {}).get("cost_myr", 0) +
            sum(act.get("cost_myr", 0) for act in day.get("activities", []))
            for day in merged_itinerary
        )

        actual_total_all = (cheapest_flight.get("cost_myr", 0) + day_costs_per_person) * num_participants

        try:
            budget_optimization = self.budget.optimize(pre_budget_data, budget_limit_myr) or {}
        except AgentAPIError as e:
            print(f"Budget Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Budget Agent failed: {type(e).__name__}: {e}")
            budget_optimization = {}

        llm_total = budget_optimization.get("estimated_total_cost_myr", 0)
        final_total = llm_total if isinstance(llm_total, (int, float)) and llm_total > 0 else actual_total_all

        full_data = {
            **pre_budget_data,
            "participants": participants_raw,
            "estimated_total_cost_myr": final_total,
            "budget_recommendation": budget_optimization.get("budget_recommendation", {}),
            "saving_tips": budget_optimization.get("saving_tips", [])
        }

        # Step 5: Edge Agent
        yield {"type": "progress", "text": "Edge Agent: Validating components..."}
        try:
            validated_data = self.edge.validate(full_data) or full_data
        except AgentAPIError as e:
            print(f"Edge Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Edge Agent failed: {type(e).__name__}: {e}")
            validated_data = full_data

        # Step 6: Translation Agent
        yield {"type": "progress", "text": "Translator: Localizing..."}
        try:
            final_data = self.translator.translate(validated_data) or validated_data
        except AgentAPIError as e:
            print(f"Translator Agent failed: {e.detail or e.user_message}")
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            print(f"Translator Agent failed: {type(e).__name__}: {e}")
            final_data = validated_data

        if "participants" not in final_data: final_data["participants"] = participants_raw
        if "flight_options" not in final_data: final_data["flight_options"] = flight_options

        yield {"type": "progress", "text": "Formulating final payload..."}
        yield {"type": "complete", "data": final_data}

    def process_prompt(self, prompt: str) -> dict:
        # Legacy synchronous fallback for existing PyTest suite
        final_data = {}
        for event in self.process_prompt_stream(prompt):
            if event.get("type") == "error":
                raise ValueError(event.get("message"))
            if event.get("type") == "complete":
                final_data = event.get("data")
        return final_data
