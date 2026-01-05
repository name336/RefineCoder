"""Typed payloads shared by the requirement-aware codegen agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

IssueCategory = Literal[
    "ambiguity",
    "inconsistency",
    "incompleteness",
    "conflict",
    "missing_context",
    "underspecified",
    "boundary",
]


@dataclass
class RequirementIssue:
    """Represents a single quality problem spotted in a requirement."""

    issue_type: IssueCategory
    description: str
    evidence: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    clarifying_questions: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        """Return a serializable representation for logging and prompts."""
        return {
            "issue_type": self.issue_type,
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity,
            "clarifying_questions": self.clarifying_questions,
        }


@dataclass
class AnalyzerOutput:
    """Structured output produced by the analyzer agent."""

    normalized_requirement: str
    issues: List[RequirementIssue] = field(default_factory=list)
    reasoning: str = ""
    decision: Literal["needs_clarification", "ready"] = "ready"
    raw_json: str = ""  # Original JSON block from LLM response
    original_function_signature: str = ""  # Preserved function signature


@dataclass
class CorrectionOutput:
    """Structured output produced by the corrector agent."""

    improved_requirement: str
    applied_fixes: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    raw_json: str = ""  # Original JSON block from LLM response
    original_function_signature: str = ""  # Preserved function signature


@dataclass
class CodeGenerationOutput:
    """Final payload emitted by the writer agent (and orchestrator)."""

    finalized_requirement: str
    code: str
    tests: str = ""
    assumptions: List[str] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    correction_iterations: int = 0  # Number of analyzer-corrector interaction rounds



