"""
Shared utility company matching logic.

Contains the curated list of known utility companies and keyword patterns
used to identify whether a company is a utility.
"""

# --- Known utility companies (US-focused, expandable) ---
KNOWN_UTILITY_COMPANIES = {
    # Electric
    "duke energy",
    "southern company",
    "dominion energy",
    "nextera energy",
    "exelon",
    "american electric power",
    "aep",
    "entergy",
    "firstenergy",
    "xcel energy",
    "eversource energy",
    "eversource",
    "consolidated edison",
    "con edison",
    "coned",
    "pacific gas and electric",
    "pacific gas & electric",
    "pg&e",
    "pge",
    "southern california edison",
    "sce",
    "florida power & light",
    "florida power and light",
    "fpl",
    "georgia power",
    "virginia electric and power",
    "dominion virginia power",
    "commonwealth edison",
    "comed",
    "peco energy",
    "baltimore gas and electric",
    "bge",
    "pepco",
    "atlantic city electric",
    "delmarva power",
    "consumers energy",
    "dte energy",
    "dte",
    "we energies",
    "wisconsin energy",
    "alliant energy",
    "ameren",
    "evergy",
    "westar energy",
    "kansas city power and light",
    "kcpl",
    "empire district electric",
    "avista",
    "idaho power",
    "portland general electric",
    "puget sound energy",
    "pacificorp",
    "rocky mountain power",
    "tucson electric power",
    "arizona public service",
    "aps",
    "salt river project",
    "srp",
    "nevada energy",
    "nv energy",
    "hawaiian electric",
    "heco",
    "entergy arkansas",
    "entergy louisiana",
    "entergy mississippi",
    "entergy texas",
    "cleco",
    "oncor",
    "centerpoint energy",
    "atmos energy",
    "sempra energy",
    "san diego gas & electric",
    "san diego gas and electric",
    "sdg&e",
    "national grid",
    "pseg",
    "public service enterprise group",
    "ppl corporation",
    "ppl electric",
    "algonquin power",
    "avangrid",
    "cms energy",
    "pinnacle west",
    "oge energy",
    "oklahoma gas and electric",
    "black hills energy",
    "el paso electric",
    "green mountain power",
    "unitil",
    "liberty utilities",
    "new england power",
    "berkshire hathaway energy",
    "midamerican energy",
    "tampa electric",
    "teco energy",
    # Gas
    "southern union",
    "spire",
    "laclede gas",
    "new jersey resources",
    "south jersey industries",
    "southwest gas",
    "nicor gas",
    "peoples gas",
    "columbia gas",
    "nisource",
    "piedmont natural gas",
    "questar",
    "washington gas",
    "wgl holdings",
    # Water
    "american water works",
    "american water",
    "aqua america",
    "essential utilities",
    "california water service",
    "sjw group",
    "york water",
    "middlesex water",
    "artesian resources",
    "connecticut water",
    "american states water",
    "suez water",
    "veolia water",
    "veolia",
    # Multi-utility / Holding
    "berkshire hathaway energy",
    "emera",
    "fortis",
    "hydro one",
    "ontario power generation",
    "bc hydro",
    "edf energy",
    "engie",
    "iberdrola",
    "enel",
    "eon",
    "e.on",
    "rwe",
}

# --- Keywords that suggest a utility company ---
UTILITY_KEYWORDS = [
    "electric",
    "electricity",
    "power company",
    "power authority",
    "power & light",
    "power and light",
    "energy company",
    "energy corp",
    "gas & electric",
    "gas and electric",
    "public utility",
    "public utilities",
    "utility district",
    "utility commission",
    "water authority",
    "water district",
    "water company",
    "water service",
    "water works",
    "waterworks",
    "municipal utility",
    "municipal electric",
    "cooperative electric",
    "electric cooperative",
    "electric co-op",
    "rural electric",
    "light and power",
    "light & power",
    "hydro",
    "hydroelectric",
    "nuclear power",
    "transmission",
    "grid operator",
    "independent system operator",
    "iso-ne",
    "ercot",
    "caiso",
    "pjm interconnection",
    "miso energy",
    "spp",
    "natural gas",
    "gas utility",
    "sewage",
    "sewer authority",
    "wastewater",
]


def is_utility_company(company_name, extra_companies=None, extra_keywords=None):
    """Check if a company name matches a known utility or utility keyword."""
    if not company_name:
        return False

    name_lower = company_name.strip().lower()
    if not name_lower:
        return False

    # Check against known utility companies
    all_companies = KNOWN_UTILITY_COMPANIES
    if extra_companies:
        all_companies = all_companies | {c.lower().strip() for c in extra_companies}

    if name_lower in all_companies:
        return True

    # Check if any known company name is contained within the company field
    for known in all_companies:
        if known in name_lower or name_lower in known:
            return True

    # Check for keyword matches
    all_keywords = UTILITY_KEYWORDS
    if extra_keywords:
        all_keywords = all_keywords + [k.lower().strip() for k in extra_keywords]

    for keyword in all_keywords:
        if keyword in name_lower:
            return True

    return False
