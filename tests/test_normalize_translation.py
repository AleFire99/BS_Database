"""Pure translation helpers (#95)."""

from dataclasses import replace

from golden_support import parse_fixture, real_glossary, uncurated_glossary

from bs_database.normalize.pipeline import normalize_page
from bs_database.normalize.records import NormalizedPage
from bs_database.normalize.translation import (
    TranslationRequests,
    apply_translations,
    collect_requests,
)
from bs_database.translate.types import TranslationResult


def _page(name: str, *, uncurated: bool = False) -> NormalizedPage:
    glossary = uncurated_glossary() if uncurated else real_glossary()
    return normalize_page(parse_fixture(name), glossary)


def _machine(text: str) -> TranslationResult:
    return TranslationResult(text, "machine", "fake")


def test_requests_skip_glossary_and_batspi_names() -> None:
    page = _page("card_spirit_bs01.html")
    requests = collect_requests(page)
    assert page.entries[0].name_en == "Goradon"
    assert page.entries[0].name_jp not in requests.names
    assert all(f.en is not None for e in page.entries for f in e.gameplay.families)
    assert requests.families == ()
    assert requests.products == tuple(sorted({p.product_name_jp for p in page.printings}))


def test_requests_are_sorted_unique_and_ordered() -> None:
    page = _page("card_flip.html", uncurated=True)
    requests = collect_requests(page)
    for part in (requests.families, requests.names, requests.products):
        assert list(part) == sorted(set(part))
    assert requests.ordered() == [*requests.families, *requests.names, *requests.products]
    assert requests.families


def test_blank_texts_are_not_requested() -> None:
    page = _page("card_spirit.html")
    entry = replace(page.entries[0], name_jp="  ")
    assert collect_requests(replace(page, entries=(entry,), printings=())).names == ()


def test_machine_result_fills_names_families_and_products() -> None:
    page = _page("card_flip.html", uncurated=True)
    requests = collect_requests(page)
    results = {t: _machine(f"<{t}>") for t in requests.ordered()}
    out = apply_translations(page, results)
    first = out.entries[0]
    assert (first.name_en, first.en_source, first.en_status) == (
        f"<{first.name_jp}>",
        "machine",
        "machine",
    )
    translated = [f for e in out.entries for f in e.gameplay.families if f.en_source == "machine"]
    assert translated
    assert all(f.en == f"<{f.jp}>" and f.en_status == "machine" for f in translated)
    printing = out.printings[0]
    assert printing.product_name_en == f"<{printing.product_name_jp}>"
    assert (printing.product_en_source, printing.product_en_status) == ("machine", "machine")
    assert out.unmapped == page.unmapped
    assert out.uncurated == page.uncurated


def test_failed_and_pending_results_keep_no_text() -> None:
    page = _page("card_spirit.html")
    name = page.entries[0].name_jp
    product = page.printings[0].product_name_jp
    results = {
        name: TranslationResult(None, "failed", "fake"),
        product: TranslationResult(None, "pending", "fake"),
    }
    out = apply_translations(page, results)
    first = out.entries[0]
    assert (first.name_en, first.en_source, first.en_status) == (None, None, "failed")
    printing = out.printings[0]
    assert (printing.product_name_en, printing.product_en_source) == (None, None)
    assert printing.product_en_status == "pending"


def test_curated_names_are_kept_even_if_results_exist() -> None:
    page = _page("card_spirit_bs01.html")
    results = {e.name_jp: _machine("WRONG") for e in page.entries} | {
        f.jp: _machine("WRONG") for e in page.entries for f in e.gameplay.families
    }
    out = apply_translations(page, results)
    assert out.entries[0].name_en == "Goradon"
    assert (out.entries[0].en_source, out.entries[0].en_status) == ("batspi", "reviewed")
    assert out.entries[0].gameplay.families == page.entries[0].gameplay.families


def test_missing_results_leave_the_page_unchanged() -> None:
    page = _page("card_flip.html")
    assert apply_translations(page, {}) == page


def test_requests_default_is_empty() -> None:
    assert TranslationRequests().ordered() == []
