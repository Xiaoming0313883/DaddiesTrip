import re


class AnalyzerAgent:
    """
    Pure Python prompt analyzer — zero LLM calls.
    Validates the 4 required trip fields using regex and keyword matching.
    This makes validation instant and 100% reliable (no LLM hallucinations).
    """

    # ── Destination Detection ──────────────────────────────────────────────
    KNOWN_DESTINATIONS = {
        # Countries
        "japan", "korea", "thailand", "vietnam", "indonesia", "singapore",
        "china", "taiwan", "philippines", "cambodia", "laos", "myanmar",
        "india", "sri lanka", "nepal", "maldives", "turkey", "egypt",
        "australia", "new zealand", "uk", "france", "italy", "spain",
        "germany", "switzerland", "netherlands", "portugal", "greece",
        "usa", "canada", "mexico", "brazil", "argentina",
        "dubai", "abu dhabi", "saudi arabia", "qatar",
        # Cities
        "tokyo", "osaka", "kyoto", "seoul", "busan", "bangkok", "phuket",
        "chiang mai", "pattaya", "krabi", "ho chi minh", "hanoi", "da nang",
        "bali", "jakarta", "yogyakarta", "singapore", "hong kong", "macau",
        "shanghai", "beijing", "guangzhou", "shenzhen", "chengdu",
        "taipei", "kaohsiung", "manila", "cebu", "boracay",
        "phnom penh", "siem reap", "vientiane", "yangon",
        "delhi", "mumbai", "goa", "jaipur", "agra",
        "colombo", "kathmandu", "male", "istanbul", "cairo",
        "sydney", "melbourne", "auckland", "queenstown",
        "london", "paris", "rome", "milan", "venice", "florence",
        "barcelona", "madrid", "lisbon", "amsterdam", "berlin", "munich",
        "zurich", "geneva", "athens", "santorini",
        "new york", "los angeles", "san francisco", "las vegas", "hawaii",
        "toronto", "vancouver", "cancun",
        "dubai", "doha", "riyadh",
        # Malaysian domestic
        "penang", "langkawi", "sabah", "sarawak", "kota kinabalu",
        "kuching", "melaka", "malacca", "johor bahru", "ipoh",
        "cameron highlands", "tioman", "redang", "perhentian",
        "terengganu", "kelantan", "pahang", "perak",
    }

    @staticmethod
    def _has_destination(text):
        """Check if a travel destination is mentioned."""
        lower = text.lower()

        # Check known destinations
        for dest in AnalyzerAgent.KNOWN_DESTINATIONS:
            # Word boundary match to avoid false positives
            if re.search(r'\b' + re.escape(dest) + r'\b', lower):
                return True

        # Check patterns like "to [Capitalized Place]", "visit [Place]", "trip to [Place]"
        if re.search(r'(?:to|visit|in|at|from|explore|go|going|travel)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text):
            return True

        return False

    @staticmethod
    def _has_dates(text):
        """Check if specific travel dates or time references are mentioned."""
        lower = text.lower()

        # ISO dates: 2025-05-01, 01/05/2025, 1-5-2025
        if re.search(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', text):
            return True

        # "1 May", "May 1", "1st May", "May 2025", "1 May 2025"
        months = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        if re.search(r'\d{1,2}\s*(?:st|nd|rd|th)?\s*' + months, lower):
            return True
        if re.search(months + r'\s+\d{1,2}', lower):
            return True
        if re.search(months + r'\s+\d{4}', lower):
            return True
        # Just month name alone (e.g., "in June", "during March")
        if re.search(r'(?:in|during|around|for|by)\s+' + months, lower):
            return True

        # Relative dates
        relative_patterns = [
            r'next\s+(?:week|month|year)',
            r'this\s+(?:week|month|weekend|coming)',
            r'end\s+of\s+(?:this|next)\s+(?:month|year)',
            r'(?:early|mid|late|beginning|end)\s+' + months,
            r'coming\s+' + months,
            r'chinese\s+new\s+year', r'cny', r'hari\s+raya', r'deepavali',
            r'christmas', r'easter', r'summer\s+(?:break|holiday|vacation)',
            r'school\s+holiday', r'semester\s+break',
        ]
        for pat in relative_patterns:
            if re.search(pat, lower):
                return True

        return False

    @staticmethod
    def _has_participants(text):
        """Check if participant count is mentioned."""
        lower = text.lower()

        # "4 adults", "2 people", "3 persons", "5 pax", "6 of us"
        if re.search(r'\d+\s*(?:adult|person|people|pax|traveler|friend|mate|buddy|member|of\s+us)', lower):
            return True

        # "group of 4", "party of 6", "family of 5"
        if re.search(r'(?:group|party|family|team|gang|crew)\s+of\s+\d+', lower):
            return True

        # Written numbers: "four adults", "two people"
        num_words = r'(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
        if re.search(num_words + r'\s*(?:adult|person|people|pax|traveler|friend|of\s+us)', lower):
            return True
        if re.search(r'(?:group|party|family)\s+of\s+' + num_words, lower):
            return True

        # "me and my wife/husband/friend/friends", "couple", "solo"
        if re.search(r'(?:me\s+and|with)\s+(?:my\s+)?(?:wife|husband|spouse|partner|friend|friends|family|colleague|brother|sister|parent)', lower):
            return True
        if re.search(r'\b(?:solo|alone|couple|duo)\b', lower):
            return True

        # "for 2", "for two" at end or before comma
        if re.search(r'for\s+(?:\d+|' + num_words + r')(?:\s|,|$)', lower):
            return True

        return False

    @staticmethod
    def _has_budget(text):
        """Check if a budget amount is mentioned."""
        lower = text.lower()

        # "RM 5000", "RM5000", "RM5k", "RM 5,000"
        if re.search(r'rm\s*[\d,]+(?:k)?', lower):
            return True

        # "MYR 5000", "5000 MYR"
        if re.search(r'(?:myr|ringgit)\s*[\d,]+', lower):
            return True
        if re.search(r'[\d,]+\s*(?:myr|ringgit)', lower):
            return True

        # "budget of 5000", "budget is 5000", "budget RM5000"
        if re.search(r'budget\s+(?:of|is|around|about|roughly|approximately)?\s*(?:rm\s*)?[\d,]+', lower):
            return True

        # Just a large number with "budget" nearby
        if 'budget' in lower and re.search(r'[\d,]{3,}', text):
            return True

        return False

    def analyze(self, user_request):
        """Validate the trip prompt instantly using Python. Returns dict."""
        missing = []

        if not self._has_destination(user_request):
            missing.append("destination")
        if not self._has_dates(user_request):
            missing.append("trip_dates")
        if not self._has_participants(user_request):
            missing.append("participants")
        if not self._has_budget(user_request):
            missing.append("budget")

        if not missing:
            return {"status": "valid", "missing_fields": [], "message": ""}

        # Build a specific message for exactly the missing fields
        field_questions = {
            "destination": "where you'd like to go",
            "trip_dates": "when you'd like to travel (specific dates or month)",
            "participants": "how many people are going",
            "budget": "your approximate budget in RM",
        }
        parts = [field_questions[f] for f in missing]

        if len(parts) == 1:
            message = f"Could you please tell us {parts[0]}?"
        elif len(parts) == 2:
            message = f"Could you please tell us {parts[0]} and {parts[1]}?"
        else:
            message = "We're missing a few details: " + ", ".join(parts[:-1]) + f", and {parts[-1]}."

        return {
            "status": "invalid",
            "missing_fields": missing,
            "message": message,
        }
