from .base_agent import BaseAgent
import datetime

class BookingAgent(BaseAgent):
    def get_details(self, itinerary_draft, user_request):
        current_year = datetime.datetime.now().year
        yy = str(current_year)[2:]
        system_prompt = f"""
        You are the Booking Agent for DaddiesTrip, serving Malaysian travellers departing from KUL.
        Current year is {current_year}. ALL dates must be in {current_year} or later.

        CRITICAL RULES - VIOLATIONS WILL BE REJECTED:

        1. FLIGHTS:
           - Check the 'requires_flight' flag from the planner. If false, output an empty array: "flight_options": [].
           - If requires_flight is true: Departure MUST always be "KUL" (Kuala Lumpur International Airport).
           - Return airport MUST be the destination IATA code.
           - Provide EXACTLY 3 flight options with DIFFERENT airlines.
           - Include "airline_iata" precisely (e.g. "AK" for AirAsia, "TR" for Scoot, "MH" for Malaysia Airlines).
           - "cost_myr" is the PER-PERSON round-trip price in MYR. Must be realistic for KUL to that destination.
           - Departure and return are separate objects with separate date and time.
           - For EACH flight option provide TWO verification links:
             a) Skyscanner with specific dates:
                https://www.skyscanner.com.my/transport/flights/kul/[DEST_IATA]/{yy}MMDD/{yy}MMDD/
                Use the ACTUAL departure and return dates from the itinerary in YYMMDD format.
             b) Google Flights with specific dates and airline:
                https://www.google.com/travel/flights?q=Flights+from+KUL+to+[DEST_IATA]+on+[YYYY-MM-DD]+with+[AIRLINE_NAME]&curr=MYR
                Use the ACTUAL departure date and airline name.

        2. DESTINATION REVIEW:
           - Include "destination_review" at top level with: name, rating (e.g. "4.7/5"), review_count, review_comment.

        3. HOTELS:
           - Different hotel each day unless genuinely staying in one city.
           - Real hotel names in the destination city.
           - "cost_myr" is PER-NIGHT PER-ROOM price. Assume 1 room per 2 adults.
           - Include "rating", "review_comment", and "source" (Google Maps link) for EACH hotel.

        4. ACTIVITIES & TICKETS:
           - NEVER use RM25 as default. Use realistic prices.
           - "cost_myr" is PER-PERSON price.
           - If free: name it "Attraction Name (Free Entry)", cost_myr = 0.
           - If ticket required: name it "Attraction Name (Ticket Required)" with real cost.
           - Include "source" (Google Maps link), "rating", "review_comment" for each.

        5. FOOD:
           - Specific restaurant names, not generic.
           - "avg_cost_myr" is PER-PERSON per meal.
           - Include "rating", "review_comment", "price_range" (e.g. "$", "$$"), "source" (Google Maps link).

        6. TRANSPORTATION:
           - "cost_myr" is PER-PERSON per day.

        Respond ONLY with valid JSON:
        {{
            "destination_currency": "SGD",
            "destination_iata": "SIN",
            "destination_review": {{
                "name": "Singapore",
                "rating": "4.7/5",
                "review_count": "125,000",
                "review_comment": "A vibrant city-state known for its stunning skyline and world-class food scene."
            }},
            "flight_options": [
                {{
                    "airline": "AirAsia",
                    "airline_iata": "AK",
                    "cost_myr": 350,
                    "departure": {{"airport": "KUL", "time": "08:00", "arrival_time": "09:05", "date": "{current_year}-06-01"}},
                    "return": {{"airport": "SIN", "time": "22:00", "arrival_time": "23:05", "date": "{current_year}-06-07"}},
                    "source": "https://www.skyscanner.com.my/transport/flights/kul/sin/{yy}0601/{yy}0607/",
                    "google_flights": "https://www.google.com/travel/flights?q=Flights+from+KUL+to+SIN+on+{current_year}-06-01+with+AirAsia&curr=MYR"
                }},
                {{
                    "airline": "Malaysia Airlines",
                    "airline_iata": "MH",
                    "cost_myr": 580,
                    "departure": {{"airport": "KUL", "time": "10:30", "arrival_time": "11:35", "date": "{current_year}-06-01"}},
                    "return": {{"airport": "SIN", "time": "19:00", "arrival_time": "20:05", "date": "{current_year}-06-07"}},
                    "source": "https://www.skyscanner.com.my/transport/flights/kul/sin/{yy}0601/{yy}0607/",
                    "google_flights": "https://www.google.com/travel/flights?q=Flights+from+KUL+to+SIN+on+{current_year}-06-01+with+Malaysia+Airlines&curr=MYR"
                }},
                {{
                    "airline": "Scoot",
                    "airline_iata": "TR",
                    "cost_myr": 280,
                    "departure": {{"airport": "KUL", "time": "06:15", "arrival_time": "07:20", "date": "{current_year}-06-01"}},
                    "return": {{"airport": "SIN", "time": "21:30", "arrival_time": "22:35", "date": "{current_year}-06-07"}},
                    "source": "https://www.skyscanner.com.my/transport/flights/kul/sin/{yy}0601/{yy}0607/",
                    "google_flights": "https://www.google.com/travel/flights?q=Flights+from+KUL+to+SIN+on+{current_year}-06-01+with+Scoot&curr=MYR"
                }}
            ],
            "itinerary_details": [
                {{
                    "day": 1,
                    "hotel": {{
                        "name": "Hotel 81 Orchid",
                        "cost_myr": 180,
                        "rating": "4.0/5",
                        "review_comment": "Budget-friendly, clean rooms near Geylang.",
                        "source": "https://www.google.com/maps/search/Hotel+81+Orchid+Singapore"
                    }},
                    "transportation": {{"route": "MRT from Changi to City Hall (40 min)", "cost_myr": 8}},
                    "activities": [
                        {{"name": "Gardens by the Bay (Ticket Required)", "cost_myr": 35, "source": "https://www.google.com/maps/search/Gardens+by+the+Bay+Singapore", "rating": "4.8/5", "review_comment": "Amazing light show and futuristic trees.", "review_count": "95,000"}},
                        {{"name": "Marina Bay Sands SkyPark (Ticket Required)", "cost_myr": 26, "source": "https://www.google.com/maps/search/Marina+Bay+Sands+SkyPark+Singapore", "rating": "4.6/5", "review_comment": "Breathtaking city views.", "review_count": "42,000"}}
                    ],
                    "food_recommendations": [
                        {{"name": "Lau Pa Sat", "rating": "4.3/5", "review_comment": "Great satay street at night.", "avg_cost_myr": 20, "price_range": "$$", "source": "https://www.google.com/maps/search/Lau+Pa+Sat+Singapore"}},
                        {{"name": "Maxwell Food Centre", "rating": "4.5/5", "review_comment": "Famous for Tian Tian Chicken Rice.", "avg_cost_myr": 8, "price_range": "$", "source": "https://www.google.com/maps/search/Maxwell+Food+Centre+Singapore"}}
                    ]
                }}
            ]
        }}
        """
        user_prompt = f"Itinerary Draft: {itinerary_draft}\nOriginal Request: {user_request}"
        return self.query(system_prompt, user_prompt)
