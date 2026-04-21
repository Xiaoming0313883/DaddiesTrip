from .base_agent import BaseAgent

class AnalyzerAgent(BaseAgent):
    def analyze(self, user_request):
        system_prompt = """
        You are the Analyzer Agent for DaddiesTrip.
        Your job is to read the user's travel request and determine if it contains enough valid information to plan a trip (such as destination, participants), and ensure the budget is not unreasonably low (e.g. 5 RM for an international trip).
        
        Respond ONLY with a JSON object:
        {
            "status": "valid" | "invalid",
            "message": "If invalid, ask a conversational question asking for the missing details (e.g., 'your budget seems too low for this trip, could you provide a higher budget?'). If valid, simply output 'OK'."
        }
        """
        return self.query(system_prompt, f"User Request: {user_request}")
