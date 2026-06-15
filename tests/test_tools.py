"""Tests for FitFindr tools."""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "title" in results[0]
    assert "price" in results[0]


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("tee", size="M", max_price=100)
    assert len(results) > 0
    for item in results:
        assert "M" in item["size"].upper()


def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    item = results[0]
    wardrobe = get_example_wardrobe()
    suggestion = suggest_outfit(item, wardrobe)
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    item = results[0]
    wardrobe = get_empty_wardrobe()
    suggestion = suggest_outfit(item, wardrobe)
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0


def test_create_fit_card():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    item = results[0]
    outfit = "Pair with jeans and sneakers for a casual look."
    card = create_fit_card(outfit, item)
    assert isinstance(card, str)
    assert len(card) > 0
    assert "Error:" not in card


def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    item = results[0]
    card = create_fit_card("", item)
    assert "Error:" in card
