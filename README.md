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

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` orchestrates the three tools in a fixed sequence:

1. **Parse** — calls the LLM (`parse_query`) to extract `description`, `size`, and `max_price` from the free-text user query. Stores result in `session["parsed"]`.
2. **Search** — calls `search_listings` with the parsed parameters. Stores results in `session["search_results"]`. If the list is empty, sets `session["error"]` and returns early — the remaining tools are skipped.
3. **Select** — picks `results[0]` (highest relevance score) as `session["selected_item"]`.
4. **Outfit** — calls `suggest_outfit(selected_item, wardrobe)`. Stores result in `session["outfit_suggestion"]`.
5. **Caption** — calls `create_fit_card(outfit_suggestion, selected_item)`. Stores result in `session["fit_card"]`.
6. **Return** — returns the full session dict. Caller checks `session["error"]` first.

The loop is linear and non-iterative — each step feeds directly into the next with no branching after the early-exit check in Step 2.

---

## State Management

All state lives in a single `session` dict initialized by `_new_session(query, wardrobe)` at the start of each `run_agent` call. No global variables are used.

```python
session = {
    "query": query,             # original user input, never mutated
    "parsed": {},               # output of parse_query — description, size, max_price
    "search_results": [],       # full list returned by search_listings
    "selected_item": None,      # results[0], passed to suggest_outfit and create_fit_card
    "wardrobe": wardrobe,       # passed through unchanged to suggest_outfit
    "outfit_suggestion": None,  # string returned by suggest_outfit
    "fit_card": None,           # string returned by create_fit_card
    "error": None,              # set on early exit; all other output fields stay None
}
```

Each tool writes its output into the session immediately after returning, before the next tool is called. This means any tool can inspect what the previous tool produced by reading from the session rather than relying on local variables.

---

## Error Handling

| Tool | Failure mode | Handling | Concrete example |
|---|---|---|---|
| `search_listings` | No listings match the query | Returns `[]`. The agent sets `session["error"] = "Unfortunately the database currently doesn't contain a good match. Try using a different query."` and returns the session early. | Query `"designer ballgown size XXS under $5"` — the dataset has no ballgowns and no items under $5, so `search_listings` returns `[]` and the agent exits before calling `suggest_outfit`. Tested in `test_search_empty_results`. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Does not raise. Switches to a general styling prompt: asks the LLM what common staples pair well with the item rather than referencing specific wardrobe pieces. | Called with `get_empty_wardrobe()` on the Y2K Baby Tee — returned two complete outfit suggestions using common staples (white tee, straight-leg jeans, chunky sneakers) with no wardrobe references. Tested in `test_suggest_outfit_empty_wardrobe`. |
| `create_fit_card` | `outfit` is an empty or whitespace-only string | Guards before making any LLM call. Returns `"There isn't enough information on an outfit with this piece."` immediately. | `create_fit_card("", item)` and `create_fit_card("   ", item)` both returned the error string without raising. Tested in `test_create_fit_card_empty_outfit` and `test_create_fit_card_whitespace_outfit`. |

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
