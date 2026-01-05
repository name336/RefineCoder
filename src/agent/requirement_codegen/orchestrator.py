"""Coordinator that links the Analyzer, Corrector, and Writer agents."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..llm.factory import LLMFactory
from .analyzer import RequirementAnalyzer
from .corrector import RequirementCorrector
from .code_writer import RequirementCodeWriter
from .types import (
    AnalyzerOutput,
    CodeGenerationOutput,
    CorrectionOutput,
    RequirementIssue,
)

logger = logging.getLogger(__name__)

# Optional visualizer import - will be None if not available
try:
    import sys
    import importlib.util
    from pathlib import Path
    
    # Get the absolute path to the current project's visualizer module
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    visualizer_module_path = project_root / "visualizer" / "codegen_status.py"
    
    if not visualizer_module_path.exists():
        raise ImportError(f"Visualizer module not found at {visualizer_module_path}")
    
    # Load the module directly from file path
    spec = importlib.util.spec_from_file_location("codegen_status_local", visualizer_module_path)
    if spec and spec.loader:
        codegen_status_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(codegen_status_module)
        CodegenStatusVisualizer = codegen_status_module.CodegenStatusVisualizer
        VISUALIZER_AVAILABLE = True
    else:
        raise ImportError("Failed to load visualizer module")
except (ImportError, AttributeError) as e:
    VISUALIZER_AVAILABLE = False
    CodegenStatusVisualizer = None


class RequirementCodegenOrchestrator:
    """Runs the iterative requirement clarification + codegen loop."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        max_iterations: Optional[int] = None,
        enable_visualization: bool = True,
    ):
        self.analyzer = RequirementAnalyzer(config_path=config_path)
        self.corrector = RequirementCorrector(config_path=config_path)
        self.writer = RequirementCodeWriter(config_path=config_path)
        self.max_iterations = self._resolve_iteration_budget(config_path, max_iterations)
        
        # Initialize visualizer if available and enabled
        self.visualizer = None
        if enable_visualization and VISUALIZER_AVAILABLE and CodegenStatusVisualizer:
            self.visualizer = CodegenStatusVisualizer()

    def run(
        self,
        requirement: str,
        metadata: Optional[Dict[str, Any]] = None,
        requirement_file_path: Optional[str] = None,
    ) -> CodeGenerationOutput:
        """Execute the three-agent workflow until the requirement is ready."""
        # Store requirement_file_path for later use
        self._requirement_file_path = requirement_file_path
        
        # Initialize visualization
        if self.visualizer:
            self.visualizer.set_requirement_preview(requirement, requirement_file_path)
            self.visualizer.update(
                active_agent="analyzer",
                iteration=0,
                status_message="Starting requirement analysis...",
            )
        
        history: List[Dict[str, Any]] = []
        current_requirement = requirement
        analyzer_snapshot: AnalyzerOutput | None = None
        correction_count = 0  # Track number of corrector invocations
        original_function_signature = ""  # Track the original function signature across agents

        for iteration in range(1, self.max_iterations + 1):
            logger.info("Analyzer iteration %s started.", iteration)
            
            # Update visualization
            if self.visualizer:
                self.visualizer.update(
                    active_agent="analyzer",
                    iteration=iteration,
                    status_message=f"Analyzing requirement (iteration {iteration})...",
                )
            
            analyzer_snapshot = self.analyzer.process(
                current_requirement,
                context=metadata,
                history=history,
            )
            
            # Capture original function signature from the first analyzer run
            if iteration == 1 and analyzer_snapshot.original_function_signature:
                original_function_signature = analyzer_snapshot.original_function_signature
            
            history.append(
                {
                    "iteration": iteration,
                    "decision": analyzer_snapshot.decision,
                    "issues": [issue.as_dict() for issue in analyzer_snapshot.issues],
                    "normalized_requirement": analyzer_snapshot.normalized_requirement,
                    "analyzer_raw_json": analyzer_snapshot.raw_json,  # Store raw JSON for tracing
                    "original_function_signature": analyzer_snapshot.original_function_signature,  # Track signature
                }
            )

            # Check if ready to proceed to code generation
            # Ready means: decision is "ready" AND no issues
            if analyzer_snapshot.decision == "ready" and not analyzer_snapshot.issues:
                logger.info("Requirement deemed ready after %s iterations.", iteration)
                # Update visualization
                if self.visualizer:
                    self.visualizer.update(
                        active_agent="analyzer",
                        iteration=iteration,
                        status_message="Requirement is ready for code generation!",
                        issues_count=0,
                    )
                break
            
            # If there are issues, call corrector
            if analyzer_snapshot.issues:
                logger.info(
                    "Corrector iteration %s started with %s issues.",
                    iteration,
                    len(analyzer_snapshot.issues),
                )
            else:
                # needs_clarification but no issues - proceed anyway
                logger.warning(
                    f"Decision is '{analyzer_snapshot.decision}' but no issues found. "
                    "Proceeding to Writer anyway."
                )
                break
            
            # Update visualization
            if self.visualizer:
                self.visualizer.update(
                    active_agent="corrector",
                    iteration=iteration,
                    status_message=f"Correcting issues ({len(analyzer_snapshot.issues)} found)...",
                    issues_count=len(analyzer_snapshot.issues),
                )
            
            correction = self._correct_requirement(
                analyzer_snapshot.normalized_requirement,
                analyzer_snapshot.issues,
                original_function_signature,
            )
            correction_count += 1  # Increment correction counter
            current_requirement = correction.improved_requirement
            history[-1]["correction"] = {
                "applied_fixes": correction.applied_fixes,
                "open_questions": correction.open_questions,
            }
            history[-1]["corrector_raw_json"] = correction.raw_json  # Store raw JSON for tracing
            history[-1]["corrector_original_function_signature"] = correction.original_function_signature  # Track signature from corrector
            
            # Update visualization after correction
            if self.visualizer:
                self.visualizer.set_requirement_preview(current_requirement, self._requirement_file_path)
                self.visualizer.update(
                    active_agent="corrector",
                    iteration=iteration,
                    status_message=f"Applied {len(correction.applied_fixes)} fixes, ready for re-analysis...",
                )
        else:
            # Max iterations reached - proceed with last corrected requirement instead of failing
            logger.warning(
                f"Max iterations ({self.max_iterations}) reached. "
                "Proceeding to code generation with best available requirement."
            )
            if self.visualizer:
                self.visualizer.update(
                    active_agent="analyzer",
                    iteration=self.max_iterations,
                    status_message=f"Max iterations reached, proceeding with current requirement...",
                )

        assert analyzer_snapshot is not None, "Analyzer must run at least once."
        # Use current_requirement (latest corrected version) as it may be better than analyzer's normalized version
        final_requirement = current_requirement if current_requirement else analyzer_snapshot.normalized_requirement
        logger.info("Writer generating code for the clarified requirement.")
        
        # Update visualization for writer
        if self.visualizer:
            self.visualizer.update(
                active_agent="writer",
                iteration=0,
                status_message="Generating code from clarified requirement...",
            )
        
        output = self.writer.process(
            finalized_requirement=final_requirement,
            analysis=analyzer_snapshot,
            metadata=metadata,
            original_function_signature=original_function_signature,
        )
        
        # Final visualization update
        if self.visualizer:
            self.visualizer.update(
                active_agent="writer",
                iteration=0,
                status_message="Code generation complete!",
            )
        
        output.trace = history
        output.correction_iterations = correction_count  # Store correction count
        return output

    def _correct_requirement(
        self,
        requirement: str,
        issues: List[RequirementIssue],
        original_function_signature: str = "",
    ) -> CorrectionOutput:
        """Send issues to the Corrector agent and return its fixes."""
        return self.corrector.process(
            requirement=requirement,
            issues=issues,
            original_function_signature=original_function_signature,
        )

    def _resolve_iteration_budget(
        self,
        config_path: Optional[str],
        explicit_budget: Optional[int],
    ) -> int:
        """Resolve the maximum Analyzer/Corrector iterations."""
        if explicit_budget is not None:
            return explicit_budget

        try:
            config = LLMFactory.load_config(config_path)
        except FileNotFoundError:
            return 5

        return int(config.get("requirement_flow", {}).get("max_iterations", 5))

