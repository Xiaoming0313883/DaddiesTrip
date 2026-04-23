from .base_agent import BaseAgent

class AnalyzerAgent(BaseAgent):
    def analyze(self, user_request):
        system_prompt = """
        You are the Analyzer Agent for DaddiesTrip.
        Your job is to read the user's travel request and determine if it contains enough valid information to plan a trip.
        Specifically, you MUST ensure the request includes:
        1. Destination
        2. Participants
        3. Trip dates (from when to when, e.g., start and end date)
        4. Budget (ensure it's not unreasonably low, e.g., 5 RM for an international trip)
        
        Respond ONLY with a JSON object:
        {
            "status": "valid" | "invalid",
            "message": "If invalid, ask a conversational question asking for the missing details (e.g., 'Could you please specify your trip date, from when to when?'). If valid, simply output 'OK'."
        }
        """
        return self.query(system_prompt, f"User Request: {user_request}")
