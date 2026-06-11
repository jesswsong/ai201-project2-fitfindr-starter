"""
tests/test_tools.py

One test per failure mode, plus basic happy-path coverage for each tool.

Run all tests:
    pytest tests/test_tools.py -v

Run tests for one function:
    pytest tests/test_tools.py -m search -v
    pytest tests/test_tools.py -m outfit -v
    pytest tests/test_tools.py -m fitcard -v

suggest_outfit and create_fit_card call the Groq LLM, so those tests require
GROQ_API_KEY to be set in the environment (or a .env file at the project root).
"""

import pytest
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_item():
    """A real listing from the dataset — used across multiple tests."""
    return load_listings()[0]


@pytest.fixture
def example_wardrobe():
    return get_example_wardrobe()


@pytest.fixture
def empty_wardrobe():
    return get_empty_wardrobe()


# ── search_listings ───────────────────────────────────────────────────────────

@pytest.mark.search
def test_search_returns_results():
    """Happy path: broad query with no filters should match multiple listings."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.search
def test_search_result_shape():
    """Each returned item must have the required fields."""
    required_fields = {
        "id", "title", "description", "category", "style_tags",
        "size", "condition", "price", "colors", "brand", "platform",
    }
    results = search_listings("jacket", size=None, max_price=None)
    for item in results:
        assert required_fields.issubset(item.keys()), (
            f"Listing {item.get('id')} is missing fields: "
            f"{required_fields - item.keys()}"
        )


@pytest.mark.search
def test_search_empty_results():
    """Failure mode: impossible query returns an empty list, not an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=1)
    assert results == []


@pytest.mark.search
def test_search_price_filter():
    """Failure mode (partial): items exceeding max_price must be excluded."""
    max_price = 30.0
    results = search_listings("jacket", size=None, max_price=max_price)
    for item in results:
        assert item["price"] <= max_price, (
            f"Item '{item['title']}' costs ${item['price']}, exceeds ${max_price}"
        )


@pytest.mark.search
def test_search_size_filter():
    """Size filter: only listings matching the size string should be returned."""
    results = search_listings("top", size="S", max_price=None)
    for item in results:
        assert "S" in item["size"].upper(), (
            f"Item '{item['title']}' has size '{item['size']}', not 'S'"
        )


@pytest.mark.search
def test_search_no_exception_on_nonsense():
    """search_listings must never raise — returns [] for truly unrecognisable input."""
    results = search_listings("", size=None, max_price=None)
    assert isinstance(results, list)


# ── search_listings — output quality ─────────────────────────────────────────

