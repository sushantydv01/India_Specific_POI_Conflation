"""Annotation schema and validation models for human-labelled POI conflation benchmark.

Defines:
- LabelDecision: MATCH, NON_MATCH, UNCERTAIN, NEEDS_ADJUDICATION.
- ConfidenceLevel: HIGH, MEDIUM, LOW.
- EvidenceType: Formal categorization of human reasoning and evidence.
- AnnotationQueueItem: Candidate pair presented to annotators.
- AnnotationRecord: Validated human decision record.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Set


class LabelDecision(str, Enum):
    """Permitted human annotation decision classes."""
    MATCH = "MATCH"
    NON_MATCH = "NON_MATCH"
    UNCERTAIN = "UNCERTAIN"
    NEEDS_ADJUDICATION = "NEEDS_ADJUDICATION"


class ConfidenceLevel(str, Enum):
    """Confidence level assigned by the human annotator."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceType(str, Enum):
    """Categorized justification evidence for the annotation decision."""
    EXACT_NAME_AND_LOCATION = "EXACT_NAME_AND_LOCATION"
    TRANSLITERATION_OR_PHONETIC_MATCH = "TRANSLITERATION_OR_PHONETIC_MATCH"
    NAME_EXPANSION_OR_ACRONYM = "NAME_EXPANSION_OR_ACRONYM"
    STREET_LEVEL_DISPLACEMENT = "STREET_LEVEL_DISPLACEMENT"
    SAME_BUILDING_DIFFERENT_BUSINESS = "SAME_BUILDING_DIFFERENT_BUSINESS"
    SAME_BRAND_DIFFERENT_BRANCH = "SAME_BRAND_DIFFERENT_BRANCH"
    PARENT_CHILD_RELATION = "PARENT_CHILD_RELATION"
    CATEGORY_DISJOINT = "CATEGORY_DISJOINT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OTHER = "OTHER"


class AnnotationProvenance(str, Enum):
    """Provenance origin of an annotation record."""
    AI_GENERATED = "AI_GENERATED"
    AUTO_ADOPTED_AI = "AUTO_ADOPTED_AI"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    UNKNOWN_LEGACY = "UNKNOWN_LEGACY"


@dataclass
class AnnotationQueueItem:
    """Represents an unlabelled candidate pair in the annotation queue."""
    pair_id: str
    osm_source_id: str
    ov_source_id: str
    osm_name_raw: Optional[str]
    ov_name_raw: Optional[str]
    osm_name_normalized: Optional[str]
    ov_name_normalized: Optional[str]
    osm_latitude: float
    osm_longitude: float
    ov_latitude: float
    ov_longitude: float
    distance_meters: float
    osm_category: str
    ov_category: str
    category_compatibility: str
    blocking_strategies: str
    sampling_stratum: str
    osm_name_kn: Optional[str] = None
    osm_name_en: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnnotationRecord:
    """Represents a validated human annotation entry."""
    pair_id: str
    osm_source_id: str
    ov_source_id: str
    osm_name_raw: Optional[str]
    ov_name_raw: Optional[str]
    osm_name_normalized: Optional[str]
    ov_name_normalized: Optional[str]
    osm_latitude: float
    osm_longitude: float
    ov_latitude: float
    ov_longitude: float
    distance_meters: float
    osm_category: str
    ov_category: str
    category_compatibility: str
    blocking_strategies: str
    sampling_stratum: str
    decision: LabelDecision
    annotator_id: str
    confidence: ConfidenceLevel
    evidence_type: EvidenceType
    annotation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None
    provenance: str = AnnotationProvenance.UNKNOWN_LEGACY.value

    def validate(self) -> List[str]:
        """Validate record integrity and return list of validation errors."""
        errors: List[str] = []

        if not self.pair_id or "::" not in self.pair_id:
            errors.append(f"Invalid pair_id format: '{self.pair_id}'. Must be 'osm_id::ov_id'")
        
        parts = self.pair_id.split("::")
        if len(parts) != 2 or parts[0] != self.osm_source_id or parts[1] != self.ov_source_id:
            errors.append(f"pair_id '{self.pair_id}' does not match osm_source_id '{self.osm_source_id}' and ov_source_id '{self.ov_source_id}'")

        if not isinstance(self.decision, LabelDecision):
            try:
                LabelDecision(str(self.decision))
            except ValueError:
                errors.append(f"Invalid decision '{self.decision}'. Allowed: {[e.value for e in LabelDecision]}")

        if not isinstance(self.confidence, ConfidenceLevel):
            try:
                ConfidenceLevel(str(self.confidence))
            except ValueError:
                errors.append(f"Invalid confidence '{self.confidence}'. Allowed: {[e.value for e in ConfidenceLevel]}")

        if not isinstance(self.evidence_type, EvidenceType):
            try:
                EvidenceType(str(self.evidence_type))
            except ValueError:
                errors.append(f"Invalid evidence_type '{self.evidence_type}'. Allowed: {[e.value for e in EvidenceType]}")

        if not self.annotator_id or not self.annotator_id.strip():
            errors.append("annotator_id is required and cannot be empty")

        if self.provenance not in [e.value for e in AnnotationProvenance]:
            errors.append(f"Invalid provenance '{self.provenance}'. Allowed: {[e.value for e in AnnotationProvenance]}")

        if not (-90.0 <= self.osm_latitude <= 90.0 and -180.0 <= self.osm_longitude <= 180.0):
            errors.append(f"Invalid OSM latitude/longitude coordinates: ({self.osm_latitude}, {self.osm_longitude})")

        if not (-90.0 <= self.ov_latitude <= 90.0 and -180.0 <= self.ov_longitude <= 180.0):
            errors.append(f"Invalid Overture latitude/longitude coordinates: ({self.ov_latitude}, {self.ov_longitude})")

        if self.distance_meters < 0.0:
            errors.append(f"distance_meters cannot be negative: {self.distance_meters}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value if isinstance(self.decision, LabelDecision) else str(self.decision)
        d["confidence"] = self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else str(self.confidence)
        d["evidence_type"] = self.evidence_type.value if isinstance(self.evidence_type, EvidenceType) else str(self.evidence_type)
        d["provenance"] = self.provenance.value if isinstance(self.provenance, AnnotationProvenance) else str(self.provenance)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnnotationRecord":
        d = dict(data)
        d["decision"] = LabelDecision(d["decision"])
        d["confidence"] = ConfidenceLevel(d["confidence"])
        d["evidence_type"] = EvidenceType(d["evidence_type"])
        d["distance_meters"] = float(d["distance_meters"])
        d["osm_latitude"] = float(d["osm_latitude"])
        d["osm_longitude"] = float(d["osm_longitude"])
        d["ov_latitude"] = float(d["ov_latitude"])
        d["ov_longitude"] = float(d["ov_longitude"])
        d["provenance"] = d.get("provenance") or AnnotationProvenance.UNKNOWN_LEGACY.value
        return cls(**d)
