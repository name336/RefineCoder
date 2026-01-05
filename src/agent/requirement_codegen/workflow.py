"""Public workflow helpers for requirement-aware code generation."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .orchestrator import RequirementCodegenOrchestrator
from .types import CodeGenerationOutput


def generate_code_from_requirement(
    requirement: str,
    config_path: str = "config/agent_config.yaml",
    metadata: Optional[Dict[str, Any]] = None,
    max_iterations: Optional[int] = None,
    requirement_file_path: Optional[str] = None,
) -> CodeGenerationOutput:
    """Generate Python code from a textual requirement using the three-agent loop."""
    orchestrator = RequirementCodegenOrchestrator(
        config_path=config_path,
        max_iterations=max_iterations,
    )
    return orchestrator.run(
        requirement=requirement, 
        metadata=metadata,
        requirement_file_path=requirement_file_path,
    )