@pytest.mark.search
def test_search_relevant_items_ranked_first():
    """The first result for 'vintage graphic tee' should contain 'vintage' or 'tee' in its title."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) > 0
    top_title = results[0]["title"].lower()
    assert "vintage" in top_title or "tee" in top_title or "graphic" in top_title, (
        f"Top result '{results[0]['title']}' doesn't seem relevant to 'vintage graphic tee'"
    )


@pytest.mark.search
def test_search_irrelevant_items_excluded():
    """A query for 'graphic tee' should not return items with no textual connection to it."""
    results = search_listings("graphic tee", size=None, max_price=None)
    # Known dataset items with zero keyword overlap: shoes, bags, unrelated accessories
    result_titles = [r["title"].lower() for r in results]
    unrelated_keywords = {"loafer", "boot", "sandal", "heel", "bag", "tote"}
    for title in result_titles:
        words = set(title.split())
        assert not words & unrelated_keywords, (
            f"'{title}' looks unrelated to 'graphic tee' but appeared in results"
        )


@pytest.mark.search
def test_search_more_keyword_matches_rank_higher():
    """An item matching 2 query keywords should rank above one matching only 1."""
    # "vintage denim jacket": items with both 'vintage' and 'denim' should beat items with only one
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    assert len(results) >= 2, "Need at least 2 results to compare ranking"
    # Confirm list is in non-increasing relevance order by re-scoring manually
    import re
    keywords = {"vintage", "denim", "jacket"}
    def count_matches(item):
        text = " ".join([
            item.get("title", ""), item.get("description", ""),
            item.get("category", ""), " ".join(item.get("style_tags", [])),
        ]).lower()
        words = set(re.findall(r"[a-z0-9]+", text))
        return len(keywords & words)
    scores = [count_matches(r) for r in results]
    assert scores == sorted(scores, reverse=True), (
        f"Results are not sorted by relevance. Scores: {scores}"
    )


@pytest.mark.search
def test_search_specific_query_returns_specific_item():
    """'denim jacket' should surface the known 'Denim Jacket — Light Wash, Cropped' listing."""
    results = search_listings("denim jacket", size=None, max_price=None)
    titles = [r["title"] for r in results]
    assert any("Denim Jacket" in t for t in titles), (
        f"Expected 'Denim Jacket' in results, got: {titles[:5]}"
    )


@pytest.mark.search
def test_search_top_result_beats_partial_matches():
    """For a precise query, the top result should match more keywords than the last result."""
    results = search_listings("vintage band tee grunge", size=None, max_price=None)
    assert len(results) >= 2
    import re
    keywords = {"vintage", "band", "tee", "grunge"}
    def count_matches(item):
        text = " ".join([
            item.get("title", ""), " ".join(item.get("style_tags", [])),
        ]).lower()
        words = set(re.findall(r"[a-z0-9]+", text))
        return len(keywords & words)
    top_score = count_matches(results[0])
    last_score = count_matches(results[-1])
    assert top_score >= last_score, (
        f"Top result scored {top_score}, last result scored {last_score} — ordering looks wrong"
    )


@pytest.mark.search
def test_search_combined_filters_narrow_results():
    """Applying both size and price filters should return fewer results than no filters."""
    all_results = search_listings("top", size=None, max_price=None)
    filtered_results = search_listings("top", size="M", max_price=30.0)
    assert len(filtered_results) <= len(all_results), (
        "Adding filters should not increase the result count"
    )


# ── suggest_outfit ────────────────────────────────────────────────────────────

@pytest.mark.outfit
def test_suggest_outfit_with_wardrobe(sample_item, example_wardrobe):
    """Happy path: returns a non-empty string when wardrobe has items."""
    result = suggest_outfit(sample_item, example_wardrobe)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.outfit
def test_suggest_outfit_empty_wardrobe(sample_item, empty_wardrobe):
    """Failure mode: empty wardrobe still returns a general outfit suggestion, not ''."""
    result = suggest_outfit(sample_item, empty_wardrobe)
    assert isinstance(result, str)
    assert len(result.strip()) > 0, (
        "suggest_outfit should return general styling advice for an empty wardrobe"
    )


# ── create_fit_card ───────────────────────────────────────────────────────────

@pytest.mark.fitcard
def test_create_fit_card_returns_caption(sample_item):
    """Happy path: returns a non-empty caption string."""
    outfit = "Pair with wide-leg jeans and chunky white sneakers for a laid-back streetwear look."
    result = create_fit_card(outfit, sample_item)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.fitcard
def test_create_fit_card_mentions_item_metadata(sample_item):
    """Caption should reference the item name, price, and platform."""
    outfit = "Pair with wide-leg jeans and chunky white sneakers."
    result = create_fit_card(outfit, sample_item)
    title_word = sample_item["title"].split()[0].lower()
    assert (
        title_word in result.lower()
        or str(sample_item["price"]) in result
        or sample_item["platform"].lower() in result.lower()
    ), "Caption should mention at least the item name, price, or platform"


@pytest.mark.fitcard
def test_create_fit_card_empty_outfit(sample_item):
    """Failure mode: empty outfit string returns an error message, not ''."""
    result = create_fit_card("", sample_item)
    assert isinstance(result, str)
    assert len(result.strip()) > 0, (
        "create_fit_card should return an error string, not an empty string"
    )


@pytest.mark.fitcard
def test_create_fit_card_whitespace_outfit(sample_item):
    """Failure mode: whitespace-only outfit is treated as missing."""
    result = create_fit_card("   ", sample_item)
    assert isinstance(result, str)
    assert len(result.strip()) > 0
