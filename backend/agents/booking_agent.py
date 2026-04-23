from .base_agent import BaseAgent
import datetime

class BookingAgent(BaseAgent):
    def get_details(self, compressed_draft, trip_summary):
        current_year = datetime.datetime.now().year
        dest = trip_summary.get("destination", "the destination")
        requires_flight = trip_summary.get("requires_flight", True)

        system_prompt = f"""You are the Booking Agent for DaddiesTrip. Travellers depart from KUL, Malaysia.
Current year: {current_year}.

Return a CONCISE JSON object:
{{
  "destination_currency": "<ISO>",
  "destination_iata": "<IATA>",
  "destination_review": {{"name":"...","rating":"4.x/5","review_count":"...","review_comment":"one short line"}},
  "flight_options": [/* 2 options if requires_flight=true, else [] */],
  "itinerary_details": [/* one entry per day */]
}}

FLIGHTS (if requires_flight=true):
- 2 options. "cost_myr"=per-person round-trip. departure.airport="KUL", return.airport=destination IATA.
- Include departure/return date, time, airline, airline_iata, cost_myr.
- "google_flights": "https://www.google.com/travel/flights?q=Flights+from+KUL+to+[IATA]+on+[YYYY-MM-DD]+with+[Airline]&curr=MYR&hl=en&gl=MY"

PER DAY in itinerary_details:
- "hotel": {{"name":"...","cost_myr":N,"rating":"4.x/5"}}
- "activities": [{{"name":"...","cost_myr":N,"schedule":"HH:MM-HH:MM","transport_to_next":{{"mode":"walk|bus|metro|taxi","duration":"X min","estimated_cost_myr":0}}}}]
- "food_recommendations": [{{"name":"...","avg_cost_myr":N}}]
- "daily_food_cost_myr": N
- "transportation": {{"route":"...","cost_myr":N}}

IMPORTANT: Keep responses SHORT. No long review_comments. No source URLs. Realistic costs for KUL→{dest}."""

        user_prompt = f"Trip: {trip_summary}\nItinerary to book: {compressed_draft}"
        return self.query(system_prompt, user_prompt, max_tokens=3500)
