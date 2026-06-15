# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
This function receives user input -- `description, size, max_price`. Given these information, it searches through listing dataset to find items that match the desired description, size and price. If no matches are found, it returns an explicit message "Unfortunately I don't see any listing matching your request".

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): a string describing desired item
- `size` (str): size information such as XS, S, M, L, etc.
- `max_price` (float): the max price user is willing to spend for this listing. If everything else matches but the price exceeds max_price, it's not a match. If it's set to None, no price filtering is applied.

**What it returns:**
Returns a list of dicts, each dict contains details of the listing, including id, title, description, category, style_tags (list), size,condition, price (float), colors (list), brand, platform. 

The list should be sorted by relevance to prompt. 

**What happens if it fails or returns nothing:**
Returns an empty list.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific item with details and the user's wardrobe, this function should suggest one or more complete outfit combinations.


**Input parameters:**
- `new_item` (dict): a listing dict
- `wardrobe` (dict): a wardrobe dict, with a `items` key assigned to a list of wardrobe item dicts. 

**What it returns:**
a string that contains outfit suggestions

**What happens if it fails or returns nothing:**
If the wardrobe is empty or no outfit can be suggested, the agent should return general outfits for `new_item`. 

---

### Tool 3: create_fit_card

**What it does:**
This function creates a social media caption based on the new outfit including the thrifted new item. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): an agent generated string containing a new outfit
- `new_item` (dict): the listing for new item

**What it returns:**
This function returns a 2-4 sentence string as a social media caption. It should read like an authentic post, capture the outfit vibe, mention the new item's metadata (name, price and platform) and vary for different outputs. 

**What happens if it fails or returns nothing:**
If the outfit is empty or missing, the function returns an error message (still outputs a string).

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

- user query comes through gradio interface
- run `search_listings()`
     - check if results is empty
          - If yes, set an error message in the session and return early. 
          - If no, set selected_item = results[0] and proceed to suggest_outfit.
- call `suggest_outfit(selected_item, wardrobe)`
     - check if wardrobe is empty
          - If yes, request a generic fit suggestion based on selected_item
          - If not, join wardrobe and selected_item as context to the LLM prompt, and request for a suggestion with both information
     - return a string describing a fit
- call `create_fit_card()` based on previous two outputs
     - If outfit string is empty, return an error message
     - Prompt agent to consider item and outfit as input, and generate a caption
     - return response

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Unfortunately the database currently doesn't contain a good match. Try switching keywords? |
| suggest_outfit | Wardrobe is empty | suggest a generic outfit based on new_item |
| create_fit_card | Outfit input is missing or incomplete | There isn't enough information on an outfit with this piece. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │ wardrobe={'items':[]}                      │
    │       ├──► prompt: outfit based on selected_item.  │
    │       │                                            │
    │       │ wardrobe={'items':[...]}                   │
    │       ├──► prompt contains items and selected_item │
    │       ▼                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │ outfit_suggestion= ''/ None / incomplete   │
            ├──► fit_card = descriptive error message    │
            │                                            │
            │ outfit_suggestion= "..."                   │
            ▼ 
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->


**Milestone 3 — Individual tool implementations:**

- **`search_listings()`**
  - I plan to let Claude Code develop a set of tests given the the Tool 1 specs and diagram from this file. I'll verify my code's output with 3 manual test queries — (1) a query with clear matches, (2) a query with a price filter that eliminates some results, (3) a query with no matches — and confirm the return values and sort order match the spec before moving on.

- **`suggest_outfit()`**
  - *AI tool:* Claude Code
  - *Input to AI:* The Tool 2 spec from this file (new_item dict, wardrobe dict), the architecture diagram showing the two wardrobe-empty vs. wardrobe-populated branches, and the example interaction in the "Complete Interaction" section.
  - *Expected output:* A Python function that calls the Claude API with a prompt that either (a) asks for a general outfit for `new_item` when `wardrobe['items']` is empty, or (b) incorporates wardrobe items alongside `new_item` and asks for a coordinated outfit. Returns a plain-English outfit suggestion string.
  - *Verification:* Call the function with an empty wardrobe and confirm it returns a general suggestion; call it with 2–3 wardrobe items and confirm the suggestion references at least one of them.

- **`create_fit_card()`**
  - *AI tool:* Claude Code
  - *Input to AI:* The Tool 3 spec from this file (outfit string, new_item dict), the requirement for a 2–4 sentence caption that reads authentically, mentions the item's name/price/platform, and varies across runs.
  - *Expected output:* A Python function that prompts the Claude API to write a social-media caption. Returns the caption string. Returns an error string when `outfit` is empty or None.
  - *Verification:* Call the function with a real outfit string + item dict and confirm the output is 2–4 sentences, contains the item name, price, and platform. Call it with an empty outfit string and confirm an error string is returned (not an exception).

---

**Milestone 4 — Planning loop and state management:**

- *AI tool:* Claude Code
- *Input to AI:* The Planning Loop section of this file, the Architecture diagram, the State Management section, and the Error Handling table — plus the three tool implementations from Milestone 3.
- *Expected output:* A `run_agent(query, size, max_price, wardrobe)` function (or equivalent Gradio callback) that:
  1. Calls `search_listings()` and returns early with an error message if results are empty.
  2. Stores `results[0]` as `selected_item` in the session/local state.
  3. Calls `suggest_outfit(selected_item, wardrobe)` and stores the result as `outfit_suggestion`.
  4. Calls `create_fit_card(outfit_suggestion, selected_item)` and stores the result as `fit_card`.
  5. Returns all three outputs so the Gradio UI can display them in separate text boxes.
- *Verification:* Run the full "Example user query" from the Complete Interaction section end-to-end through the Gradio interface. Confirm all three text boxes populate, the early-exit path works (use a nonsense query), and no unhandled exceptions are raised for the empty-wardrobe case.

---

## A Complete Interaction (Step by Step)

FitFindr takes a description of a piece of clothing the user is looking for and their existing wardrobe, suggest a piece in the existing database, a fit with their current wardrobe, and a style card that helps them feel hyped about the fit. 


Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent uses this description to call `search_listings()` to find a list of matching recommended items, ranked my relevance. It grabs the top output as `new_item` for the next call.
If nothing is found, it recommends the user to try with a different description. And stop the next steps. 

<!-- TODO: would be good to add reason why this isn't found -->

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
If the agent received something from `search_listings()`, it uses that top output as the `new item`, combined with the wardrobe, to call `suggest_outfit()`. Prints output as a string to interface.

**Step 3:**
<!-- Continue until the full interaction is complete -->
Agent receives string from Step 2, and call that upon `create_fit_card()`. 
End loop. 

**Final output to user:**
<!-- What does the user actually see at the end? -->
3 text boxes filled with string. 
