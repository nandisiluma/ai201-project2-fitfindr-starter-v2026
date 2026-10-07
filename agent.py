"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable


_PRICE_RE = re.compile(
    r"(?:under|below|max(?:imum)?)\s*\$?(\d+(?:\.\d+)?)|\$(\d+(?:\.\d+)?)",
    re.I,
)
_SIZE_RE = re.compile(r"\bsize\s+([A-Za-z0-9/.\-]+)", re.I)


def _parse_query(query: str) -> dict:
    """
    Pull a description, a size, and a max_price out of free-text, with regex.

    Price: the number after "under" / "below" / "max", or a bare "$30".
    Size:  the token after the word "size" (e.g. "size M", "size XXS").
    Description: whatever's left after those two phrases are removed.
    """
    spans = []

    price_match = _PRICE_RE.search(query)
    max_price = None
    if price_match:
        max_price = float(price_match.group(1) or price_match.group(2))
        spans.append(price_match.span())

    size_match = _SIZE_RE.search(query)
    size = None
    if size_match:
        size = size_match.group(1)
        spans.append(size_match.span())

    description = query
    for start, end in sorted(spans, reverse=True):
        description = description[:start] + description[end:]
    description = re.sub(r"\s*,\s*", " ", description)
    description = re.sub(r"\s+", " ", description).strip() or query

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    What this does, in order:

      1. Parses the query into a description, a size, and a max_price with a
         small regex parser (_parse_query above) — no model call for this.
      2. Calls search_listings() with the parsed fields.

         THIS IS THE BRANCH: if nothing comes back, session["error"] is set
         to a message naming what to change, and the session is returned
         without calling suggest_outfit or create_fit_card.

      3. Otherwise picks the first result as session["selected_item"], then
         calls suggest_outfit() and create_fit_card() in sequence.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)

    count = 0
    while True:
        count += 1
        trace.check_iterations(count)

        parsed = _parse_query(query)
        session["parsed"] = parsed

        results = search_listings(**parsed)
        session["search_results"] = results

        if not results:
            session["error"] = (
                "No listings matched that search. Try a broader description, "
                "a different size, or a higher max_price."
            )
            return session

        selected = results[0]
        session["selected_item"] = selected

        session["outfit_suggestion"] = suggest_outfit(selected, wardrobe)
        session["fit_card"] = create_fit_card(session["outfit_suggestion"], selected)

        return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
