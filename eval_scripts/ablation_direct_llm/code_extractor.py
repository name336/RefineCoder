"""
Code extraction utilities for LLM responses.

This module provides functions to extract Python code from LLM responses
using multiple fallback methods, similar to the code_writer agent.
"""

import re
import json
from typing import Tuple


def extract_code_multilayer(response: str) -> Tuple[str, str]:
    """Try multiple methods to extract code from response.
    
    Returns:
        Tuple of (extracted_code, method_used)
    """
    # Method 1: Markdown code block with python tag (most common)
    code = _try_extract_markdown_python(response)
    if code:
        return code, "markdown_python"
    
    # Method 2: Markdown code block without language tag
    code = _try_extract_markdown_any(response)
    if code:
        return code, "markdown_any"
    
    # Method 3: <CODE> simple tags
    code = _try_extract_simple_tags(response)
    if code:
        return code, "simple_tags"
    
    # Method 4: Legacy JSON format (backward compatibility)
    code = _try_extract_legacy_json(response)
    if code:
        return code, "legacy_json"
    
    # Method 5: Direct function definition extraction
    code = _try_extract_function_definition(response)
    if code:
        return code, "function_definition"
    
    # Method 6: Any code-like content
    code = _try_extract_any_code(response)
    if code:
        return code, "any_code"
    
    return "", "none"


def _try_extract_markdown_python(response: str) -> str:
    """Extract code from ```python ... ``` block."""
    # Match ```python or ```Python or ```PYTHON
    pattern = r'```[pP]ython\s*\n(.*?)```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _try_extract_markdown_any(response: str) -> str:
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


def _try_extract_simple_tags(response: str) -> str:
    """Extract code from <CODE>...</CODE> or <code>...</code> tags."""
    pattern = r'<[cC][oO][dD][eE]>\s*(.*?)\s*</[cC][oO][dD][eE]>'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _try_extract_legacy_json(response: str) -> str:
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


def _try_extract_function_definition(response: str) -> str:
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


def _try_extract_any_code(response: str) -> str:
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
    
    if code_lines:
        code = '\n'.join(code_lines).strip()
        # Verify it has a function definition
        if 'def ' in code:
            return code
    
    return ""

