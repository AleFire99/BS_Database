"""A translator wrapper: cache first, optional character budget, one INFO line per call."""

import logging
from collections.abc import Sequence

from bs_database.translate.cache import TranslationCache
from bs_database.translate.types import Lang, TranslationResult, Translator, check_pair

log = logging.getLogger(__name__)

CHUNK = 50  # texts sent to the engine (and committed to the cache) at a time


class CachedTranslator:
    """Looks texts up in the cache and sends only the misses to ``engine``.

    ``max_chars`` caps the characters sent to the engine over the life of this object
    (``None`` = no limit). A text that would exceed it comes back ``pending``; a later,
    shorter text can still fit. Cache hits cost nothing. Only ``machine`` results are cached.
    """

    def __init__(
        self, engine: Translator, cache: TranslationCache, *, max_chars: int | None = None
    ) -> None:
        self._engine = engine
        self._cache = cache
        self._max_chars = max_chars
        self.name = engine.name
        self.chars_sent = 0

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        check_pair(src, tgt)
        name = self.name
        unique = [t for t in dict.fromkeys(texts) if t.strip()]
        hits = self._cache.get_many(name, src, tgt, unique)
        results: dict[str, TranslationResult] = {
            t: TranslationResult(v, "machine", name) for t, v in hits.items()
        }
        pending = TranslationResult(None, "pending", name)
        to_send: list[str] = []
        budget = None if self._max_chars is None else self._max_chars - self.chars_sent
        for t in unique:
            if t in results:
                continue
            if budget is not None and len(t) > budget:
                results[t] = pending
                continue
            if budget is not None:
                budget -= len(t)
            to_send.append(t)
        sent = 0
        for i in range(0, len(to_send), CHUNK):
            chunk = to_send[i : i + CHUNK]
            out = self._engine.translate(chunk, src=src, tgt=tgt)
            self.chars_sent += sum(len(t) for t in chunk)
            sent += len(chunk)
            good = [
                (t, r.text)
                for t, r in zip(chunk, out, strict=True)
                if r.status == "machine" and r.text is not None
            ]
            self._cache.put_many(name, src, tgt, good)
            results.update(zip(chunk, out, strict=True))
        final = [results.get(t, pending) for t in texts]
        log.info(
            "translate engine=%s hits=%d sent=%d chars=%d pending=%d failed=%d",
            name,
            len(hits),
            sent,
            self.chars_sent,
            sum(r.status == "pending" for r in final),
            sum(r.status == "failed" for r in final),
        )
        return final
