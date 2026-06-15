# FitFindr

FitFindr is an AI thrift-shopping assistant. Give it a natural language description of what you're looking for, and it searches a secondhand listings dataset, suggests a complete outfit using your existing wardrobe, and generates a shareable social media caption for the look.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the agent end-to-end:

```bash
python agent.py
```

Run the test suite:

```bash
pytest tests/test_tools.py -v          # all tests
pytest tests/test_tools.py -m search   # search_listings only
pytest tests/test_tools.py -m outfit   # suggest_outfit only
pytest tests/test_tools.py -m fitcard  # create_fit_card only
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the 40-listing dataset for items that match what the user described. Filters by size and price first, then ranks remaining items by keyword overlap with the description.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Natural language description of the item (e.g. `"vintage graphic tee"`) |
| `size` | `str \| None` | Size string to filter by (`"M"`, `"S/M"`, `"W30"`). Case-insensitive substring match. `None` skips size filtering. |
| `max_price` | `float \| None` | Price ceiling (inclusive). `None` skips price filtering. |

**Output:** `list[dict]` — matching listings sorted by relevance score (most keyword matches first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` on no match.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given a thrifted item and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, falls back to a general styling suggestion.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` |
| `wardrobe` | `dict` | A wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. `{"items": []}` is valid. |

**Output:** `str` — a non-empty string with outfit suggestions. Never raises on an empty wardrobe.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Generates a 2–4 sentence social media caption for the thrifted outfit. Reads like an authentic OOTD post — mentions the item name, price, and platform naturally. Uses temperature 0.9 so outputs vary across calls.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Output:** `str` — a caption string, or a descriptive error message string if `outfit` is empty/whitespace. Never raises.

---

### `compare_price(item)` ⭐ stretch

**Purpose:** Estimates whether an item's price is fair by comparing it against similar listings in the dataset (same category + overlapping style tags). Falls back to category-only comparison if no tag overlap exists.

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `item` | `dict` | A listing dict (e.g. the `selected_item` from `search_listings`) |

**Output:** `dict` with keys:

| Key | Type | Description |
|---|---|---|
| `verdict` | `str` | `"great deal"`, `"fair"`, `"overpriced"`, or `"unknown"` |
| `item_price` | `float` | The item's price |
| `avg_price` | `float \| None` | Average price of comparable listings |
| `min_price` | `float \| None` | Cheapest comparable |
| `max_price` | `float \| None` | Most expensive comparable |
| `comparables` | `int` | Number of listings used for comparison |
| `note` | `str` | One-sentence plain-English explanation |

Thresholds: ≤ 80% of avg → `"great deal"`, ≤ 110% → `"fair"`, above 110% → `"overpriced"`.

---

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` orchestrates all tools in a fixed sequence, with retry logic and price comparison added as stretch steps:

`run_agent(query, wardrobe)` in `agent.py` orchestrates the three tools in a fixed sequence:

1. **Profile load** ⭐ — if an empty wardrobe is passed and a saved profile exists (`user_profile.json`), loads it automatically. The caller doesn't need to do anything differently.
2. **Parse** — calls the LLM (`parse_query`) to extract `description`, `size`, and `max_price` from the free-text user query. Stores result in `session["parsed"]`.
3. **Search with retry** ⭐ — calls `search_listings` with the parsed parameters. If no results:
   - Retry 1: drop the size filter, keep the price cap.
   - Retry 2: drop both size and price filters.
   - Each successful retry sets `session["search_note"]` with a plain-English explanation of what was loosened.
   - If all three attempts return empty, sets `session["error"]` and returns early.
4. **Select** — picks `results[0]` (highest relevance score) as `session["selected_item"]`.
5. **Price comparison** ⭐ — calls `compare_price(selected_item)`. Stores result in `session["price_comparison"]`.
6. **Outfit** — calls `suggest_outfit(selected_item, wardrobe)`. Stores result in `session["outfit_suggestion"]`.
7. **Caption** — calls `create_fit_card(outfit_suggestion, selected_item)`. Stores result in `session["fit_card"]`.
8. **Return** — returns the full session dict. Caller checks `session["error"]` first, then optionally surfaces `session["search_note"]` and `session["price_comparison"]` in the UI.

⭐ = stretch feature

---

## State Management

All state lives in a single `session` dict initialized by `_new_session(query, wardrobe)` at the start of each `run_agent` call. No global variables are used.

```python
session = {
    "query": query,              # original user input, never mutated
    "parsed": {},                # output of parse_query — description, size, max_price
    "search_results": [],        # full list returned by search_listings
    "selected_item": None,       # results[0], passed to suggest_outfit and create_fit_card
    "wardrobe": wardrobe,        # passed through unchanged to suggest_outfit
    "outfit_suggestion": None,   # string returned by suggest_outfit
    "fit_card": None,            # string returned by create_fit_card
    "price_comparison": None,    # ⭐ dict returned by compare_price
    "search_note": None,         # ⭐ set when retry logic loosened the search constraints
    "error": None,               # set on early exit; all other output fields stay None
}
```

Each tool writes its output into the session immediately after returning, before the next tool is called. This means any tool can inspect what the previous tool produced by reading from the session rather than relying on local variables.

---

## Error Handling

