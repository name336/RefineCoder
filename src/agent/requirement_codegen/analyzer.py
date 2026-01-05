"""Analyzer agent that inspects natural language requirements for issues."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from ..base import BaseAgent
from .types import AnalyzerOutput, RequirementIssue, IssueCategory

logger = logging.getLogger(__name__)


class RequirementAnalyzer(BaseAgent):
    """LLM-backed agent that validates and normalizes requirements."""

    OUTPUT_TAG = "ANALYSIS"

    def __init__(self, config_path: Optional[str] = None):
        super().__init__("Analyzer", config_path=config_path)
        self.system_prompt = """You are the Analyzer. Identify issues that prevent correct code generation.

## GOLDEN RULES
1. PRESERVE function signature EXACTLY (number of parameters, param types) 
2. DERIVE behavior from examples when description is unclear
3. YOU ARE AN ANALYZER, NOT A CORRECTOR - Your job is to FIND problems, NOT to FIX them!

## THREE ISSUE TYPES

### AMBIGUITY
- Triggers: including but not limited to "or", "e.g.", "certain", "some", "may"
- Report ONLY if examples don't clarify which interpretation is correct
- If examples resolve it → NOT an issue

### INCONSISTENT
- Triggers: Description says X but examples show Y
- Report ONLY if cannot determine correct behavior
- Usually: trust examples → NOT an issue

### INCOMPLETE 
- Triggers: Missing handling of edge cases or 
the correct functionality of the function cannot be inferred from the description, function signature, or examples.
- Report ONLY if critical and cannot infer from function name/examples
- Common patterns (empty→[], None→error) can be inferred → NOT an issue
-The correct functionality of the function cannot be inferred from the description and function signature.


## DECISION LOGIC
- "ready": Can implement correctly (behavior is clear or inferable)
- "needs_correction": TRUE ambiguity remains that prevents implementation

## CRITICAL: normalized_requirement RULES (MUST FOLLOW)
When decision = "needs_correction":
  → normalized_requirement MUST be the EXACT ORIGINAL requirement text, UNCHANGED
  → DO NOT resolve any issues and modify anything
  → DO NOT pick one interpretation over another
  → Simply COPY the original requirement AS-IS
  → The Corrector agent will handle all fixes
When decision = "ready":
  → normalized_requirement = your clarified version of the requirement

