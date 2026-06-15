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
Searches the mock listings dataset (`data/listings.json`) for items matching a keyword description, optional size, and optional maximum price. It scores each listing by keyword overlap with the description, filters by size and price constraints, drops zero-score items, and returns results sorted by relevance (best match first).

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Used for keyword scoring against title, description, style_tags, category, and colors.
- `size` (str | None): Size string to filter by, or None to skip size filtering. Matching is case-insensitive and checks if the query size appears anywhere in the listing's size field (e.g., "M" matches "S/M" and "M/L").
- `max_price` (float | None): Maximum price (inclusive), or None to skip price filtering.

**What it returns:**
A list of matching listing dicts, sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str|None), `platform` (str).

**What happens if it fails or returns nothing:**
Returns an empty list `[]` — does NOT raise an exception. The agent checks `if not results`, sets `session["error"]` to a helpful message like "No listings found matching 'designer ballgown' in size XXS under $5. Try broadening your search — remove the size filter or increase your budget.", and returns the session early without calling `suggest_outfit`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item (a listing dict) and the user's current wardrobe, suggests 1–2 complete outfit combinations. If the wardrobe is empty, it provides general styling advice for the item instead of specific combinations.

**Input parameters:**
- `new_item` (dict): A listing dict representing the thrifted item the user is considering. Contains the same fields as a search result.
- `wardrobe` (dict): A wardrobe dict with an `'items'` key containing a list of wardrobe item dicts. Each wardrobe item has: `id`, `name`, `category`, `colors`, `style_tags`, `notes`. The `items` list may be empty.

**What it returns:**
A non-empty string with outfit suggestions. If wardrobe has items, it names specific pieces from the wardrobe and explains how to combine them with the new item. If wardrobe is empty, it offers general styling advice (what kinds of items pair well, what vibe it suits, fit tips).

