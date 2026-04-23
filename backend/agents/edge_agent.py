from .base_agent import BaseAgent

class EdgeAgent(BaseAgent):
    def validate(self, final_json):
        """Python-only heuristic validation — no LLM call needed."""
        itinerary = final_json.get("itinerary", [])

        # Fix 1: Collect all activity costs to detect RM25 hallucination
        all_act_costs = []
        for day in itinerary:
            for act in day.get("activities", []):
                cost = act.get("cost_myr", 0)
                if cost > 0:
                    all_act_costs.append(cost)

        if len(all_act_costs) >= 3 and len(set(all_act_costs)) == 1 and all_act_costs[0] == 25:
            print("Edge: RM25 hallucination detected — zeroing activity costs for re-display")
            for day in itinerary:
                for act in day.get("activities", []):
                    if act.get("cost_myr") == 25:
                        act["cost_myr"] = 0

        # Fix 2: Detect same departure/return airport (round-trip impossibility)
        flights = final_json.get("flights", {})
        dep = (flights.get("departure", {}).get("airport") or "").upper()
        ret = (flights.get("return", {}).get("airport") or "").upper()
        if dep and ret and dep == ret:
            print(f"Edge: Same airport round-trip detected ({dep}→{ret}), flagging in metadata")
            final_json["_edge_warning"] = f"Return airport same as departure ({dep}). Verify flights."

        # Fix 3: Ensure every day has required fields
        for idx, day in enumerate(itinerary):
            if not day.get("day"):
                day["day"] = idx + 1
            if not day.get("location"):
                day["location"] = "Destination"

        return final_json
