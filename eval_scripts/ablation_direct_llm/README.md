# Ablation Study: Direct LLM API Code Generation

This directory contains scripts for ablation study that generates code by directly calling LLM API without using the multi-agent collaboration framework (Analyzer -> Corrector -> Writer).

## Overview

The ablation study compares code generation performance between:
- **Baseline**: Multi-agent collaboration (CodeGen framework)
- **Ablation**: Direct LLM API calls (this implementation)

## Files

- `code_extractor.py`: Code extraction utilities for parsing LLM responses (reused from code_writer agent)
- `code_generation.py`: Direct LLM API code generation function
- `evaluate.py`: Evaluation script that runs code generation and testing
- `main_evaluate.py`: Main entry point for the ablation study evaluation pipeline

## Usage

### Basic Usage

Run the complete evaluation pipeline (code generation + report generation):

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 -c config/agent_config.yaml
```

### Step-by-Step Execution

**Step 1: Generate code and run tests**

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 -c config/agent_config.yaml --step 1
```

**Step 2: Generate final report**

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 --step 2
```

### Quick Test

Test with a small subset of problems:

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 -c config/agent_config.yaml --max-problems 5
```

### Reproducible Experiments

Use a fixed random seed:

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 -c config/agent_config.yaml --max-problems 10 --random-seed 42
```

### Test All Prompt Types

Generate report for all prompt types:

```bash
python main_evaluate.py -e ablation_direct_llm -m deepseek -n 1 -t 0.3 --step 2 --test-all-prompts
```

## Parameters

- `-e, --experiment`: Experiment name (default: `ablation_direct_llm`)
- `-m, --model`: Model name (e.g., `deepseek`, `qwen`)
- `-n, --topn`: Number of code candidates to generate (default: 1)
- `-t, --temperature`: Temperature parameter for LLM generation (default: 0.3)
- `-c, --config`: Path to LLM configuration file (default: `config/agent_config.yaml`)
- `--step`: Steps to run (`1`, `2`, or `1,2`)
- `--max-problems`: Maximum number of problems to process
- `--random-seed`: Random seed for problem selection
- `--test-all-prompts`: Calculate metrics for all prompt types in step 2

## Output

- **Log files**: `eval_scripts/log/record/{experiment}_model_{model}_topn_{topn}_temperature_{temperature}.0.log_0`
- **Excel reports**: `eval_scripts/tables/result_{experiment}_dataset_HumanEvalComm_model_{model}_topn_{topn}_temperature_{temperature}_all_prompts.xlsx`

## Differences from Baseline

The main difference from the baseline CodeGen framework:

1. **No multi-agent collaboration**: Directly calls LLM API with a single prompt
2. **Simplified workflow**: No Analyzer/Corrector iteration loop
3. **Same evaluation**: Uses the same test evaluation and code fixing utilities

## Code Reuse

This implementation reuses:
- Code extraction logic from `code_writer.py`
- Code fixing utilities from `code_fixes.py`
- Evaluation and testing framework from `evaluate.py`
- Report generation from `generate_report.py`

