"""Candidate generation and multi-attribute blocking modules."""

from src.poi_conflation.blocking.spatial import SpatialBlocker
from src.poi_conflation.blocking.lexical import LexicalBlocker
from src.poi_conflation.blocking.multilingual import MultilingualTransliterationEngine
from src.poi_conflation.blocking.category import (
    CategoryCompatibility,
    CategoryCompatibilityClassifier,
)
from src.poi_conflation.blocking.candidate_engine import CandidateEngine

__all__ = [
    "SpatialBlocker",
    "LexicalBlocker",
    "MultilingualTransliterationEngine",
    "CategoryCompatibility",
    "CategoryCompatibilityClassifier",
    "CandidateEngine",
]
