"""Pick the translation engine from the settings."""

from bs_database.settings import Settings
from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator
from bs_database.translate.deepl import DeepLTranslator
from bs_database.translate.null import NullTranslator
from bs_database.translate.types import Translator


def make_translator(settings: Settings, *, max_chars: int | None = None) -> Translator:
    """DeepL behind the cache when a key is set, else a bare ``NullTranslator``.

    Without a key nothing is read and no cache file is created, so runs stay offline
    and deterministic (CI).
    """
    if settings.deepl_api_key is None:
        return NullTranslator()
    cache = TranslationCache(settings.translation_cache_path)
    return CachedTranslator(DeepLTranslator(settings.deepl_api_key), cache, max_chars=max_chars)
