"""The offline quickmt ja-en engine (#102, ADR 0008): CTranslate2 + SentencePiece, on the CPU.

Needs the optional ``mt`` dependency group (``uv sync --group mt``) and the model files in
``BSDB_MT_MODEL_DIR`` (see docs/architecture/translation.md). Both libraries are imported
lazily, so the module imports without them and CI never needs them.

Decoding is deterministic: beam search, one hypothesis, no sampling, one inference thread.
Nothing here raises on engine errors: a load failure marks every text ``failed`` (one
WARNING), a batch failure marks only that batch.
"""

import importlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from bs_database.translate.types import Lang, TranslationResult

log = logging.getLogger(__name__)

MODEL_FILES = ("model.bin", "src.spm.model", "tgt.spm.model")
LIBRARIES = ("ctranslate2", "sentencepiece")


class _Result(Protocol):
    hypotheses: list[list[str]]


class _CT2Translator(Protocol):
    def translate_batch(self, source: list[list[str]], **options: Any) -> Sequence[_Result]: ...


class _Spm(Protocol):
    def encode(self, text: str, out_type: type[str]) -> list[str]: ...

    def decode(self, pieces: list[str]) -> str: ...


@dataclass(frozen=True)
class Models:
    """The three loaded pieces: the CTranslate2 translator and both SentencePiece models."""

    translator: _CT2Translator
    src_spm: _Spm
    tgt_spm: _Spm


Loader = Callable[[Path, str, str], Models]


def default_loader(model_dir: Path, device: str, compute_type: str) -> Models:
    """Load the real libraries and model files; raises on a missing library or bad model."""
    ct2: Any = importlib.import_module("ctranslate2")
    spm: Any = importlib.import_module("sentencepiece")
    translator = ct2.Translator(
        str(model_dir), device=device, compute_type=compute_type, inter_threads=1
    )
    src = spm.SentencePieceProcessor(model_file=str(model_dir / "src.spm.model"))
    tgt = spm.SentencePieceProcessor(model_file=str(model_dir / "tgt.spm.model"))
    return Models(translator, src, tgt)


class QuickMTTranslator:
    """jp -> en only. The model loads on the first non-empty call."""

    name = "quickmt-ja-en"

    def __init__(
        self,
        model_dir: Path,
        *,
        beam_size: int = 5,
        batch_size: int = 32,
        device: str = "cpu",
        compute_type: str = "int8",
        max_decoding_length: int = 256,
        loader: Loader = default_loader,
    ) -> None:
        self._model_dir = model_dir
        self._beam_size = beam_size
        self._batch_size = batch_size
        self._device = device
        self._compute_type = compute_type
        self._max_decoding_length = max_decoding_length
        self._loader = loader
        self._models: Models | None = None
        self._load_failed = False

    def _load(self) -> Models | None:
        if self._models is None and not self._load_failed:
            try:
                self._models = self._loader(self._model_dir, self._device, self._compute_type)
            except Exception as exc:  # noqa: BLE001 - any load problem degrades to "failed"
                self._load_failed = True
                log.warning(
                    "quickmt model not loaded from %s (%s: %s); texts are marked failed",
                    self._model_dir,
                    type(exc).__name__,
                    exc,
                )
        return self._models

    def _translate_batch(self, models: Models, batch: list[str]) -> list[str] | None:
        try:
            source = [models.src_spm.encode(t, out_type=str) for t in batch]
            results = models.translator.translate_batch(
                source,
                beam_size=self._beam_size,
                num_hypotheses=1,
                max_decoding_length=self._max_decoding_length,
                sampling_topk=1,
            )
            if len(results) != len(batch) or any(len(r.hypotheses) != 1 for r in results):
                raise ValueError(f"expected {len(batch)} single hypotheses, got {len(results)}")
            return [models.tgt_spm.decode(r.hypotheses[0]).strip() for r in results]
        except Exception as exc:  # noqa: BLE001 - a bad batch must not stop the run
            log.warning("quickmt batch of %d failed (%s: %s)", len(batch), type(exc).__name__, exc)
            return None

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        if (src, tgt) != ("jp", "en"):
            raise ValueError(f"unsupported language pair: {src!r} -> {tgt!r}")
        pending = TranslationResult(None, "pending", self.name)
        failed = TranslationResult(None, "failed", self.name)
        out = [pending] * len(texts)
        todo = [i for i, t in enumerate(texts) if t.strip()]
        if not todo:
            return out
        models = self._load()
        for start in range(0, len(todo), self._batch_size):
            idx = todo[start : start + self._batch_size]
            translated = (
                None if models is None else self._translate_batch(models, [texts[i] for i in idx])
            )
            for pos, i in enumerate(idx):
                if translated is None or not translated[pos]:
                    out[i] = failed
                else:
                    out[i] = TranslationResult(translated[pos], "machine", self.name)
        return out
