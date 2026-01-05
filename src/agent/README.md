# Agent Framework for Requirement-Aware Code Generation

This package contains the reusable primitives and specialized agents that power CodeGen's requirement-to-code workflow.

## Overview

Every agent subclasses `BaseAgent`, which provides:

- Centralized LLM initialization via `LLMFactory`
- Shared message memory utilities
- Temperature/token controls to keep inference deterministic

On top of this foundation, `src/agent/requirement_codegen/` implements the Analyzer → Corrector → Writer loop that clarifies requirements before generating code. The workflow entry point is exposed through `generate_code_from_requirement` inside `workflow.py`.

## Agents

1. **`RequirementAnalyzer`**
   - Normalizes the input requirement and flags ambiguity, inconsistency, incompleteness, conflicts, or missing context.
   - Emits structured JSON describing each issue plus clarifying questions.

2. **`RequirementCorrector`**
   - Consumes the Analyzer's issue list and resolves each item.
   - Produces an improved requirement plus a changelog of applied fixes and any open questions.

3. **`RequirementCodeWriter`**
   - Generates production-ready Python modules once the requirement is approved.
   - Adds inline explanations, lightweight tests/usages, and records residual assumptions.

4. **`RequirementCodegenOrchestrator`**
   - Coordinates the iterative Analyzer ↔ Corrector loop.
   - Terminates once the Analyzer marks the spec as ready or when the iteration budget is exhausted.
   - Hands the finalized requirement to the Writer and returns a full trace of decisions.

## Supporting Files

- **`base.py`**: Abstract base with shared LLM helpers.
- **`llm/`**: Provider-specific adapters (OpenAI, Anthropic, Gemini, Hugging Face, local) plus simple rate limiting.
- **`requirement_codegen/types.py`**: Dataclasses for issues, corrections, and writer outputs.
- **`requirement_codegen/workflow.py`**: Helper to run the orchestrator directly from Python code.