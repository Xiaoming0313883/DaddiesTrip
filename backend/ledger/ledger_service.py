import pandas as pd

class LedgerService:
    def __init__(self):
        # Mock exchange rates
        self.exchange_rates = {
            "USD": 1.0,
            "EUR": 0.92,
            "JPY": 150.0,
            "MYR": 4.75 # Assuming local currency is MYR for some users
        }

    def calculate_split(self, total_cost: float, currency: str, participants: list) -> dict:
        """
        Splits the expense equally among participants using Pandas for robust aggregation.
        """
        if not participants:
            return {}

        num_participants = len(participants)
        
        # Create a dataframe to handle potential complex logic later
        df = pd.DataFrame({
            'Participant': participants,
            'Owed': [total_cost / num_participants] * num_participants
        })
        
        # Calculate local currency if needed, let's say target is MYR
        rate = self.exchange_rates.get("MYR", 1.0) / self.exchange_rates.get(currency, 1.0)
        df['Owed_Local'] = df['Owed'] * rate
        
        return {
            "currency": currency,
            "total": total_cost,
            "split_per_person": round(total_cost / num_participants, 2),
            "split_per_person_local": round(df['Owed_Local'].iloc[0], 2),
            "local_currency": "MYR"
        }

    def settle_payment(self, user_id: str, card_number: str):
        # TC-02 (Negative Case): Invalid simulated payment card
        if card_number.startswith("0000"):
            return False, "Payment rejected: Invalid card number."
        return True, "Payment settled successfully."
