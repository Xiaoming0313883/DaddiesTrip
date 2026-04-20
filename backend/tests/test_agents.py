import pytest
from unittest.mock import patch, MagicMock
from backend.agents.mock_agents import OrchestratorAgent
from backend.ledger.ledger_service import LedgerService

@patch('requests.post')
def test_tc01_happy_case(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": '{"itinerary": [{"day": 1, "location": "Tokyo", "activities": [{"name":"Arrival", "cost": 0, "source":"N/A"}], "daily_hotel_cost": 100, "daily_food_cost": 50, "daily_transport_cost": 20}, {"day": 2, "location": "Tokyo", "activities": [{"name":"Tour", "cost": 50, "source":"tour.com"}], "daily_hotel_cost": 100, "daily_food_cost": 50, "daily_transport_cost": 20}], "flights": {"cost": 800, "source": "flights.com"}, "estimated_total_cost": 1190, "currency": "USD", "participants": ["Alice", "Bob", "Charlie", "David"], "budget_recommendation": {"is_sufficient": true, "message": "Budget looks good."}}'
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    agent = OrchestratorAgent()
    ledger = LedgerService()
    
    prompt = "Generate an itinerary for a 2-day trip to Tokyo."
    result = agent.process_prompt(prompt)
    
    assert result["estimated_total_cost"] == 1190
    assert len(result["itinerary"]) == 2
    
    split = ledger.calculate_split(result["estimated_total_cost"], result["currency"], result["participants"])
    assert split["split_per_person"] == 297.5 # 1190 / 4

def test_tc02_negative_case():
    ledger = LedgerService()
    success, message = ledger.settle_payment("user1", "0000-1234-5678-9012")
    assert not success
    assert "Invalid card number" in message

@patch('requests.post')
def test_ai01_oversized_input(mock_post, capsys):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": '{"itinerary": [], "estimated_total_cost": 0, "currency": "USD", "participants": []}'
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    agent = OrchestratorAgent()
    oversized_prompt = "word " * 2000
    agent.process_prompt(oversized_prompt)
    
    captured = capsys.readouterr()
    assert "Triggering chunking array" in captured.out
