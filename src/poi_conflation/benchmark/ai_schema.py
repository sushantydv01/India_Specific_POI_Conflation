"""Schema definitions for AI-assisted human annotation in POI conflation.

Defines:
- HumanAction: Enumeration of human interactions with AI suggestions.
- AIPairSuggestion: Structured, explainable AI recommendation for a candidate pair.
- AIAuditRecord: Comprehensive audit record capturing human decisions alongside AI suggestions.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
)


class HumanAction(str, Enum):
    """Categorization of human action relative to AI suggestion."""
    ACCEPTED = "ACCEPTED"       # Reviewer accepted the AI suggestion verbatim
    MODIFIED = "MODIFIED"       # Reviewer adjusted confidence, evidence type, or notes while keeping/changing label
    REJECTED = "REJECTED"       # Reviewer rejected the AI suggestion and chose an alternative label
    INDEPENDENT = "INDEPENDENT" # Review was conducted blindly without AI assistance (e.g. second reviewer)
    AUTO_ADOPTED_AI = "AUTO_ADOPTED_AI" # Automated script adoption of AI suggestion


@dataclass
class AIPairSuggestion:
    """Structured, explainable recommendation generated for a candidate pair."""
    pair_id: str
    suggested_label: LabelDecision
    suggested_confidence: ConfidenceLevel
    suggested_evidence_type: EvidenceType
    explanation: str
    supporting_evidence: List[str] = field(default_factory=list)
    contradictory_evidence: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    adjudication_recommended: bool = False
    model_identifier: str = "rule_heuristic_v1"
    generation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> List[str]:
        """Validate suggestion integrity against schema constraints."""
        errors: List[str] = []
        if not self.pair_id or "::" not in self.pair_id:
            errors.append(f"Invalid pair_id format: '{self.pair_id}'. Must contain '::'")

        if not isinstance(self.suggested_label, LabelDecision):
            try:
                LabelDecision(str(self.suggested_label))
            except ValueError:
                errors.append(f"Invalid suggested_label '{self.suggested_label}'.")

        if not isinstance(self.suggested_confidence, ConfidenceLevel):
            try:
                ConfidenceLevel(str(self.suggested_confidence))
            except ValueError:
                errors.append(f"Invalid suggested_confidence '{self.suggested_confidence}'.")

        if not isinstance(self.suggested_evidence_type, EvidenceType):
            try:
                EvidenceType(str(self.suggested_evidence_type))
            except ValueError:
                errors.append(f"Invalid suggested_evidence_type '{self.suggested_evidence_type}'.")

        if not self.explanation or not self.explanation.strip():
            errors.append("explanation is required and cannot be empty.")

        if not self.model_identifier or not self.model_identifier.strip():
            errors.append("model_identifier is required and cannot be empty.")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert suggestion to dictionary representation."""
        return {
            "pair_id": self.pair_id,
            "suggested_label": self.suggested_label.value if isinstance(self.suggested_label, LabelDecision) else str(self.suggested_label),
            "suggested_confidence": self.suggested_confidence.value if isinstance(self.suggested_confidence, ConfidenceLevel) else str(self.suggested_confidence),
            "suggested_evidence_type": self.suggested_evidence_type.value if isinstance(self.suggested_evidence_type, EvidenceType) else str(self.suggested_evidence_type),
            "explanation": self.explanation,
            "supporting_evidence": list(self.supporting_evidence),
            "contradictory_evidence": list(self.contradictory_evidence),
            "missing_information": list(self.missing_information),
            "adjudication_recommended": self.adjudication_recommended,
            "model_identifier": self.model_identifier,
            "generation_timestamp": self.generation_timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIPairSuggestion":
        """Instantiate suggestion from dictionary representation."""
        d = dict(data)
        d["suggested_label"] = LabelDecision(d["suggested_label"])
        d["suggested_confidence"] = ConfidenceLevel(d["suggested_confidence"])
        d["suggested_evidence_type"] = EvidenceType(d["suggested_evidence_type"])
        d["supporting_evidence"] = list(d.get("supporting_evidence", []))
        d["contradictory_evidence"] = list(d.get("contradictory_evidence", []))
        d["missing_information"] = list(d.get("missing_information", []))
        d["adjudication_recommended"] = bool(d.get("adjudication_recommended", False))
        return cls(**d)


@dataclass
class AIAuditRecord:
    """Audit record capturing the interaction between human decision and AI suggestion."""
    pair_id: str
    annotator_id: str
    human_decision: LabelDecision
    human_confidence: ConfidenceLevel
    human_evidence_type: EvidenceType
    human_action: HumanAction = HumanAction.INDEPENDENT
    ai_suggested_label: Optional[LabelDecision] = None
    ai_suggested_confidence: Optional[ConfidenceLevel] = None
    ai_evidence_type: Optional[EvidenceType] = None
    ai_model_id: Optional[str] = None
    review_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None

    def validate(self) -> List[str]:
        """Validate audit record constraints."""
        errors: List[str] = []
        if not self.pair_id or "::" not in self.pair_id:
            errors.append(f"Invalid pair_id format: '{self.pair_id}'")

        if not self.annotator_id or not self.annotator_id.strip():
            errors.append("annotator_id is required")

        if not isinstance(self.human_decision, LabelDecision):
            try:
                LabelDecision(str(self.human_decision))
            except ValueError:
                errors.append(f"Invalid human_decision '{self.human_decision}'")

        if not isinstance(self.human_action, HumanAction):
            try:
                HumanAction(str(self.human_action))
            except ValueError:
                errors.append(f"Invalid human_action '{self.human_action}'")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit record to dictionary."""
        return {
            "pair_id": self.pair_id,
            "annotator_id": self.annotator_id,
            "human_decision": self.human_decision.value if isinstance(self.human_decision, LabelDecision) else str(self.human_decision),
            "human_confidence": self.human_confidence.value if isinstance(self.human_confidence, ConfidenceLevel) else str(self.human_confidence),
            "human_evidence_type": self.human_evidence_type.value if isinstance(self.human_evidence_type, EvidenceType) else str(self.human_evidence_type),
            "human_action": self.human_action.value if isinstance(self.human_action, HumanAction) else str(self.human_action),
            "ai_suggested_label": self.ai_suggested_label.value if isinstance(self.ai_suggested_label, LabelDecision) else (str(self.ai_suggested_label) if self.ai_suggested_label else None),
            "ai_suggested_confidence": self.ai_suggested_confidence.value if isinstance(self.ai_suggested_confidence, ConfidenceLevel) else (str(self.ai_suggested_confidence) if self.ai_suggested_confidence else None),
            "ai_evidence_type": self.ai_evidence_type.value if isinstance(self.ai_evidence_type, EvidenceType) else (str(self.ai_evidence_type) if self.ai_evidence_type else None),
            "ai_model_id": self.ai_model_id,
            "review_timestamp": self.review_timestamp,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIAuditRecord":
        """Instantiate audit record from dictionary."""
        d = dict(data)
        d["human_decision"] = LabelDecision(d["human_decision"])
        d["human_confidence"] = ConfidenceLevel(d["human_confidence"])
        d["human_evidence_type"] = EvidenceType(d["human_evidence_type"])
        d["human_action"] = HumanAction(d["human_action"])
        if d.get("ai_suggested_label"):
            d["ai_suggested_label"] = LabelDecision(d["ai_suggested_label"])
        if d.get("ai_suggested_confidence"):
            d["ai_suggested_confidence"] = ConfidenceLevel(d["ai_suggested_confidence"])
        if d.get("ai_evidence_type"):
            d["ai_evidence_type"] = EvidenceType(d["ai_evidence_type"])
        return cls(**d)
