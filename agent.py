"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card, compare_price, _get_groq_client
from dotenv import load_dotenv
from utils.profile import load_profile, save_profile, profile_exists
import json

load_dotenv()



# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "price_comparison": None,    # dict returned by compare_price
        "search_note": None,         # set if retry logic loosened the constraints
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────
def parse_query(query: str) -> dict:
    client = _get_groq_client()
    prompt = (
        "Extract search parameters from this thrift shopping query. "
        "Reply with ONLY a JSON object with keys: description (str), size (str or null), max_price (float or null).\n\n"
        f"Query: {query}"
    )
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    
    user_query = json.loads(response.choices[0].message.content)
    print(user_query)
    return user_query
    
def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # ── Load saved profile if no wardrobe was passed ─────────────────────────
    if not wardrobe.get("items") and profile_exists():
        profile = load_profile()
        wardrobe = profile["wardrobe"]
        print(f"Loaded saved profile (last saved: {profile.get('saved_at', 'unknown')})")

    session = _new_session(query, wardrobe)
    session["parsed"] = parse_query(session["query"])

    parsed = session["parsed"]

    # ── Search with retry / fallback logic ───────────────────────────────────
    matches = search_listings(
        parsed["description"],
        size=parsed.get("size"),
        max_price=parsed.get("max_price"),
    )

    if not matches and parsed.get("size"):
        # Retry 1: drop size filter
        matches = search_listings(parsed["description"], size=None, max_price=parsed.get("max_price"))
        if matches:
            session["search_note"] = (
                f"No results found for size {parsed['size']} — "
                "showing results for all sizes instead."
            )

    if not matches and parsed.get("max_price"):
        # Retry 2: drop price cap too
        matches = search_listings(parsed["description"], size=None, max_price=None)
        if matches:
            session["search_note"] = (
                f"No results found for size {parsed.get('size') or 'any'} under "
                f"${parsed['max_price']} — showing results without filters."
            )

    if not matches:
        session["error"] = (
            "Unfortunately the database currently doesn't contain a good match. "
            "Try using different keywords."
        )
        return session

    session["search_results"] = matches
    session["selected_item"] = matches[0]

    # ── Price comparison ──────────────────────────────────────────────────────
    session["price_comparison"] = compare_price(session["selected_item"])

    # ── Outfit suggestion ─────────────────────────────────────────────────────
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], wardrobe)

    # ── Fit card ──────────────────────────────────────────────────────────────
    if len(session["outfit_suggestion"]) < 10:
        session["fit_card"] = "There isn't enough information on an outfit with this piece."
    else:
        session["fit_card"] = create_fit_card(session["outfit_suggestion"], session["selected_item"])

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
