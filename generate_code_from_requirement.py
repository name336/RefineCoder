#!/usr/bin/env python3
"""Command line entry point for the requirement-aware codegen workflow."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agent.requirement_codegen import generate_code_from_requirement
from src.agent.requirement_codegen.types import CodeGenerationOutput

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("requirement_codegen")


def read_requirement(requirement_arg: Optional[str], requirement_file: Optional[str]) -> tuple[str, Optional[str]]:
    """Resolve the requirement text from CLI arguments.
    
    Returns:
        Tuple of (requirement_text, requirement_file_path)
    """
    if requirement_arg:
        return requirement_arg, None

    if requirement_file:
        path = Path(requirement_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Requirement file not found: {path}")
        return path.read_text(encoding="utf-8"), str(path)

    raise ValueError(
        "You must provide either --requirement or --requirement-file."
    )


def write_output(output_path: Optional[str], payload: Dict[str, Any]) -> None:
    """Persist the generation artifact if the user requested it.
    
    Ensures strict JSON compliance: all newlines escaped, proper quoting, etc.
    """
    if not output_path:
        return
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use ensure_ascii=False for Unicode support, but ensure proper JSON escaping
    # indent=2 for readability, but JSON will still be valid
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(json_str, encoding="utf-8")
    logger.info("Wrote generation artifact to %s", path)


def format_interaction_trace(trace: List[Dict[str, Any]], finalized_requirement: str) -> str:
    """Format the interaction trace for human-readable output."""
    output = []
    output.append("=" * 80)
    output.append("ANALYZER-CORRECTOR INTERACTION TRACE")
    output.append("=" * 80)
    
    for entry in trace:
        iteration = entry.get("iteration", 0)
        decision = entry.get("decision", "unknown")
        issues = entry.get("issues", [])
        normalized_req = entry.get("normalized_requirement", "")
        correction = entry.get("correction", {})
        
        output.append(f"\n{'─' * 80}")
        output.append(f"ITERATION {iteration}")
        output.append(f"{'─' * 80}")
        
        # Analyzer output
        output.append(f"\n[ANALYZER] Decision: {decision}")
        
        if issues:
            output.append(f"\n[ANALYZER] Issues Found ({len(issues)}):")
            for idx, issue in enumerate(issues, 1):
                output.append(f"\n  Issue #{idx}:")
                output.append(f"    Type: {issue.get('issue_type', 'N/A')}")
                output.append(f"    Severity: {issue.get('severity', 'N/A')}")
                output.append(f"    Description: {issue.get('description', 'N/A')}")
                if issue.get('evidence'):
                    output.append(f"    Evidence: {issue.get('evidence')}")
                clarifying_questions = issue.get('clarifying_questions', [])
                if clarifying_questions:
                    output.append(f"    Clarifying Questions:")
                    for q_idx, question in enumerate(clarifying_questions, 1):
                        output.append(f"      {q_idx}. {question}")
        else:
            output.append("\n[ANALYZER] No issues found - requirement is ready!")
        
        if normalized_req and issues:  # Only show if there were issues
            output.append(f"\n[ANALYZER] Normalized Requirement:")
            output.append(f"{normalized_req}")
        
        # Corrector output
        if correction:
            output.append(f"\n[CORRECTOR] Applied Fixes:")
            applied_fixes = correction.get('applied_fixes', [])
            if applied_fixes:
                for idx, fix in enumerate(applied_fixes, 1):
                    output.append(f"  {idx}. {fix}")
            else:
                output.append("  (none)")
            
            open_questions = correction.get('open_questions', [])
            if open_questions:
                output.append(f"\n[CORRECTOR] Open Questions:")
                for idx, question in enumerate(open_questions, 1):
                    output.append(f"  {idx}. {question}")
    
    # Final requirement
    output.append(f"\n{'=' * 80}")
    output.append("FINAL REQUIREMENT PASSED TO WRITER")
    output.append(f"{'=' * 80}")
    output.append(finalized_requirement)
    output.append("=" * 80)
    
    return "\n".join(output)


def save_interaction_trace(
    trace: List[Dict[str, Any]], 
    finalized_requirement: str, 
    filepath: str,
    correction_iterations: int
) -> None:
    """Save interaction trace to file (JSON or Markdown based on extension)."""
    path = Path(filepath).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if filepath.endswith('.json'):
        # Save as JSON
        data = {
            "correction_iterations": correction_iterations,
            "trace": trace,
            "finalized_requirement": finalized_requirement
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved interaction trace (JSON) to {path}")
    else:
        # Save as Markdown
        content = format_interaction_trace(trace, finalized_requirement)
        
        # Add header
        markdown = [
            f"# Code Generation Interaction Trace",
            f"",
            f"**Correction Iterations:** {correction_iterations}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            "---",
            f"",
            content
        ]
        
        path.write_text("\n".join(markdown), encoding="utf-8")
        logger.info(f"Saved interaction trace (Markdown) to {path}")


def format_raw_json_trace(trace: List[Dict[str, Any]], finalized_requirement: str) -> str:
    """Format the raw JSON blocks exchanged between Analyzer and Corrector."""
    output = []
    output.append("=" * 80)
    output.append("RAW JSON BLOCKS - ANALYZER & CORRECTOR INTERACTIONS")
    output.append("=" * 80)
    output.append("")
    output.append("> This file contains the complete, unmodified JSON blocks exchanged")
    output.append("> between the Analyzer and Corrector agents during each iteration.")
    output.append("")
    
    for entry in trace:
        iteration = entry.get("iteration", 0)
        analyzer_raw_json = entry.get("analyzer_raw_json", "")
        corrector_raw_json = entry.get("corrector_raw_json", "")
        
        output.append(f"{'─' * 80}")
        output.append(f"## ITERATION {iteration}")
        output.append(f"{'─' * 80}")
        
        # Analyzer JSON block
        output.append("")
        output.append("### ANALYZER OUTPUT")
        output.append("")
        output.append("```json")
        if analyzer_raw_json:
            # Try to pretty-print the JSON
            try:
                parsed = json.loads(analyzer_raw_json)
                output.append(json.dumps(parsed, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                output.append(analyzer_raw_json)
        else:
            output.append("// No raw JSON captured")
        output.append("```")
        
        # Corrector JSON block (only if correction happened)
        if corrector_raw_json:
            output.append("")
            output.append("### CORRECTOR OUTPUT")
            output.append("")
            output.append("```json")
            try:
                parsed = json.loads(corrector_raw_json)
                output.append(json.dumps(parsed, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                output.append(corrector_raw_json)
            output.append("```")
        
        output.append("")
    
    # Final requirement section
    output.append(f"{'=' * 80}")
    output.append("## FINAL REQUIREMENT PASSED TO WRITER")
    output.append(f"{'=' * 80}")
    output.append("")
    output.append("```")
    output.append(finalized_requirement)
    output.append("```")
    output.append("")
    output.append("=" * 80)
    
    return "\n".join(output)


def save_raw_json_trace(
    trace: List[Dict[str, Any]], 
    finalized_requirement: str, 
    filepath: str,
    correction_iterations: int
) -> None:
    """Save raw JSON blocks to a Markdown file."""
    path = Path(filepath).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    content = format_raw_json_trace(trace, finalized_requirement)
    
    # Add header
    markdown = [
        "# Raw JSON Interaction Trace",
        "",
        f"**Correction Iterations:** {correction_iterations}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> Complete JSON blocks exchanged between Analyzer and Corrector agents.",
        "",
        "---",
        "",
        content
    ]
    
    path.write_text("\n".join(markdown), encoding="utf-8")
    logger.info(f"Saved raw JSON trace to {path}")


def print_interaction_summary(result: CodeGenerationOutput) -> None:
    """Print a summary of analyzer-corrector interactions."""
    print("\n" + "=" * 80)
    print("INTERACTION SUMMARY")
    print("=" * 80)
    print(f"Total correction iterations: {result.correction_iterations}")
    
    if result.trace:
        total_issues = sum(len(entry.get('issues', [])) for entry in result.trace)
        print(f"Total issues detected: {total_issues}")
        
        if result.correction_iterations > 0:
            print(f"\nIterations breakdown:")
            for entry in result.trace:
                iteration = entry.get("iteration", 0)
                decision = entry.get("decision", "unknown")
                issues_count = len(entry.get("issues", []))
                has_correction = "correction" in entry
                
                status = "✓" if decision == "ready" else "→"
                correction_marker = " [corrected]" if has_correction else ""
                print(f"  {status} Iteration {iteration}: {issues_count} issues{correction_marker}")
    print("=" * 80 + "\n")


def main() -> None:
    """Parse arguments and invoke the requirement-aware pipeline."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate executable Python code from a natural-language requirement using "
            "a three-agent clarification workflow."
        )
    )
    parser.add_argument("--requirement", type=str, help="Raw requirement text.")
    parser.add_argument(
        "--requirement-file",
        type=str,
        default="req.txt",
        help="Path to a text/markdown file that contains the requirement.",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/agent_config.yaml",
        help="Agent configuration file (defaults to config/agent_config.yaml).",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        help="Optional JSON string with metadata (e.g., repo, coding conventions).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Override the Analyzer/Corrector loop limit. If omitted, uses requirement_flow.max_iterations from config (default 5).",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        help="Optional JSON file where the final artifact will be saved.",
    )
    
    # Interaction-related parameters
    parser.add_argument(
        "--save-interactions",
        type=str,
        default="traces/interaction_trace.md",
        help="Save detailed interaction trace to a file (.json or .md). Default: traces/interaction_trace.md",
    )
    parser.add_argument(
        "--save-raw-json",
        type=str,
        default="traces/raw_json_trace.md",
        help="Save raw JSON blocks exchanged between agents. Default: traces/raw_json_trace.md",
    )
    parser.add_argument(
        "--no-save-interactions",
        action="store_true",
        help="Disable saving interaction trace to file.",
    )
    parser.add_argument(
        "--no-save-raw-json",
        action="store_true",
        help="Disable saving raw JSON trace to file.",
    )
    parser.add_argument(
        "--show-interactions",
        action="store_true",
        default=False,
        help="Display detailed analyzer-corrector interactions in terminal.",
    )
    parser.add_argument(
        "--interaction-summary",
        dest="interaction_summary",
        action="store_true",
        default=True,
        help="Show a brief summary of interactions (default: enabled).",
    )
    parser.add_argument(
        "--no-interaction-summary",
        dest="interaction_summary",
        action="store_false",
        help="Disable interaction summary.",
    )

    args = parser.parse_args()

    requirement_text, requirement_file_path = read_requirement(args.requirement, args.requirement_file)
    metadata = json.loads(args.metadata) if args.metadata else None

    logger.info("Starting requirement-aware code generation workflow.")
    result = generate_code_from_requirement(
        requirement=requirement_text,
        config_path=args.config_path,
        metadata=metadata,
        max_iterations=args.max_iterations,
        requirement_file_path=requirement_file_path,
    )

    payload = {
        "finalized_requirement": result.finalized_requirement,
        "code": result.code,
        "tests": result.tests,
        "assumptions": result.assumptions,
        "trace": result.trace,
        "correction_iterations": result.correction_iterations,
    }

    write_output(args.output_path, payload)

    # Save interaction information to file (enabled by default)
    if not args.no_save_interactions and args.save_interactions:
        try:
            save_interaction_trace(
                result.trace, 
                result.finalized_requirement, 
                args.save_interactions,
                result.correction_iterations
            )
            print(f"\n✓ Interaction trace saved to: {args.save_interactions}")
        except Exception as e:
            logger.warning(f"Failed to save interaction trace: {e}")
    
    # Save raw JSON blocks to file (enabled by default)
    if not args.no_save_raw_json and args.save_raw_json:
        try:
            save_raw_json_trace(
                result.trace, 
                result.finalized_requirement, 
                args.save_raw_json,
                result.correction_iterations
            )
            print(f"✓ Raw JSON trace saved to: {args.save_raw_json}")
        except Exception as e:
            logger.warning(f"Failed to save raw JSON trace: {e}")

    # Display interaction summary (enabled by default, brief)
    if args.interaction_summary:
        print_interaction_summary(result)

    # Display detailed interaction information (disabled by default)
    if args.show_interactions and result.trace:
        print("\n" + format_interaction_trace(result.trace, result.finalized_requirement))

    print("\n=== Finalized Requirement ===\n")
    if requirement_file_path:
        print(f"Source: {requirement_file_path}")
    print(result.finalized_requirement)
    print("\n=== Generated Code ===\n")
    print(result.code)
    if result.tests:
        print("\n=== Suggested Tests / Usage ===\n")
        print(result.tests)
    if result.assumptions:
        print("\n=== Assumptions ===\n")
        for assumption in result.assumptions:
            print(f"- {assumption}")


if __name__ == "__main__":
    main()

