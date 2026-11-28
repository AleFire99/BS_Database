"""Machine translation (#94, ADR 0008): translator protocol, engines and cache."""

from bs_database.translate.factory import make_translator
from bs_database.translate.null import NullTranslator
from bs_database.translate.protect import (
    GlossaryResolver,
    SpanKind,
    TermResolver,
    kakasi_romaniser,
)
from bs_database.translate.protected import ProtectedTranslator, ProtectionConfig
from bs_database.translate.types import Lang, Status, TranslationResult, Translator

__all__ = [
    "GlossaryResolver",
    "Lang",
    "NullTranslator",
    "ProtectedTranslator",
    "ProtectionConfig",
    "SpanKind",
    "Status",
    "TermResolver",
    "TranslationResult",
    "Translator",
    "kakasi_romaniser",
    "make_translator",
]