**What happens if it fails or returns nothing:**
The tool itself never crashes: if `wardrobe['items']` is empty, it calls the LLM with a "general styling advice" prompt instead of a "specific combinations" prompt. The agent does not need special error handling here because the tool handles the empty wardrobe internally. If the LLM call fails, the tool catches the exception and returns a fallback string with basic styling advice.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable outfit caption (2–4 sentences) suitable for Instagram or TikTok. It reads like an authentic OOTD post, not a product description. It naturally mentions the item name, price, and platform once each, captures the outfit vibe, and sounds different on each run (uses a higher LLM temperature).

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()`.
- `new_item` (dict): The listing dict for the thrifted item, used to extract title, price, and platform for natural inclusion in the caption.

**What it returns:**
A 2–4 sentence string usable as a social media caption. If `outfit` is empty or whitespace-only, returns a descriptive error message string: "Error: Cannot generate a fit card without an outfit suggestion. Please try again with a valid outfit."

**What happens if it fails or returns nothing:**
If `outfit` is empty or missing, the tool returns an error message string immediately — it does NOT call the LLM and does NOT raise an exception. If the LLM call fails, it catches the exception and returns a fallback caption using the item title, price, and platform.

---

### Additional Tools (if any)

No additional tools for the base submission. Stretch features (price comparison, style profile memory, trend awareness, retry logic) may be added later.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop is a sequential, state-driven pipeline with conditional early termination. It is implemented in `agent.py` inside `run_agent()`. Here is the exact logic:

1. **Initialize session**: Create a fresh session dict with `_new_session(query, wardrobe)`.

2. **Parse the query**: Extract `description`, `size`, and `max_price` from the natural language query using a lightweight regex parser (no LLM call needed for parsing). Store the parsed dict in `session["parsed"]`.

3. **Call `search_listings`** with `session["parsed"]["description"]`, `session["parsed"]["size"]`, and `session["parsed"]["max_price"]`.
   - Store results in `session["search_results"]`.
   - **Branch**: `if not session["search_results"]`:
     - Set `session["error"]` to a specific, actionable message: `"No listings found for '<description>' in size <size> under $<max_price>. Try removing the size filter or raising your budget."`
     - Return the session immediately. Do NOT call `suggest_outfit` or `create_fit_card`.
   - **Else**: Select `session["selected_item"] = session["search_results"][0]` (top result by relevance score).

4. **Call `suggest_outfit`** with `session["selected_item"]` and `session["wardrobe"]`.
   - Store result in `session["outfit_suggestion"]`.
   - No early termination here — even if the wardrobe is empty, the tool returns general advice.

5. **Call `create_fit_card`** with `session["outfit_suggestion"]` and `session["selected_item"]`.
   - Store result in `session["fit_card"]`.
   - If `session["outfit_suggestion"]` was somehow empty, the tool returns an error message string, which gets stored in `session["fit_card"]`.

6. **Return session**: The session now contains `selected_item`, `outfit_suggestion`, `fit_card`, and `error=None`. The caller (`handle_query` in `app.py`) checks `session["error"]` first to decide which UI panels to populate.

The loop is done when all three tools have run (happy path) or when `search_listings` returns empty (error path).

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single Python dict called `session`, created at the start of each interaction by `_new_session()`. The session is the single source of truth for the entire run.

Key fields tracked in the session:
- `query` (str): original user query
- `parsed` (dict): extracted `description`, `size`, `max_price`
- `search_results` (list[dict]): raw results from `search_listings`
- `selected_item` (dict | None): top result, passed into `suggest_outfit`
- `wardrobe` (dict): user's wardrobe, passed into `suggest_outfit`
- `outfit_suggestion` (str | None): result from `suggest_outfit`, passed into `create_fit_card`
- `fit_card` (str | None): result from `create_fit_card`
- `error` (str | None): if set, the interaction ended early

Data flow:
1. `search_listings` writes to `session["search_results"]`.
2. The planning loop reads `session["search_results"]` and writes `session["selected_item"]`.
3. `suggest_outfit` reads `session["selected_item"]` and `session["wardrobe"]`, and the loop writes its return value to `session["outfit_suggestion"]`.
4. `create_fit_card` reads `session["outfit_suggestion"]` and `session["selected_item"]`, and the loop writes its return value to `session["fit_card"]`.

There is no re-prompting the user between steps and no hardcoded values. State is passed entirely through the session dict.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Agent sets `session["error"]` to: "No listings found for 'designer ballgown' in size XXS under $5.00. Try removing the size filter or raising your budget." It returns the session early. The UI shows this message in the first panel and leaves the other two panels empty. |
| suggest_outfit | Wardrobe is empty | The tool itself handles this: it calls the LLM with a "general styling advice" prompt instead of a "specific combinations" prompt. The agent does not branch here. The user sees general advice like "This item pairs well with wide-leg trousers and chunky sneakers for a streetwear vibe." |
| create_fit_card | Outfit input is missing or incomplete | The tool guards against empty `outfit` and returns: "Error: Cannot generate a fit card without an outfit suggestion. Please try again with a valid outfit." This gets displayed in the fit card panel. No exception is raised. |

---

## Architecture

```
User query (natural language)
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► Parse query (regex)                              │
    │       │ parsed = {description, size, max_price}     │
    │       ▼                                            │
    ├─► search_listings(description, size, max_price)    │
    │       │ results = []                               │
    │       ├──► [ERROR] "No listings found..." ───────► return
    │       │                                            │
    │       │ results = [item, ...]                      │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │ wardrobe empty → general advice            │
    │       │ wardrobe has items → specific combos       │
    │       ▼                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item) │
            │                                            │
        Session: fit_card = "..."                        │
            │                                            │
            ▼                                            │
        Return session                                   │
            │                                            │
            ▼                                            │
        handle_query() maps session to UI panels         │
            │                                            │
            ▼                                            │
        Gradio UI displays 3 output panels               │
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For each tool, I will use **Claude** as the AI assistant.

- **search_listings**: I will give Claude the Tool 1 spec from planning.md (what it does, exact inputs, return value, failure mode) plus the data loader code (`load_listings()`). I will ask Claude to implement the function in `tools.py` with keyword scoring against title, description, style_tags, category, and colors, plus size and price filtering. Before using the output, I will verify: (1) it uses `load_listings()` rather than re-reading the file, (2) it filters by all three parameters, (3) it sorts by score, (4) it returns `[]` on no matches without raising. Then I will run 3 test queries manually.

