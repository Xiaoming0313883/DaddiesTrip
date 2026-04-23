from .base_agent import BaseAgent

class PlannerAgent(BaseAgent):
    def plan(self, user_request):
        system_prompt = """
        You are the Planner Agent for DaddiesTrip.
        Create a high-level logical itinerary JSON.
        
        RULES:
        1. MANDATORY: "day" (int), "location" (string), "requires_flight" (bool).
        2. Activities: include "name", "schedule" (e.g. 09:00-11:30), "cost_myr", "source" (Google Maps link).
        3. Transport: Each activity needs "transport_to_next": {"mode":"walk|bus|metro|taxi", "duration":"X min", "estimated_cost_myr":0, "notes":"..."}. Null if last activity.
        4. Include "participants" (array), "food_recommendations" (array), "weather_advice" (string).
        5. Output ONLY valid JSON.
        """
        return self.query(system_prompt, f"User Request: {user_request}")