| Tool | Failure mode | Handling | Concrete example |
|---|---|---|---|
| `search_listings` | No listings match the query | Returns `[]`. The agent sets `session["error"]` and returns the session early. | Query `"designer ballgown size XXS under $5"` — no ballgowns exist and nothing is under $5, so `search_listings` returns `[]` and the agent exits before calling `suggest_outfit`. Tested in `test_search_empty_results`. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Does not raise. Switches to a general styling prompt: asks the LLM what common staples pair well with the item rather than referencing specific wardrobe pieces. | Called with `get_empty_wardrobe()` on the Y2K Baby Tee — returned two complete outfit suggestions using common staples (white tee, straight-leg jeans, chunky sneakers) with no wardrobe references. Tested in `test_suggest_outfit_empty_wardrobe`. |
| `create_fit_card` | `outfit` is an empty or whitespace-only string | Guards before making any LLM call. Returns an error message string immediately. | `create_fit_card("", item)` and `create_fit_card("   ", item)` both returned the error string without raising. Tested in `test_create_fit_card_empty_outfit` and `test_create_fit_card_whitespace_outfit`. |
| `compare_price` ⭐ | No comparable listings in dataset | Returns `verdict: "unknown"` and `None` for all price fields. Does not raise. | An item in a category with only one other listing (e.g. a rare shoe size) returns `"unknown"` if that single listing is itself — the self-exclusion logic leaves zero comparables. |
| Retry logic ⭐ | Size + price filters together return no results | Stage 1: retries without size. Stage 2: retries without size or price. Sets `session["search_note"]` to explain what was loosened. | Query `"vintage tee size XS under $5"` — no XS items under $5 exist. Retry 1 (drop size) also found nothing. Retry 2 (drop both) found the Y2K Baby Tee. `session["search_note"]` was set to `"No results found for size XS under $5.0 — showing results without filters."` |

---

## Stretch Features

### Price Comparison (`compare_price` in `tools.py`)

Automatically called on `selected_item` during every agent run. The result lives in `session["price_comparison"]` and can be surfaced directly in the UI:

```python
pc = session["price_comparison"]
print(pc["verdict"])   # "great deal" / "fair" / "overpriced"
print(pc["note"])      # "At $18.0, this is priced close to the $22.0 average for similar tops."
```

### Style Profile Memory (`utils/profile.py`)

Saves and loads a user's wardrobe and style notes to `user_profile.json` in the project root so they persist across sessions.

```python
from utils.profile import save_profile, load_profile

# After the user sets up their wardrobe — save it
save_profile(wardrobe=get_example_wardrobe(), style_notes="I love Y2K and cottagecore.")

# Next session — load it back
profile = load_profile()
wardrobe = profile["wardrobe"]
notes    = profile["style_notes"]
```

`run_agent` loads the profile automatically if an empty wardrobe is passed and `user_profile.json` exists — no changes needed at the call site.

### Retry Logic with Fallback (`run_agent` in `agent.py`)

When `search_listings` returns no results, the agent retries up to two times with progressively looser constraints instead of immediately erroring:

1. Drop size filter → retry
2. Drop size and price cap → retry
3. If still empty → set `session["error"]`

The UI can read `session["search_note"]` to tell the user what was adjusted:

```python
if session["search_note"]:
    print(session["search_note"])
# → "No results found for size XS under $5.0 — showing results without filters."
```

---

## Spec Reflection

**What matched the spec:**
The three-tool pipeline in `planning.md` mapped cleanly to the implementation. The linear planning loop — parse → search → outfit → caption — required no structural changes from what was planned. The session dict fields were defined in the spec and used as-is in the code.

**What changed from the spec:**
- `search_listings` was originally specced to return an explicit `"Unfortunately I don't see any listing matching your request"` string on no match. The implementation returns `[]` instead and moves the user-facing message to the agent layer — this makes the function easier to test and reuse.
- `parse_query` was listed as a planning decision in the spec but not assigned to a specific tool. The LLM-based approach was chosen over regex and string splitting because user queries are conversational and inconsistently formatted.
- The model was changed from `llama3-8b-8192` (decommissioned) to `llama-3.3-70b-versatile` mid-implementation.

**What was harder than expected:**
Unpacking the `parse_query` result correctly — the initial implementation passed the whole dict to `search_listings` instead of spreading its keys, which caused an `AttributeError` at runtime.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

**Input to AI:** The full Tool 1 spec from `planning.md` (inputs, return type, failure mode, the 5-step TODO in the docstring), plus the field names from `data/listings.json`.

**What it produced:** A complete implementation using `load_listings()`, hard filters for price and size, and a keyword-overlap scoring function that tokenised both the query and each listing's searchable fields with `re.findall`.

**What was changed:** The initial implementation used `" ".join(searchable_parts)` before filtering out `None` values, which crashed on listings where `brand` is `null` in the JSON. Added `filter(lambda x: x is not None, searchable_parts)` before the join. Also overrode the model name after the original (`llama3-8b-8192`) was decommissioned.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**Input to AI:** The Planning Loop section of `planning.md`, the Architecture ASCII diagram, the State Management section, and the `_new_session` dict definition — plus the three completed tool signatures from `tools.py`.

**What it produced:** A `run_agent` function with the correct step sequence and a `parse_query` helper using the LLM approach. The session dict was initialized and populated at each step.

**What was changed:** Two bugs were introduced that required manual fixes:
1. `search_listings(session["parsed"])` passed the dict directly instead of unpacking it — corrected to `search_listings(parsed["description"], size=parsed.get("size"), max_price=parsed.get("max_price"))`.
2. The early-exit branch on no results used `return` instead of `return session`, which would have caused a `TypeError` on `session2["error"]` in the no-results test path — corrected to `return session`.
