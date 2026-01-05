"""
Direct LLM API code generation for ablation study.

This module generates code by directly calling LLM API without using
the multi-agent collaboration framework (Analyzer -> Corrector -> Writer).
"""

import os
import sys
import re
from typing import Optional

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from src.agent.llm.factory import LLMFactory
from code_extractor import extract_code_multilayer

# Import code fixing utilities from parent directory
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))



def resolve_config_path(config_path):
    """Resolve config file path relative to project root or absolute path."""
    if os.path.isabs(config_path):
        return config_path
    root_path = os.path.join(PROJECT_ROOT, config_path)
    if os.path.exists(root_path):
        return root_path
    if os.path.exists(config_path):
        return os.path.abspath(config_path)
    return config_path


def is_valid_code(code: str) -> tuple[bool, str]:
    """Check if the generated code is valid.
    
    Validates that:
    1. Code is not empty
    2. Code does not contain raw JSON structure
    3. Code contains valid Python syntax (at least a function definition)
    """
    if not code or code.strip() == '':
        return False, "empty code"
    
    # Check for raw JSON structure
    if code.strip().startswith('{') and '"code"' in code:
        return False, "contains raw JSON structure (JSON parsing failed)"
    
    # Check for valid Python code (should contain at least one function definition)
    if 'def ' not in code:
        return False, "no function definition found (invalid Python code)"
    
    return True, ""


def generate_code_with_direct_llm(
    requirement: str, 
    config_path: str = 'config/agent_config.yaml',
    temperature: float = 0.3,
    max_retries: int = 1,
    entry_point: Optional[str] = None
) -> str:
    """Generate code by directly calling LLM API without multi-agent collaboration.
    
    Args:
        requirement: The requirement text (prompt)
        config_path: Path to the LLM configuration file
        temperature: Temperature parameter for LLM generation
        max_retries: Maximum number of retry attempts
        entry_point: Not used in ablation study
        
    Returns:
        Generated code string, or empty string if generation failed
        
    """
    resolved_path = resolve_config_path(config_path)
    
    # Load LLM configuration
    config = LLMFactory.load_config(resolved_path)
    llm_config = config.get('llm', {})
    
    # Get temperature from config if not provided
    if temperature is None:
        temperature = llm_config.get('temperature', 0.3)
    
    # Create LLM instance
    llm = LLMFactory.create_llm(llm_config)
    
    # System prompt for direct code generation (ablation study: no function signature check)
    system_prompt = """You are a Python code generation assistant. Generate Python code from the given requirement.
Output your code inside a markdown code block:

```python
# your complete code here
```
"""

    # User message with requirement 
    user_message = f"""Generate Python code for this requirement:
{requirement.strip()}
"""

    try:
        # Call LLM directly (no retry mechanism for ablation study)
        messages = [
            llm.format_message("system", system_prompt),
            llm.format_message("user", user_message)
        ]
        
        response = llm.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=llm_config.get('max_output_tokens', 12288)
        )
        
        # Extract code from response
        code, extraction_method = extract_code_multilayer(response)
        
        if not code:
            print(f'\n     [Direct LLM] Failed: no code extracted from response', flush=True)
            return ''
        
        # Basic validation only
        is_valid, error_reason = is_valid_code(code)
        
        if is_valid:
            return code
        else:
            print(f'\n     [Direct LLM] Failed: {error_reason}', flush=True)
            return ''
            
    except Exception as e:
        import traceback
        print(f'\n     [Direct LLM] Exception: {e}', flush=True)
        print(f'     [Direct LLM] Traceback: {traceback.format_exc()[:500]}', flush=True)
        return ''

