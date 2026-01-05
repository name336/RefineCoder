"""Writer agent that produces executable code from clarified requirements."""

from __future__ import annotations

import json
import re
import logging

from typing import Dict, List, Optional, Tuple

from ..base import BaseAgent
from .types import AnalyzerOutput, CodeGenerationOutput

logger = logging.getLogger(__name__)


class RequirementCodeWriter(BaseAgent):
    """LLM-backed agent that turns finalized requirements into code."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__("Writer", config_path=config_path)
        # Simplified prompt - Markdown format is LLM's natural output
        self.system_prompt = """You are the Writer agent responsible for generating high-quality, production-ready Python code from clarified requirements. The requirements you receive have been thoroughly analyzed and corrected, ensuring they are precise and complete. Your code must faithfully implement these requirements with attention to correctness, edge cases, and code quality.
## OUTPUT FORMAT (CRITICAL)
Output your code inside a markdown code block:

```python
# your complete code here
```

## RULES
1.The function signature (Parameter types and number of parameters) specified in the requirement MUST be preserved exactly as given throughout the entire workflow.
2. Include ALL necessary imports (from typing import List, Dict, etc.)
3. Handle edge cases (empty input, None, etc.)
4. Verify your code works for ALL provided examples

## CHECKLIST
Before outputting:
- [ ] All imports included
- [ ] All examples pass when mentally executed
- [ ] Edge cases handled
- [ ] Without altering the parameter types and the number of parameters, especially the number of parameters.

Output ONLY the code block, including docstrings"""

    def _reset_conversation(self) -> None:
        """Reset memory for stateless generations."""
        self.clear_memory()
        self.add_to_memory("system", self.system_prompt)

    def process(
        self,
        finalized_requirement: str,
        analysis: AnalyzerOutput,
        metadata: Optional[Dict[str, str]] = None,
        original_function_signature: str = "",
    ) -> CodeGenerationOutput:
        """Generate Python code according to the clarified requirement."""
        self._reset_conversation()
        
        # Include original function signature if provided
        signature_reminder = ""
        if original_function_signature:
            signature_reminder = f"\n\nORIGINAL FUNCTION SIGNATURE (MUST PRESERVE EXACTLY):\n{original_function_signature}\n"
        
        # Simplified user message
        requirement_block = f"""Generate Python code for this requirement:

