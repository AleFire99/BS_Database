"""The null engine: translates nothing, does no I/O (used in CI and without a key)."""

from collections.abc import Sequence

from bs_database.translate.types import Lang, TranslationResult, check_pair


class NullTranslator:
    name = "null"

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        check_pair(src, tgt)
        return [TranslationResult(None, "pending", self.name) for _ in texts]