- **suggest_outfit**: I will give Claude the Tool 2 spec, the wardrobe schema, and the Groq client setup code. I will ask it to implement the function with two prompt branches (empty wardrobe vs. non-empty wardrobe) and to handle the empty wardrobe case gracefully. I will verify the empty-wardrobe branch does not crash and that the LLM temperature is reasonable. I will test with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

- **create_fit_card**: I will give Claude the Tool 3 spec and ask for a function that guards against empty `outfit`, builds a prompt for a casual social-media caption, and calls the LLM with a higher temperature (e.g., 0.8) so outputs vary. I will verify it mentions item title, price, and platform naturally, and that running it twice on the same input produces different output.

**Milestone 4 — Planning loop and state management:**

I will give Claude the **Architecture diagram** and the **Planning Loop** + **State Management** sections from this planning.md. I will ask it to implement `run_agent()` in `agent.py` following the numbered steps in the file's TODO. Before using the output, I will verify: (1) it initializes the session with `_new_session()`, (2) it parses the query with regex, (3) it branches on empty `search_results` and returns early, (4) it stores `selected_item`, `outfit_suggestion`, and `fit_card` in the session, (5) it does NOT call all three tools unconditionally.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1: Parse query**
The agent extracts:
- `description` = "vintage graphic tee"
- `size` = None (no size mentioned)
- `max_price` = 30.0
Store in `session["parsed"]`.

**Step 2: Search listings**
Call `search_listings("vintage graphic tee", size=None, max_price=30.0)`.

The tool loads all 40 listings, filters by price <= 30.0, then scores remaining items by keyword overlap with "vintage graphic tee". Top matches:
- `lst_033` — "Vintage Band Tee — Faded Grey" ($19, depop) — score: high (matches "vintage", "band tee" ~ "graphic tee", "grunge", "streetwear")
- `lst_006` — "Graphic Tee — 2003 Tour Bootleg Style" ($24, depop) — score: high (matches "graphic tee", "vintage", "grunge")
- `lst_002` — "Y2K Baby Tee — Butterfly Print" ($18, depop) — score: medium (matches "vintage", "graphic tee" via butterfly print)

Returns `[lst_033, lst_006, lst_002]` sorted by score.

Agent sets `session["selected_item"] = lst_033`.

**Step 3: Suggest outfit**
Call `suggest_outfit(new_item=lst_033, wardrobe=example_wardrobe)`.

The wardrobe has 10 items including baggy jeans, chunky sneakers, black denim jacket, etc.

LLM prompt includes the new item details and the wardrobe items list. LLM returns:
"Pair this faded grey band tee with your baggy straight-leg jeans and chunky white sneakers for an effortless streetwear look. Layer your vintage black denim jacket over it when it gets chilly. Roll the sleeves once and tuck the front corner slightly for shape."

Agent stores this in `session["outfit_suggestion"]`.

**Step 4: Create fit card**
Call `create_fit_card(outfit=<outfit_suggestion>, new_item=lst_333)`.

LLM prompt includes the outfit suggestion and item details (title, price, platform). LLM returns:
"thrifted this faded band tee off depop for $19 and honestly it was made for my baggy jeans \ud83d\udda4 full fit in my stories"

Agent stores this in `session["fit_card"]`.

**Final output to user:**
The Gradio UI shows three panels:
- **Top listing found**: "Vintage Band Tee — Faded Grey | $19.00 | depop | Size L | Condition: fair | Colors: grey, charcoal"
- **Outfit idea**: "Pair this faded grey band tee with your baggy straight-leg jeans and chunky white sneakers for an effortless streetwear look. Layer your vintage black denim jacket over it when it gets chilly. Roll the sleeves once and tuck the front corner slightly for shape."
- **Your fit card**: "thrifted this faded band tee off depop for $19 and honestly it was made for my baggy jeans \ud83d\udda4 full fit in my stories"

