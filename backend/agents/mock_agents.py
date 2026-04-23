import json
import re
import time
from .planner_agent import PlannerAgent
from .booking_agent import BookingAgent
from .edge_agent import EdgeAgent
from .analyzer_agent import AnalyzerAgent
from .base_agent import AgentAPIError


class OrchestratorAgent:
    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.planner = PlannerAgent()
        self.booking = BookingAgent()
        self.edge = EdgeAgent()

    # ─── Context Compression Helpers ────────────────────────────────────────────

    @staticmethod
    def _build_trip_summary(prompt, itinerary_draft):
        """Compact dict (~50 tokens) to replace full prompt in downstream agents."""
        itinerary = itinerary_draft.get("itinerary", [])
        destination = itinerary[0].get("location", "Unknown") if itinerary else "Unknown"

        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        num_pax = int(num_match.group(1)) if num_match else len(itinerary_draft.get("participants", [])) or 1

        budget_match = re.search(r'RM\s*(\d+(?:,\d+)?k?|\d+)', prompt, re.IGNORECASE)
        budget_str = budget_match.group(1).replace(',', '') if budget_match else "5000"
        if budget_str.lower().endswith('k'):
            budget_myr = int(budget_str[:-1]) * 1000
        else:
            try:
                budget_myr = int(budget_str)
            except ValueError:
                budget_myr = 5000

        return {
            "destination": destination,
            "duration_days": len(itinerary),
            "participants": num_pax,
            "budget_myr": budget_myr,
            "depart_from": "KUL",
            "requires_flight": itinerary_draft.get("requires_flight", True),
        }

    @staticmethod
    def _compress_for_booking(itinerary_draft):
        """Strip non-essential planner fields before sending to BookingAgent."""
        return {
            "requires_flight": itinerary_draft.get("requires_flight", True),
            "itinerary": [
                {
                    "day": d.get("day"),
                    "location": d.get("location"),
                    "activities": [
                        {"name": a.get("name"), "schedule": a.get("schedule")}
                        for a in d.get("activities", [])
                    ],
                }
                for d in itinerary_draft.get("itinerary", [])
            ],
        }

    @staticmethod
    def _compress_for_budget(merged_itinerary, flight_options, num_participants, budget_limit_myr):
        """Send only cost fields to BudgetAgent — strips URLs, reviews, etc."""
        return {
            "num_participants": num_participants,
            "budget_limit_myr": budget_limit_myr,
            "flight_options": [
                {"airline": f.get("airline"), "cost_myr": f.get("cost_myr", 0)}
                for f in flight_options
            ],
            "days": [
                {
                    "day": d.get("day"),
                    "hotel_cost_myr": (d.get("hotel") or {}).get("cost_myr", 0),
                    "daily_food_cost_myr": d.get("daily_food_cost_myr", 0),
                    "transport_cost_myr": (d.get("transportation") or {}).get("cost_myr", 0),
                    "activity_costs_myr": [a.get("cost_myr", 0) for a in d.get("activities", [])],
                }
                for d in merged_itinerary
            ],
        }

    @staticmethod
    def _calculate_budget(merged_itinerary, flight_options, num_participants, budget_limit_myr):
        """Pure Python budget calculation — no LLM needed."""
        cheapest = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}
        flight_pp = cheapest.get("cost_myr", 0)
        day_pp = sum(
            (d.get("hotel") or {}).get("cost_myr", 0)
            + d.get("daily_food_cost_myr", 0)
            + (d.get("transportation") or {}).get("cost_myr", 0)
            + sum(a.get("cost_myr", 0) for a in d.get("activities", []))
            for d in merged_itinerary
        )
        total = round((flight_pp + day_pp) * num_participants)
        surplus = budget_limit_myr - total
        is_ok = surplus >= 0
        tips = (
            [
                "Book flights 3–4 weeks ahead for better rates.",
                "Eat at local hawker stalls to save RM30–60/day per person.",
                "Choose a 3-star hotel to cut accommodation costs by ~40%.",
            ]
            if not is_ok else
            [
                "You have budget headroom — consider travel insurance for peace of mind.",
                "Pre-book popular attractions online to avoid queue surcharges.",
            ]
        )
        return {
            "estimated_total_cost_myr": total,
            "budget_recommendation": {
                "is_sufficient": is_ok,
                "message": (
                    f"Group total: RM{total:,} ({num_participants} pax). "
                    f"Budget: RM{budget_limit_myr:,} → "
                    f"{'Surplus' if is_ok else 'Deficit'} RM{abs(surplus):,}."
                ),
            },
            "saving_tips": tips,
        }

    # ─── Deep Merge Helper ──────────────────────────────────────────────────────

    @staticmethod
    def _merge_itineraries(raw_itinerary, raw_details):
        details_by_day = {d.get("day"): d for d in raw_details if d.get("day") is not None}
        merged = []
        for idx, day in enumerate(raw_itinerary):
            if not day.get("day"):
                day["day"] = idx + 1
            if not day.get("location"):
                day["location"] = "Destination"

            detail = details_by_day.get(day["day"]) or (raw_details[idx] if idx < len(raw_details) else {})
            booking_acts = detail.get("activities")
            if booking_acts:
                planner_by_name = {a.get("name", ""): a for a in day.get("activities", [])}
                day["activities"] = [
                    {**planner_by_name.get(b.get("name", ""), {}), **b}
                    for b in booking_acts
                ]
            for key, val in detail.items():
                if key != "activities":
                    day[key] = val
            merged.append(day)
        return merged

    # ─── Main Stream ────────────────────────────────────────────────────────────

    def process_prompt_stream(self, prompt: str):
        # Truncate runaway prompts
        words = prompt.split()
        if len(words) > 1500:
            prompt = " ".join(words[:1500])

        # ── Step 1: Analyzer (serial — must validate before anything else) ──────
        yield {"type": "progress", "text": "Validating your request..."}
        t0 = time.time()
        try:
            analyze_res = self.analyzer.analyze(prompt) or {}
        except AgentAPIError as e:
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Analyzer failed: {e}"}
            return
        print(f"⏱️ Analyzer: {time.time() - t0:.1f}s")

        if analyze_res.get("status") == "invalid":
            yield {
                "type": "clarification",
                "message": analyze_res.get("message", "Please provide more details about your trip."),
                "missing_fields": analyze_res.get("missing_fields", []),
            }
            return

        # ── Step 2: Planner (serial — Booking needs its output) ──────────────────
        yield {"type": "progress", "text": "Planning your itinerary route..."}
        t1 = time.time()
        try:
            itinerary_draft = self.planner.plan(prompt) or {"itinerary": []}
        except AgentAPIError as e:
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Planner failed: {e}"}
            return
        print(f"⏱️ Planner: {time.time() - t1:.1f}s")

        # Participants
        participants_raw = itinerary_draft.get("participants", [])
        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        if num_match:
            participants_raw = [f"Adult {i+1}" for i in range(int(num_match.group(1)))]
        elif not participants_raw:
            participants_raw = ["User"]
        num_participants = len(participants_raw)

        trip_summary = self._build_trip_summary(prompt, itinerary_draft)
        budget_limit_myr = trip_summary["budget_myr"]

        # ── Stream partial itinerary skeleton immediately ─────────────────────────
        partial_days = [
            {
                "day": d.get("day") or (i + 1),
                "location": d.get("location") or "Destination",
                "activities": d.get("activities", []),
            }
            for i, d in enumerate(itinerary_draft.get("itinerary", []))
        ]
        yield {"type": "partial_itinerary", "days": partial_days, "num_participants": num_participants}

        # ── Step 3: Sequential execution ─────────────────────────────────────────
        yield {"type": "progress", "text": "Searching flights, hotels & activities..."}

        compressed_draft = self._compress_for_booking(itinerary_draft)
        booking_result = {}
        booking_error = None

        t2 = time.time()
        try:
            booking_result = self.booking.get_details(compressed_draft, trip_summary) or {}
        except AgentAPIError as e:
            booking_error = e.user_message
        except Exception as e:
            booking_error = f"Booking failed: {e}"
            print(f"Booking Agent error: {e}")
        print(f"⏱️ Booking: {time.time() - t2:.1f}s")

        if booking_error:
            yield {"type": "error", "message": booking_error}
            return

        # ── Stream partial flights immediately after booking ──────────────────────
        flight_options = booking_result.get("flight_options", [])
        if flight_options:
            yield {
                "type": "partial_flights",
                "flight_options": flight_options,
                "num_participants": num_participants,
            }

        yield {"type": "progress", "text": "Finalising costs and merging results..."}

        # ── Merge planner + booking ───────────────────────────────────────────────
        merged_itinerary = self._merge_itineraries(
            itinerary_draft.get("itinerary", []),
            booking_result.get("itinerary_details", []),
        )

        cheapest_flight = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}

        # ── Step 3b: Python-side Budget (instant, no LLM) ────────────────────────
        budget_result = self._calculate_budget(
            merged_itinerary, flight_options, num_participants, budget_limit_myr
        )
        final_total = budget_result["estimated_total_cost_myr"]

        # ── Step 4: Edge Agent (Python-only, instant) ─────────────────────────────
        full_data = {
            "itinerary": merged_itinerary,
            "flight_options": flight_options,
            "flights": cheapest_flight,
            "num_participants": num_participants,
            "participants": participants_raw,
            "destination_currency": booking_result.get("destination_currency", "MYR"),
            "destination_iata": booking_result.get("destination_iata", ""),
            "destination_review": booking_result.get("destination_review"),
            "estimated_total_cost_myr": final_total,
            "budget_recommendation": budget_result.get("budget_recommendation", {}),
            "saving_tips": budget_result.get("saving_tips", []),
        }

        validated_data = self.edge.validate(full_data)
        yield {"type": "complete", "data": validated_data}

    def process_prompt(self, prompt: str) -> dict:
        """Legacy sync wrapper for test suite."""
        final_data = {}
        for event in self.process_prompt_stream(prompt):
            if event.get("type") == "error":
                raise ValueError(event.get("message"))
            if event.get("type") == "complete":
                final_data = event.get("data")
        return final_data
