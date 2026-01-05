"""Corrector agent that iteratively fixes requirement issues."""

from __future__ import annotations

import json
import re
import logging
from typing import Dict, List, Optional, Tuple

from ..base import BaseAgent
from .types import CorrectionOutput, RequirementIssue

logger = logging.getLogger(__name__)


class RequirementCorrector(BaseAgent):
    """LLM-backed agent that resolves analyzer-detected issues."""

    OUTPUT_TAG = "CORRECTION"

    def __init__(self, config_path: Optional[str] = None):
        super().__init__("Corrector", config_path=config_path)
        self.system_prompt = """You are the Corrector. Resolve issues to make requirements implementation-ready.

## GOLDEN RULES
1. NEVER change function signature (number of parameters, param types)
2. DERIVE clarifications from EXAMPLES, not assumptions


## CORRECTION STRATEGIES

### AMBIGUITY ("or", "e.g.", "certain" ...)
→ TRUST ORDER: Function Signature > Examples > Description
→ Test each interpretation against ALL examples, pick the one that matches ALL
→ Replace ambiguous phrase with concrete rule


### INCONSISTENT (description ↔ example or description ↔ description)
→ Function name + return type = truth source; check which (description OR example) aligns with it
→ If return type mismatches content, that content is WRONG
→ Trust what matches function signature semantics, discard what contradicts


### INCOMPLETE
→ TRUST ORDER: Function Signature > Examples > Description
→ Infer from function signature, parameter types, example patterns, or description
→ Use common conventions: empty→[], None→error, etc.
→ Use common assumptions and reasonable guesses.


## OUTPUT FORMAT
<CORRECTION>
{
  "improved_requirement": "Complete requirement with ALL issues resolved and function signature preserved",
  "applied_fixes": ["Resolved X to Y based on examples"],
  "open_questions": [],
  "original_function_signature": "Copy the EXACT function signature from the input (must match analyzer's signature)"
}
</CORRECTION>

## CRITICAL: After your correction, the requirement should be READY for code generation.
Ensure improved_requirement is complete, unambiguous, and matches all examples.
"""

    def _reset_conversation(self) -> None:
        """Reset memory to keep generations deterministic per turn."""
        self.clear_memory()
        self.add_to_memory("system", self.system_prompt)

    def process(
        self,
        requirement: str,
        issues: List[RequirementIssue],
        original_function_signature: str = "",
    ) -> CorrectionOutput:
        """Produce an improved requirement based on detected issues."""
        self._reset_conversation()
        issues_payload = [issue.as_dict() for issue in issues]
        requirement_block = (
            "<CURRENT_REQUIREMENT>\n"
            f"{requirement.strip()}\n"
            "</CURRENT_REQUIREMENT>\n\n"
            f"<ORIGINAL_FUNCTION_SIGNATURE>\n"
            f"{original_function_signature}\n"
            f"</ORIGINAL_FUNCTION_SIGNATURE>\n\n"
            f"Issues identified by Analyzer:\n{json.dumps(issues_payload, ensure_ascii=False, indent=2)}\n"
        )
        self.add_to_memory("user", requirement_block)
        response = self.generate_response()
        return self._parse_response(response, fallback_requirement=requirement)

    def _parse_response(self, response: str, fallback_requirement: str) -> CorrectionOutput:
        """Parse the JSON payload from the LLM response."""
        raw_json_block = ""
        try:
            json_blob = self._extract_json_block(response)
            raw_json_block = json_blob  # Store raw JSON for tracing
            data = json.loads(json_blob)
        except (ValueError, json.JSONDecodeError):
            return CorrectionOutput(
                improved_requirement=fallback_requirement,
                applied_fixes=["Failed to parse correction output; returning original requirement."],
                open_questions=[],
                raw_json=raw_json_block or response,  # Store raw response for debugging
            )

        improved_requirement = data.get("improved_requirement", fallback_requirement).strip()
        
        # Validate function signature is preserved
        is_valid, error_msg = self._validate_signature_preserved(fallback_requirement, improved_requirement)
        if not is_valid:
            logger.warning(f"Signature validation failed: {error_msg}. Reverting to original requirement.")
            return CorrectionOutput(
                improved_requirement=fallback_requirement,
                applied_fixes=[f"Signature validation failed: {error_msg}. Reverted to original."],
                open_questions=[],
            )

        return CorrectionOutput(
            improved_requirement=improved_requirement,
            applied_fixes=[fix.strip() for fix in data.get("applied_fixes", []) if fix],
            open_questions=[q.strip() for q in data.get("open_questions", []) if q],
            raw_json=raw_json_block,  # Store raw JSON for tracing
            original_function_signature=data.get("original_function_signature", "").strip(),
        )

    def _extract_json_block(self, response: str) -> str:
        """Extract JSON enclosed by the output tag."""
        lower = response.lower()
        start_tag = f"<{self.OUTPUT_TAG.lower()}>"
        end_tag = f"</{self.OUTPUT_TAG.lower()}>"
        if start_tag in lower and end_tag in lower:
            start_idx = lower.index(start_tag) + len(start_tag)
            end_idx = lower.index(end_tag)
            return response[start_idx:end_idx].strip()
        return response.strip()

    def _extract_function_signature(self, text: str) -> Tuple[Optional[str], List[Tuple[str, Optional[str]]]]:
        """Extract function name and parameters from requirement text.
        
        Returns:
            Tuple of (function_name, list of (param_name, param_type))
        """
        # Match function definition: def func_name(param1: type1, param2: type2, ...) -> return_type:
        pattern = r'def\s+(\w+)\s*\(([^)]*)\)'
        match = re.search(pattern, text)
        
        if not match:
            return None, []
        
        func_name = match.group(1)
        params_str = match.group(2).strip()
        
        if not params_str:
            return func_name, []
        
        # Parse parameters
        params = []
        # Handle nested brackets in type annotations like List[int], Dict[str, int]
        param_parts = self._split_params(params_str)
        
        for param in param_parts:
            param = param.strip()
            if not param:
                continue
            
            # Check for type annotation
            if ':' in param:
                # Split on first ':' to handle complex types
                colon_idx = param.index(':')
                param_name = param[:colon_idx].strip()
                param_type = param[colon_idx + 1:].strip()
                # Remove default value if present
                if '=' in param_type:
                    param_type = param_type.split('=')[0].strip()
                params.append((param_name, param_type))
            else:
                # No type annotation
                param_name = param.split('=')[0].strip()
                params.append((param_name, None))
        
        return func_name, params

    def _split_params(self, params_str: str) -> List[str]:
        """Split parameters string handling nested brackets."""
        params = []
        current = ""
        bracket_depth = 0
        
        for char in params_str:
            if char in '([{':
                bracket_depth += 1
                current += char
            elif char in ')]}':
                bracket_depth -= 1
                current += char
            elif char == ',' and bracket_depth == 0:
                params.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            params.append(current.strip())
        
        return params

    def _validate_signature_preserved(self, original: str, improved: str) -> Tuple[bool, str]:
        """Validate that function signature (name, param count, param types) is preserved.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        orig_name, orig_params = self._extract_function_signature(original)
        impr_name, impr_params = self._extract_function_signature(improved)
        
        # If can't extract signatures, allow through (might not be a function)
        if orig_name is None:
            return True, ""
        
        if impr_name is None:
            return True, ""  # Improved might not have explicit def, allow
        
        # Check function name
        # Allow 'candidate' as a placeholder name that can be preserved
        if orig_name != impr_name and orig_name != 'candidate' and impr_name != 'candidate':
            return False, f"Function name changed from '{orig_name}' to '{impr_name}'"
        
        # Check parameter count
        if len(orig_params) != len(impr_params):
            return False, f"Parameter count changed from {len(orig_params)} to {len(impr_params)}"
        
        # Check parameter types (if specified in original)
        for i, (orig_param, impr_param) in enumerate(zip(orig_params, impr_params)):
            orig_pname, orig_ptype = orig_param
            impr_pname, impr_ptype = impr_param
            
            # Check type if original had one
            if orig_ptype and impr_ptype:
                # Normalize types for comparison (remove spaces)
                orig_type_normalized = orig_ptype.replace(' ', '')
                impr_type_normalized = impr_ptype.replace(' ', '')
                
                if orig_type_normalized != impr_type_normalized:
                    return False, f"Parameter {i+1} type changed from '{orig_ptype}' to '{impr_ptype}'"
        
        return True, ""



