# Evaluation Scripts

Scripts for evaluating code generation on the HumanEvalComm dataset.

## Quick Start

```bash
python evaluate.py \
    -e codegen \
    -m gpt-3.5-turbo \
    -n 1 \
    -t 0.2 \
    -c config/agent_config.yaml
```

This runs the complete evaluation pipeline:
1. **Step 1**: Generate code and run tests for all available prompt types
2. **Step 2**: Calculate Pass@k and Test Pass Rate metrics and generate Excel report

The script automatically detects which prompt types exist in the dataset and only processes those.

## Files

| File | Description |
|------|-------------|
| `evaluate.py` | Main entry point for running evaluation |
| `code_generation.py` | Generate code using CodeGen and run test cases |
| `generate_report.py` | Calculate metrics and generate Excel reports |

## Usage

### Basic Commands

```bash
# Run complete evaluation
python evaluate.py -e codegen -m codegen -n 5 -t 1 -c config/agent_config.yaml

# Run only code generation (step 1)
python evaluate.py -e codegen -m codegen -n 5 -t 1 -c config/agent_config.yaml --step 1

# Run only report generation (step 2)
python evaluate.py -e codegen -m codegen -n 5 -t 1 --step 2

# Quick test with limited problems
python evaluate.py -e test -m test -n 1 -t 1 -c config/agent_config.yaml --max-problems 5

# Reproducible test with fixed random seed
python evaluate.py -e test -m test -n 1 -t 1 -c config/agent_config.yaml --max-problems 10 --random-seed 42

# Test all prompt types and generate comprehensive report
python evaluate.py -e codegen -m codegen -n 1 -t 0.2 -c config/agent_config.yaml --test-all-prompts
```

### Arguments

| Argument | Description |
|----------|-------------|
| `-e, --experiment` | Experiment name (for file naming) |
| `-m, --model` | Model name (for file naming) |
| `-n, --topn` | Number of code candidates per problem |
| `-t, --temperature` | Temperature parameter |
| `-c, --config` | CodeGen config file path (required for step 1) |
| `--step` | Steps to run (1, 2, or comma-separated like "1,2") |
| `--max-problems` | Limit number of problems (for quick testing) |
| `--random-seed` | Random seed for reproducible problem selection |
| `-pt, --prompt_type` | Specific prompt type to evaluate |
| `--test-all-prompts` | Calculate metrics for all prompt types in step 2 |

## Output Files

- **Log files**: `log/record/{experiment}_model_{model}_topn_{topn}_temperature_{temperature}.0.log_0`
- **Excel reports**: `tables/result_{experiment}_dataset_HumanEvalComm_model_{model}_topn_{topn}_temperature_{temperature}_all_prompts.xlsx`

## Prompt Types

The HumanEvalComm dataset includes multiple prompt types:

| Type | Description |
|------|-------------|
| `prompt` | Original unmodified prompt |
| `prompt1a` | Variant 1a |
| `prompt1c` | Variant 1c |
| `prompt1p` | Variant 1p |
| `prompt2ac` | Variant 2ac |
| `prompt2ap` | Variant 2ap |
| `prompt2cp` | Variant 2cp |

**Note**: Not all problems in the dataset contain all prompt types. For example:
- `prompt`, `prompt1a`, `prompt1p`: ~100% coverage (164/164 problems)
- `prompt1c`: ~99% coverage (163/164 problems)
- `prompt2ac`: ~99% coverage (162/164 problems)
- `prompt2ap`: ~43% coverage (71/164 problems)
- `prompt2cp`: ~21% coverage (35/164 problems)

The evaluation script automatically detects which prompt types are available for each problem and only processes those that exist. This ensures accurate metrics calculation.

## Metrics

The evaluation calculates two main metrics:

- **Pass@k**: Percentage of problems where all test cases pass
  - Formula: (# problems with all tests passed) / (# total problems)
  - Range: 0% to 100%

- **Test Pass Rate**: Overall percentage of test cases passed
  - Formula: (# total passed test cases) / (# total test cases)
  - Range: 0% to 100%

## Evaluation Pipeline

### Step 1: Code Generation and Testing

Runs `code_generation.py` to:
1. Scan dataset to identify available prompt types for each problem
2. Generate code using CodeGen only for prompt types that exist
3. Execute test cases and record results
4. Save results to log files

**Important**: The script automatically detects which prompt types exist in the dataset and only processes those. Not all problems have all prompt types.

### Step 2: Report Generation

Runs `generate_report.py` to:
1. Read results from log files
2. Calculate Pass@k and Test Pass Rate for each available prompt type
3. Generate aggregate metrics across all non-prompt variants
4. Export results to Excel

**Aggregate Metrics**: The `all_non_prompt` row aggregates metrics from all non-prompt types (prompt1a, prompt1c, prompt1p, prompt2ac, prompt2ap, prompt2cp) that are actually present in the dataset.

## Individual Scripts

### code_generation.py

Generate code and run test cases.

```bash
python code_generation.py -f output.log -n 5 -c config/agent_config.yaml
```

### generate_report.py

Generate metrics report from log files.

```bash
python generate_report.py -e codegen -m gpt-3.5-turbo -n 1 -t 0.2
```

## Configuration

Default configuration in `evaluate.py`:

```python
DEFAULT_CONFIG = {
    'experiment': 'codegen_firstversion',
    'model': 'gpt-3.5-turbo',
    'topn': 1,
    'temperature': '0.2',
    'config_path': 'config/agent_config.yaml',
    'step': '1,2',
    'max_problems': None,
    'random_seed': None,
    'test_all_prompts': True
}
```

You can also use a JSON config file:

```bash
python evaluate.py --config-file my_config.json
```

## Directory Structure

```
eval_scripts/
├── Benchmark/              # Dataset files
│   ├── HumanEval.jsonl
│   └── HumanEvalComm_v2.jsonl
├── log/record/            # Evaluation logs
├── tables/                # Excel reports
├── temp_files/            # Temporary test files
├── code_generation.py     # Step 1: Code generation and testing
├── generate_report.py     # Step 2: Report generation
└── evaluate.py            # Main entry point
```

## Error Handling and Retry Mechanism

The code generation process includes automatic retry for failed attempts:

- **Validation checks**: Empty code, JSON parsing errors, malformed responses
- **Max retries**: 3 attempts per problem by default
- **Retry on failure**: Automatically retries if code is invalid
- **Detailed logging**: Reports reason for each failure

This significantly improves the success rate and reliability of code generation.
