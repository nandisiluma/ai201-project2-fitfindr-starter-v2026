"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


def _size_tokens(size: str) -> set[str]:
    """
    Normalize a size string into a set of comparable tokens.

    Strips parenthetical notes (e.g. "XL (oversized)" -> "XL"), then splits on
    anything that isn't a letter or digit, uppercasing what's left. This turns
    "S/M" into {"S", "M"} and "US 9" into {"US", "9"} so matching is done by
    whole-token equality rather than substring — avoiding false positives like
    `"s" in "us 9"` or `"l" in "xl"`.
    """
    stripped = re.sub(r"\([^)]*\)", " ", size)
    return {tok.upper() for tok in re.split(r"[^A-Za-z0-9]+", stripped) if tok}


def _size_matches(query_size: str, listing_size: str) -> bool:
    """A size matches when it shares at least one normalized token."""
    return bool(_size_tokens(query_size) & _size_tokens(listing_size))


_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    listings = load_listings()

    if max_price is not None:
        listings = [item for item in listings if item["price"] <= max_price]

    if size is not None:
        listings = [item for item in listings if _size_matches(size, item["size"])]

    query_words = _words(description)

    scored = []
    for item in listings:
        haystack = " ".join([
            item["title"],
            item["description"],
            item["category"],
            " ".join(item["style_tags"]),
            item["brand"] or "",
        ])
        score = len(query_words & _words(haystack))
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    item_desc = (
        f"{new_item['title']} ({new_item['category']}), "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])}"
    )

    items = wardrobe["items"]

    if not items:
        prompt = (
            f"A user is considering buying this thrifted item:\n{item_desc}\n\n"
            "They don't have any wardrobe items on file yet. Give general "
            "styling advice for this piece — what kinds of items, colors, and "
            "styles would pair well with it."
        )
    else:
        wardrobe_lines = []
        for piece in items:
            line = (
                f"- {piece['name']} ({piece['category']}), "
                f"colors: {', '.join(piece['colors'])}, "
                f"style: {', '.join(piece['style_tags'])}"
            )
            if piece.get("notes"):
                line += f" — {piece['notes']}"
            wardrobe_lines.append(line)

        prompt = (
            f"A user is considering buying this thrifted item:\n{item_desc}\n\n"
            "Here is their current wardrobe:\n"
            + "\n".join(wardrobe_lines)
            + "\n\nSuggest one or two outfits that pair the new item with "
            "specific pieces from their wardrobe, naming each piece by name."
        )

    system = (
        "You are a thrift-shopping stylist. Give concise, specific outfit "
        "suggestions a person could actually wear, grounded in the items "
        "described. Don't invent wardrobe pieces that weren't listed."
    )

    return generate(prompt, system=system)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip():
        return "No fit card yet — no outfit suggestion was available for this item."

    prompt = (
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']:.2f}\n"
        f"Platform: {new_item['platform']}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Style: {', '.join(new_item['style_tags'])}\n"
        f"Outfit idea: {outfit}\n\n"
        "Write a short caption someone would actually post about finding this "
        "piece — two to four sentences, written like a real social post, not "
        "a product listing. Mention the item, its price, and its platform "
        "each exactly once, and be specific about the vibe."
    )

    system = (
        "You are a thrifter writing a caption for a find they're excited "
        "about. Sound like a person posting online, not an ad."
    )

    return generate(prompt, system=system)