{finalized_requirement.strip()}{signature_reminder}
Remember: Always preserve the original function signature from the input Include all imports. Output ONLY the code block."""

        self.add_to_memory("user", requirement_block)
        response = self.generate_response()
        return self._parse_response(response, finalized_requirement)

    def _parse_response(self, response: str, requirement: str) -> CodeGenerationOutput:
        """Parse code from response using multi-layer fallback extraction.
        
        Tries multiple extraction methods in order of reliability:
        1. Markdown code block with python tag
        2. Markdown code block without language tag
        3. <CODE> tags
        4. Legacy <CODE_DELIVERABLE> JSON format
        5. Direct function definition extraction
        """
        code, method = self._extract_code_multilayer(response)
        
        if code:
            logger.debug(f"Code extracted successfully using method: {method}")
            
            # Validate function signature is preserved
            is_valid, error_msg = self._validate_signature_preserved(requirement, code)
            if not is_valid:
                logger.warning(f"Code signature validation failed: {error_msg}")
                # Try to fix the signature automatically
                fixed_code = self._fix_signature_in_code(requirement, code)
                if fixed_code:
                    code = fixed_code
                    logger.info("Signature auto-fixed in generated code")
        else:
            logger.warning(f"Failed to extract code from response. First 500 chars: {response[:500]}")
        
        return CodeGenerationOutput(
            finalized_requirement=requirement,
            code=code,
            tests="",
            assumptions=[] if code else [f"Failed to extract code from response"],
        )

    def _extract_code_multilayer(self, response: str) -> Tuple[str, str]:
        """Try multiple methods to extract code from response.
        
        Returns:
            Tuple of (extracted_code, method_used)
        """
        # Method 1: Markdown code block with python tag (most common)
        code = self._try_extract_markdown_python(response)
        if code:
            return code, "markdown_python"
        
        # Method 2: Markdown code block without language tag
        code = self._try_extract_markdown_any(response)
        if code:
            return code, "markdown_any"
        
        # Method 3: <CODE> simple tags
        code = self._try_extract_simple_tags(response)
        if code:
            return code, "simple_tags"
        
        # Method 4: Legacy JSON format (backward compatibility)
        code = self._try_extract_legacy_json(response)
        if code:
            return code, "legacy_json"
        
        # Method 5: Direct function definition extraction
        code = self._try_extract_function_definition(response)
        if code:
            return code, "function_definition"
        
        # Method 6: Any code-like content
        code = self._try_extract_any_code(response)
        if code:
            return code, "any_code"
        
        return "", "none"

    def _try_extract_markdown_python(self, response: str) -> str:
        """Extract code from ```python ... ``` block."""
        # Match ```python or ```Python or ```PYTHON
        pattern = r'```[pP]ython\s*\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _try_extract_markdown_any(self, response: str) -> str:
        """Extract code from ``` ... ``` block (any language or none)."""
        # Match ```<optional_lang>\n...\n```
        pattern = r'```(?:\w*)\s*\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Verify it looks like Python code
            if 'def ' in code or 'import ' in code or 'class ' in code:
                return code
        return ""

    def _try_extract_simple_tags(self, response: str) -> str:
        """Extract code from <CODE>...</CODE> or <code>...</code> tags."""
        pattern = r'<[cC][oO][dD][eE]>\s*(.*?)\s*</[cC][oO][dD][eE]>'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _try_extract_legacy_json(self, response: str) -> str:
        """Extract code from legacy JSON format (backward compatibility)."""
        # Try <CODE_DELIVERABLE> tags first
        lower = response.lower()
        start_tag = "<code_deliverable>"
        end_tag = "</code_deliverable>"
        
        if start_tag in lower and end_tag in lower:
            start_idx = lower.index(start_tag) + len(start_tag)
            end_idx = lower.index(end_tag)
            json_blob = response[start_idx:end_idx].strip()
        else:
            # Try to find JSON directly
            json_blob = response.strip()
        
        # Remove markdown code blocks if present
        if json_blob.startswith("```"):
            lines = json_blob.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            json_blob = "\n".join(lines).strip()
        
        # Try to parse as JSON
        try:
            # Handle trailing commas
            json_blob = re.sub(r',(\s*[}\]])', r'\1', json_blob)
            data = json.loads(json_blob)
            if isinstance(data, dict) and "code" in data:
                return data["code"].strip()
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return ""

    def _try_extract_function_definition(self, response: str) -> str:
        """Extract code starting from function definition."""
        # Find 'def ' and extract from there
        # This handles cases where LLM outputs explanations before code
        lines = response.split('\n')
        start_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Look for import statements or function definitions
            if stripped.startswith('from ') or stripped.startswith('import ') or stripped.startswith('def '):
                start_idx = i
                break
        
        if start_idx >= 0:
            # Extract from start_idx to end, stopping at obvious non-code
            code_lines = []
            for line in lines[start_idx:]:
                # Stop at markdown code block end or obvious non-code
                if line.strip() == '```' or line.strip().startswith('</'):
                    break
                code_lines.append(line)
            
            code = '\n'.join(code_lines).strip()
            # Verify it has a function definition
            if 'def ' in code:
                return code
        
        return ""

    def _try_extract_any_code(self, response: str) -> str:
        """Last resort: extract anything that looks like Python code."""
        # Look for patterns that indicate Python code
        lines = response.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            stripped = line.strip()
            
            # Start collecting when we see code-like patterns
            if not in_code:
                if (stripped.startswith('def ') or 
                    stripped.startswith('class ') or
                    stripped.startswith('import ') or
                    stripped.startswith('from ') or
                    stripped.startswith('@')):  # decorator
                    in_code = True
            
            if in_code:
                # Stop at obvious non-code markers
                if stripped.startswith('```') or stripped.startswith('</') or stripped.startswith('#'):
                    if stripped.startswith('#') and not stripped.startswith('# '):
                        # Likely a markdown header, stop
                        break
                    elif stripped.startswith('```') or stripped.startswith('</'):
                        break
                code_lines.append(line)
        
        code = '\n'.join(code_lines).strip()
        if 'def ' in code:
            return code
        
        return ""

    # ============== Signature Validation Methods ==============

    def _extract_function_signature(self, text: str) -> Tuple[Optional[str], List[Tuple[str, Optional[str]]]]:
        """Extract function name and parameters from text.
        
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
        param_parts = self._split_params(params_str)
        
        for param in param_parts:
            param = param.strip()
            if not param:
                continue
            
            # Check for type annotation
            if ':' in param:
                colon_idx = param.index(':')
                param_name = param[:colon_idx].strip()
                param_type = param[colon_idx + 1:].strip()
                # Remove default value if present
                if '=' in param_type:
                    param_type = param_type.split('=')[0].strip()
                params.append((param_name, param_type))
            else:
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

    def _validate_signature_preserved(self, requirement: str, code: str) -> Tuple[bool, str]:
        """Validate that generated code preserves function signature from requirement.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        req_name, req_params = self._extract_function_signature(requirement)
        code_name, code_params = self._extract_function_signature(code)
        
        # If can't extract signatures, allow through
        if req_name is None or code_name is None:
            return True, ""
        
        # Check parameter count (most critical)
        if len(req_params) != len(code_params):
            return False, f"Parameter count mismatch: requirement has {len(req_params)}, code has {len(code_params)}"
        
        # Check parameter types if specified
        for i, (req_param, code_param) in enumerate(zip(req_params, code_params)):
            req_pname, req_ptype = req_param
            code_pname, code_ptype = code_param
            
            if req_ptype and code_ptype:
                req_type_normalized = req_ptype.replace(' ', '')
                code_type_normalized = code_ptype.replace(' ', '')
                
                if req_type_normalized != code_type_normalized:
                    return False, f"Parameter {i+1} type mismatch: requirement has '{req_ptype}', code has '{code_ptype}'"
        
        return True, ""

    def _fix_signature_in_code(self, requirement: str, code: str) -> Optional[str]:
        """Attempt to fix function signature in code to match requirement.
        
        Returns:
            Fixed code or None if cannot fix
        """
        req_name, req_params = self._extract_function_signature(requirement)
        code_name, code_params = self._extract_function_signature(code)
        
        if req_name is None or code_name is None:
            return None
        
        # Can only fix if parameter count matches
        if len(req_params) != len(code_params):
            logger.warning(f"Cannot auto-fix: parameter count mismatch ({len(req_params)} vs {len(code_params)})")
            return None
        
        # Build the correct signature
        param_strs = []
        for (req_pname, req_ptype), (code_pname, code_ptype) in zip(req_params, code_params):
            # Use requirement's type annotation if available, otherwise code's
            ptype = req_ptype or code_ptype
            if ptype:
                param_strs.append(f"{code_pname}: {ptype}")
            else:
                param_strs.append(code_pname)
        
        new_params = ", ".join(param_strs)
        
        # Extract return type from requirement if present
        req_return_match = re.search(r'\)\s*->\s*([^:]+):', requirement)
        return_type = req_return_match.group(1).strip() if req_return_match else None
        
        # Replace the function signature in code
        # Find the original function definition in code
        code_def_pattern = r'def\s+' + re.escape(code_name) + r'\s*\([^)]*\)(\s*->[^:]+)?:'
        
        if return_type:
            new_def = f"def {req_name}({new_params}) -> {return_type}:"
        else:
            new_def = f"def {req_name}({new_params}):"
        
        fixed_code = re.sub(code_def_pattern, new_def, code, count=1)
        
        # Also replace function calls if name changed
        if req_name != code_name and req_name != 'candidate':
            # Replace calls to the old function name with new name
            # Be careful not to replace partial matches
            call_pattern = r'\b' + re.escape(code_name) + r'\s*\('
            fixed_code = re.sub(call_pattern, f"{req_name}(", fixed_code)
        
        return fixed_code
