"""
Sales Territory Mapper
======================
Maps state locations to designated Regional Sales Representatives and target solutions.
"""

from typing import Dict, Any

# Regional Sales Representative Directory & Territory Rules
TERRITORY_DIRECTORY = {
    "MIDWEST": {
        "salesperson": "Sarah Connor",
        "email": "sarah.connor@fleet-solutions.com",
        "title": "Midwest Enterprise Account Executive",
        "states": ["IL", "IN", "MI", "OH", "WI", "MO", "IA", "MN", "ND", "SD", "NE", "KS"],
        "recommended_offering": "Fleet Compliance & Maintenance Support"
    },
    "SOUTH": {
        "salesperson": "John Doe",
        "email": "john.doe@fleet-solutions.com",
        "title": "Southern Region Fleet Replacement Specialist",
        "states": ["TX", "OK", "AR", "LA", "MS", "AL", "TN", "GA", "FL", "NC", "SC"],
        "recommended_offering": "Asset Replacement & Rapid Lease Program"
    },
    "WEST": {
        "salesperson": "Alex Rivera",
        "email": "alex.rivera@fleet-solutions.com",
        "title": "West Coast Territory Director",
        "states": ["CA", "OR", "WA", "AZ", "NV", "ID", "UT", "CO", "NM", "MT", "WY", "AK", "HI"],
        "recommended_offering": "FMCSA Regulatory Compliance & Asset Leasing"
    },
    "NORTHEAST": {
        "salesperson": "Emily Taylor",
        "email": "emily.taylor@fleet-solutions.com",
        "title": "Northeast Commercial Solutions Rep",
        "states": ["NY", "PA", "NJ", "MA", "CT", "RI", "VT", "NH", "ME", "DE", "MD", "VA", "WV"],
        "recommended_offering": "Turnkey Maintenance & Fleet Safety Consulting"
    }
}


class SalesTerritoryMapper:
    """
    Service to look up regional sales representatives by carrier state.
    """

    @staticmethod
    def get_salesperson_for_state(state_code: str) -> Dict[str, Any]:
        """
        Lookup sales representative by 2-letter state code.
        """
        if not state_code or pd_isna(state_code):
            return {
                "salesperson": "General Sales Desk",
                "email": "sales@fleet-solutions.com",
                "title": "National Sales Desk",
                "region": "National",
                "recommended_offering": "Fleet Advisory & Support Services"
            }

        state_clean = str(state_code).strip().upper()

        for region_name, info in TERRITORY_DIRECTORY.items():
            if state_clean in info["states"]:
                return {
                    "salesperson": info["salesperson"],
                    "email": info["email"],
                    "title": info["title"],
                    "region": region_name,
                    "recommended_offering": info["recommended_offering"]
                }

        # Fallback if state is international (e.g. ON, MX) or unassigned
        return {
            "salesperson": "National Accounts Manager",
            "email": "national.accounts@fleet-solutions.com",
            "title": "Commercial Fleet Account Manager",
            "region": "National / Cross-Border",
            "recommended_offering": "Custom Carrier Compliance Solutions"
        }


def pd_isna(val):
    return val is None or str(val).lower() in ['nan', 'none', 'null', '']


if __name__ == "__main__":
    mapper = SalesTerritoryMapper()
    print("TX Rep:", mapper.get_salesperson_for_state("TX"))
    print("IL Rep:", mapper.get_salesperson_for_state("IL"))