## OUTPUT FORMAT
<ANALYSIS>
{
  "decision": "ready" | "needs_correction",
  "reasoning": {
    "signature_analysis": "...",
    "core_behavior": "...",
    "examples_analysis": "...",
    "ambiguities_found": [],
    "edge_cases_identified": []
  },
  "issues": [
    {
      "type": "ambiguous" | "incomplete" | "inconsistent",
      "severity": "high" | "medium" | "low",
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "normalized_requirement": "MUST be EXACT ORIGINAL TEXT if decision='needs_correction'; clarified version only if decision='ready'",
  "original_function_signature": "Extract and preserve the EXACT function signature from the requirement (e.g., 'def func_name(param: Type) -> ReturnType:')"
}
</ANALYSIS>

## CRITICAL: If requirement has been corrected and issues resolved → return "ready" with empty issues!
"""

    def _reset_conversation(self) -> None:
        """Reset the chat memory to the base system instruction."""
        self.clear_memory()
        self.add_to_memory("system", self.system_prompt)

    def process(
        self,
        requirement: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AnalyzerOutput:
        """Analyze the requirement and emit structured findings."""
        self._reset_conversation()
        
        payload = (
            "<REQUIREMENT>\n"
            f"{requirement.strip()}\n"
            "</REQUIREMENT>\n\n"
        )
        
        # Add history context to help recognize resolved issues
        if history:
            # Get previous issues that were corrected
            prev_issues = []
            for h in history:
                if h.get("issues"):
                    prev_issues.extend([i.get("description", "") for i in h["issues"]])
            
            if prev_issues:
                payload += (
                    f"CONTEXT: This requirement has been corrected {len(history)} time(s).\n"
                    f"Previously identified issues: {prev_issues[:3]}\n"
                    "If these issues are NOW RESOLVED in the requirement above → return 'ready' with empty issues.\n"
                    "Only report NEW issues not previously addressed.\n\n"
                )
        
        payload += "Analyze and return your assessment."

        self.add_to_memory("user", payload)
        response = self.generate_response()
        return self._parse_response(response, fallback_requirement=requirement)

    def _parse_response(self, response: str, fallback_requirement: str) -> AnalyzerOutput:
        """Parse JSON from the LLM response and convert to AnalyzerOutput."""
        raw_json_block = ""
        try:
            json_blob = self._extract_json_block(response)
            raw_json_block = json_blob  # Store raw JSON for tracing
            data = json.loads(json_blob)
        except (ValueError, json.JSONDecodeError):
            # Graceful fallback ensures orchestration can continue.
            return AnalyzerOutput(
                normalized_requirement=fallback_requirement,
                issues=[],
                reasoning="Failed to parse analyzer response; defaulting to original requirement.",
                decision="ready",
                raw_json=raw_json_block or response,  # Store raw response for debugging
            )

        # Parse issues with support for both old and new field names
        issues = []
        for item in data.get("issues", []):
            if not item.get("description"):
                continue
            
            # Support both old format (issue_type, evidence, clarifying_questions) 
            # and new format (type, location, suggestion)
            issue_type = item.get("issue_type") or item.get("type")
            evidence = item.get("evidence") or item.get("location")
            # clarifying_questions can be a list or a single suggestion string
            clarifying_questions = item.get("clarifying_questions", [])
            if not clarifying_questions and item.get("suggestion"):
                # Convert single suggestion to list
                clarifying_questions = [item.get("suggestion")]
            
            issues.append(
                RequirementIssue(
                    issue_type=self._sanitize_issue_type(issue_type),
                    description=item.get("description", "").strip(),
                    evidence=evidence,
                    severity=self._sanitize_severity(item.get("severity")),
                    clarifying_questions=clarifying_questions if isinstance(clarifying_questions, list) else [],
                )
            )

        # Determine decision based on issues
        # If there are ANY issues, force "needs_clarification" to ensure correction
        raw_decision = data.get("decision", "ready").lower()
        if raw_decision == "needs_correction":
            raw_decision = "needs_clarification"
        
        if issues:
            # Force correction for ALL issues
            decision = "needs_clarification"
            logger.info(f"Found {len(issues)} issues, requiring correction.")
        else:
            # No issues means ready
            decision = "ready"
            if raw_decision == "needs_clarification":
                logger.info(
                    "Analyzer returned 'needs_clarification' but no issues found. Overriding to 'ready'."
                )

        # Handle reasoning field: can be string or dict (new format)
        reasoning_data = data.get("reasoning", "")
        if isinstance(reasoning_data, dict):
            # Convert dict to formatted string
            reasoning_str = json.dumps(reasoning_data, ensure_ascii=False, indent=2)
        elif isinstance(reasoning_data, str):
            reasoning_str = reasoning_data
        else:
            reasoning_str = ""
        
        return AnalyzerOutput(
            normalized_requirement=data.get("normalized_requirement", fallback_requirement).strip(),
            issues=issues,
            reasoning=reasoning_str.strip() if reasoning_str else "",
            decision=decision,
            raw_json=raw_json_block,  # Store raw JSON for tracing
            original_function_signature=data.get("original_function_signature", "").strip(),
        )

    def _extract_json_block(self, response: str) -> str:
        """Extract the JSON payload from the tagged response."""
        lower = response.lower()
        start_tag = f"<{self.OUTPUT_TAG.lower()}>"
        end_tag = f"</{self.OUTPUT_TAG.lower()}>"
        if start_tag in lower and end_tag in lower:
            start_idx = lower.index(start_tag) + len(start_tag)
            end_idx = lower.index(end_tag)
            return response[start_idx:end_idx].strip()
        return response.strip()

    @staticmethod
    def _sanitize_issue_type(raw_type: Optional[str]) -> IssueCategory:
        """Map arbitrary strings to supported literals."""
        normalized = (raw_type or "").strip().lower()
        allowed: List[IssueCategory] = [
            "ambiguity",
            "inconsistency",
            "incompleteness",
            "conflict",
            "missing_context",
            "underspecified",
            "boundary",
        ]
        return normalized if normalized in allowed else "ambiguity"

    @staticmethod
    def _sanitize_severity(raw_severity: Optional[str]) -> Literal["low", "medium", "high", "critical"]:
        """Map arbitrary severity strings to supported literals."""
        normalized = (raw_severity or "").strip().lower()
        allowed = ["low", "medium", "high", "critical"]
        # Map critical to high for backward compatibility with code that expects only low/medium/high
        if normalized == "critical":
            return "high"
        return normalized if normalized in allowed else "medium"



