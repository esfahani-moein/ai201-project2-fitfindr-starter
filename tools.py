"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    results = []

    keywords = [kw.lower() for kw in description.split() if len(kw) > 2]
    if not keywords:
        keywords = [description.lower()]

    for item in listings:
        # Price filter
        if max_price is not None and item["price"] > max_price:
            continue

        # Size filter (case-insensitive substring match)
        if size is not None:
            size_upper = size.upper()
            item_size_upper = item.get("size", "").upper()
            if size_upper not in item_size_upper:
                continue

        # Keyword scoring
        score = 0
        text_fields = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
        ]
        text = " ".join(text_fields).lower()
        for kw in keywords:
            score += text.count(kw)
            # Extra weight for exact title matches
            if kw in item.get("title", "").lower():
                score += 2

        # Score style_tags and colors
        for kw in keywords:
            for tag in item.get("style_tags", []):
                if kw in tag.lower():
                    score += 1
            for color in item.get("colors", []):
                if kw in color.lower():
                    score += 1

        if score > 0:
            item_copy = dict(item)
            item_copy["_score"] = score
            results.append(item_copy)

    # Sort by score descending, then by price ascending
    results.sort(key=lambda x: (-x["_score"], x["price"]))

    # Remove internal score before returning
    for item in results:
        item.pop("_score", None)

    return results


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    item_desc = f"{new_item['title']} — {new_item['description']}"
    item_details = (
        f"Category: {new_item['category']}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"You are a fashion stylist. A user is considering buying this thrifted item:\n\n"
            f"{item_desc}\n{item_details}\n\n"
            f"The user does not have any wardrobe items entered yet. "
            f"Provide general styling advice for this item: what kinds of pieces it pairs well with, "
            f"what vibe or aesthetic it suits, and any fit or tucking tips. Keep it concise (2–4 sentences)."
        )
    else:
        wardrobe_lines = []
        for w in wardrobe_items:
            line = f"- {w['name']} ({w['category']}, colors: {', '.join(w.get('colors', []))}, tags: {', '.join(w.get('style_tags', []))})"
            if w.get("notes"):
                line += f" — notes: {w['notes']}"
            wardrobe_lines.append(line)

        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            f"You are a fashion stylist. A user is considering buying this thrifted item:\n\n"
            f"{item_desc}\n{item_details}\n\n"
            f"Their current wardrobe:\n{wardrobe_text}\n\n"
            f"Suggest 1–2 complete outfit combinations using the new item and specific pieces from their wardrobe. "
            f"Name the wardrobe pieces explicitly. Include fit/tucking tips if relevant. Keep it concise (3–5 sentences)."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful fashion stylist. Be concise and practical."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        suggestion = response.choices[0].message.content.strip()
        if not suggestion:
            raise ValueError("Empty LLM response")
        return suggestion
    except Exception:
        # Fallback: basic styling advice without LLM
        return (
            f"This {new_item['title'].lower()} works great with classic basics like jeans or trousers. "
            f"Try layering it with pieces in {', '.join(new_item.get('colors', ['neutral']))} tones for a cohesive look."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Error: Cannot generate a fit card without an outfit suggestion. Please try again with a valid outfit."

    client = _get_groq_client()

    prompt = (
        f"Write a short, casual Instagram/TikTok caption (2–4 sentences) for an outfit post.\n\n"
        f"Item: {new_item['title']} — ${new_item['price']:.0f} from {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        f"Guidelines:\n"
        f"- Sound authentic, like a real person's OOTD post, not a product description\n"
        f"- Mention the item name, price, and platform naturally (once each)\n"
        f"- Capture the outfit vibe in specific terms\n"
        f"- Use casual language, maybe an emoji or two\n"
        f"- Keep it 2–4 sentences"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a fashion influencer writing casual social media captions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.85,
            max_tokens=200,
        )
        caption = response.choices[0].message.content.strip()
        if not caption:
            raise ValueError("Empty LLM response")
        return caption
    except Exception:
        # Fallback caption
        return (
            f"thrifted this {new_item['title'].lower()} off {new_item['platform']} for ${new_item['price']:.0f} "
            f"and already obsessed \u2728 full fit details below"
        )
