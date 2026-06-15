# FitFindr

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. The agent orchestrates three tools in response to a natural language request: searching listings, evaluating fit against an existing wardrobe, and generating a shareable outfit caption.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Then open the localhost URL shown in your terminal (usually http://localhost:7860).

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description` (str), `size` (str\|None), `max_price` (float\|None) | `list[dict]` | Searches the mock listings dataset for items matching the description, optional size, and optional price ceiling. Returns matching listing dicts sorted by relevance. |
| `suggest_outfit` | `new_item` (dict), `wardrobe` (dict) | `str` | Given a thrifted item and the user's wardrobe, suggests 1–2 complete outfit combinations. If the wardrobe is empty, provides general styling advice instead. |
| `create_fit_card` | `outfit` (str), `new_item` (dict) | `str` | Generates a short, shareable outfit caption (2–4 sentences) for social media. Reads like an authentic OOTD post, not a product description. |

## Planning Loop

The planning loop is implemented in `agent.py` inside `run_agent()`. It is a sequential, state-driven pipeline with conditional early termination:

1. **Initialize session**: Create a fresh `session` dict with `_new_session(query, wardrobe)`.
2. **Parse query**: Extract `description`, `size`, and `max_price` from the natural language query using a lightweight regex parser. Store in `session["parsed"]`.
3. **Search listings**: Call `search_listings()` with parsed parameters and store results in `session["search_results"]`.
   - **Branch**: If no results, set `session["error"]` to an actionable message (e.g., "No listings found for 'designer ballgown' in size XXS under $5. Try removing the size filter or raising your budget.") and return the session immediately. `suggest_outfit` and `create_fit_card` are **not** called.
   - If results exist, select `session["selected_item"] = results[0]`.
4. **Suggest outfit**: Call `suggest_outfit(selected_item, wardrobe)` and store in `session["outfit_suggestion"]`.
5. **Create fit card**: Call `create_fit_card(outfit_suggestion, selected_item)` and store in `session["fit_card"]`.
6. **Return session**.

The agent's behavior changes based on what `search_listings` returns — it does not call all three tools unconditionally.

## State Management

All state lives in a single Python dict called `session`, created at the start of each interaction. The session is the single source of truth for the entire run.

Key fields:
- `query`: original user query
- `parsed`: extracted `description`, `size`, `max_price`
- `search_results`: raw results from `search_listings`
- `selected_item`: top result, passed into `suggest_outfit`
- `wardrobe`: user's wardrobe, passed into `suggest_outfit`
- `outfit_suggestion`: result from `suggest_outfit`, passed into `create_fit_card`
- `fit_card`: result from `create_fit_card`
- `error`: set if the interaction ended early

Data flows through the session dict with no re-prompting and no hardcoded values between steps.

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query | Agent sets `session["error"]` to a specific, actionable message and returns early. The UI shows this in the first panel and leaves the other two empty. |
| `suggest_outfit` | Wardrobe is empty | The tool itself handles this by switching to a "general styling advice" LLM prompt instead of a "specific combinations" prompt. The agent does not branch. |
| `create_fit_card` | Outfit input is missing or incomplete | The tool guards against empty `outfit` and returns: "Error: Cannot generate a fit card without an outfit suggestion. Please try again with a valid outfit." No exception is raised. |

**Concrete example from testing:**

Query: `designer ballgown size XXS under $5`

Result: `search_listings` returns `[]`. The agent sets:
```
session["error"] = "No listings found for 'designer ballgown' in size XXS under $5. Try removing the size filter or raising your budget."
```

The UI displays this message in the "Top listing found" panel, and the other two panels remain empty. `suggest_outfit` and `create_fit_card` are never called.

## Spec Reflection

The planning loop described in `planning.md` matches the implementation exactly:
- The regex query parser extracts `description`, `size`, and `max_price` as specified.
- The conditional branch on empty `search_results` terminates early with a helpful error message.
- State passes between tools exclusively through the `session` dict.
- `suggest_outfit` handles the empty wardrobe case internally without agent-level branching.
- `create_fit_card` guards against empty outfit input before calling the LLM.

The only deviation from the original spec is minor: the regex parser removes price/size phrases from the description string, which sometimes leaves a slightly shorter description than the raw query. This was an intentional trade-off to keep parsing lightweight and deterministic.

## AI Tool Usage

### Instance 1: Implementing `search_listings`

I gave Claude the Tool 1 spec from `planning.md` (what the tool does, exact input parameters, return value, failure mode) and the existing `load_listings()` helper code. I asked it to implement the function with keyword scoring against `title`, `description`, `style_tags`, `category`, and `colors`, plus `size` and `price` filtering.

What I changed before using the output:
- Claude initially suggested re-reading the JSON file directly. I replaced that with the provided `load_listings()` call.
- I adjusted the scoring weights to give extra points for title matches, which improved relevance sorting.

Verification: I ran 3 test queries manually and confirmed all filters (price, size, keyword) worked correctly and that an impossible query returned `[]` without crashing.

### Instance 2: Implementing the planning loop in `run_agent`

I gave Claude the Architecture diagram and the Planning Loop + State Management sections from `planning.md`. I asked it to implement `run_agent()` in `agent.py` following the numbered TODO steps in the file.

What I changed before using the output:
- Claude generated a version that called all three tools unconditionally and checked for errors afterward. I rewrote the conditional to branch **before** calling `suggest_outfit`, matching the spec: "If no results: set error and return early. Do NOT proceed to suggest_outfit with empty input."
- I added the regex query parser (`_parse_query`) myself because Claude suggested using an LLM for parsing, which would add unnecessary latency and cost.

Verification: I ran the CLI test in `agent.py` and confirmed the happy path produced `selected_item`, `outfit_suggestion`, and `fit_card`, while the no-results path set `session["error"]` and left the other fields as `None`.
