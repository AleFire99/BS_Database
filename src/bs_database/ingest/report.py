"""Run report of the scrape pipeline (#73): what was done, what failed, why the run stopped."""

from dataclasses import dataclass, field

from bs_database.ingest.http import Blocked, BudgetExhausted, RetryAfterTooLong, RobotsUnavailable
from bs_database.ingest.policy import StopRun
from bs_database.ingest.state import IngestState, PageRecord

MAX_LISTED_FAILURES = 20

EXIT_OK = 0
EXIT_NO_INDEX = 1
EXIT_STOPPED = 3

_NEEDS_HUMAN = (Blocked, RobotsUnavailable, RetryAfterTooLong)


@dataclass(frozen=True)
class DiscoveryNote:
    """Oddities of one set page: card numbers no scheme recognises, pages not written yet."""

    set_title: str
    unknown_numbers: tuple[str, ...]
    missing: int


@dataclass
class RunReport:
    """Mutable while the pipeline runs; rendered and mapped to an exit code afterwards."""

    stop: StopRun | None = None
    index_unobtainable: bool = False
    cards_parsed: int = 0
    cache_hits: int = 0
    network_pages: int = 0
    requests_made: int = 0
    index_missing_pages: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[DiscoveryNote] = field(default_factory=list)
    sets_without_cards: list[str] = field(default_factory=list)
    counts: dict[IngestState, int] = field(default_factory=dict)
    exhausted: list[PageRecord] = field(default_factory=list)

    @property
    def hit_rate(self) -> float | None:
        """Cache hits over pages obtained this run, or ``None`` when none were."""
        total = self.cache_hits + self.network_pages
        return None if total == 0 else self.cache_hits / total

    @property
    def exit_code(self) -> int:
        if isinstance(self.stop, _NEEDS_HUMAN):
            return EXIT_STOPPED
        if self.index_unobtainable:
            return EXIT_NO_INDEX
        return EXIT_OK

    def stop_line(self) -> str:
        if self.stop is None:
            return "completed"
        if isinstance(self.stop, BudgetExhausted):
            return f"budget spent, run again to continue ({self.stop})"
        return f"stopped: {type(self.stop).__name__}: {self.stop}"


def _listed(lines: list[str]) -> list[str]:
    shown = lines[:MAX_LISTED_FAILURES]
    if len(lines) > MAX_LISTED_FAILURES:
        shown.append(f"  +{len(lines) - MAX_LISTED_FAILURES} more")
    return shown


def render(report: RunReport) -> str:
    """Human-readable summary of a run."""
    out = ["State:"]
    out += [f"  {state.value}: {n}" for state, n in report.counts.items() if n]
    out.append(f"Cards parsed this run: {report.cards_parsed}")
    if report.index_unobtainable:
        out.append("The card list index could not be obtained and there is nothing to resume.")
    if report.failures:
        out.append(f"Failures this run: {len(report.failures)}")
        out += _listed([f"  {url}: {reason}" for url, reason in report.failures])
    if report.exhausted:
        out.append(f"Exhausted (never retried): {len(report.exhausted)}")
        out += _listed([f"  {r.url}: {r.last_error}" for r in report.exhausted])
    if report.sets_without_cards:
        out.append("Sets without a card list: " + ", ".join(report.sets_without_cards))
    if report.index_missing_pages:
        out.append(f"Index entries whose page does not exist yet: {report.index_missing_pages}")
    for note in report.notes:
        parts = []
        if note.unknown_numbers:
            parts.append(f"{len(note.unknown_numbers)} unknown numbers")
            parts.append(", ".join(note.unknown_numbers[:5]))
        if note.missing:
            parts.append(f"{note.missing} entries without a page")
        out.append(f"Note, {note.set_title}: " + "; ".join(parts))
    out += [f"Warning: {w}" for w in report.warnings]
    rate = "n/a" if report.hit_rate is None else f"{report.hit_rate:.0%}"
    out.append(f"Requests made: {report.requests_made} (incl. robots.txt)")
    out.append(f"Cache hit rate: {rate} ({report.cache_hits} hits, {report.network_pages} fetched)")
    out.append(f"Run: {report.stop_line()}")
    return "\n".join(out)
