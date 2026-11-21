"""Pick the translation engine from the environment."""

import logging
from importlib.util import find_spec

from bs_database.settings import Settings
from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator
from bs_database.translate.null import NullTranslator
from bs_database.translate.quickmt import LIBRARIES, MODEL_FILES, QuickMTTranslator
from bs_database.translate.types import Translator

log = logging.getLogger(__name__)


def make_translator(settings: Settings, *, max_chars: int | None = None) -> Translator:
    """quickmt behind the cache when the model and the ``mt`` group are there, else null.

    Otherwise nothing is read and no cache file is created, so runs stay offline and
    deterministic (CI). One INFO line says why the null engine was chosen.
    """
    model_dir = settings.mt_model_dir
    missing = [f for f in MODEL_FILES if not (model_dir / f).is_file()]
    if missing:
        log.info("machine translation off: model files missing in %s (%s)", model_dir, missing)
        return NullTranslator()
    if any(find_spec(lib) is None for lib in LIBRARIES):
        log.info("machine translation off: libraries missing, run `uv sync --group mt`")
        return NullTranslator()
    cache = TranslationCache(settings.translation_cache_path)
    return CachedTranslator(QuickMTTranslator(model_dir), cache, max_chars=max_chars)
