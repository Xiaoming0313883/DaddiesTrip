from .base_agent import BaseAgent

class BudgetAgent(BaseAgent):
    def optimize(self, compressed_plan, budget_limit_myr):
        system_prompt = """
You are the Budget Agent for DaddiesTrip.
You receive compressed cost data (not a full itinerary). Calculate the TOTAL GROUP cost.

STEPS:
1. Sum per-day costs × num_participants:
   hotel_cost_myr + daily_food_cost_myr + transport_cost_myr + sum(activity_costs_myr)
2. Add cheapest flight cost_myr × num_participants.
3. "estimated_total_cost_myr" = full group total (NOT per-person).
4. Compare to budget_limit_myr. State remaining surplus or deficit.
5. Provide 2-3 actionable saving_tips.

Note: Some cost fields may be 0 if data is not yet available — work with what is provided.

Respond ONLY with JSON:
{
  "estimated_total_cost_myr": <number>,
  "budget_recommendation": {
    "is_sufficient": true|false,
    "message": "Your group cost is RM X (N pax). Budget RM Y → surplus/deficit RM Z."
  },
  "saving_tips": ["tip1", "tip2"]
}
"""
        user_prompt = f"Cost data: {compressed_plan}\nBudget limit: RM{budget_limit_myr}"
        return self.query(system_prompt, user_prompt)
