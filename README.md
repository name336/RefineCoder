# CodeGen: Requirement-Aware Code Generation System

CodeGen is a multi-agent code generation system that focuses on transforming ambiguous natural language requirements into high-quality Python code. The system iteratively clarifies requirements through three collaborative agents (Analyzer, Corrector, Writer) before generating code, ensuring correctness and traceability of the final output.

## Table of Contents

- [System Architecture](#system-architecture)
- [Core Features](#core-features)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Configuration File Structure](#configuration-file-structure)
  - [Supported LLM Providers](#supported-llm-providers)
  - [API Key Configuration](#api-key-configuration)
  - [Rate Limit Configuration](#rate-limit-configuration)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Command Line Arguments](#command-line-arguments)
  - [Output Description](#output-description)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## System Architecture

CodeGen employs a three-agent collaborative workflow:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Analyzer  │ ──▶  │  Corrector  │ ──▶  │   Writer    │
│  Requirement│ ◀──  │  Requirement│      │    Code     │
│   Analyzer  │      │  Corrector  │      │  Generator  │
└─────────────┘      └─────────────┘      └─────────────┘
       │                    │
       └────────┬───────────┘
          Iterative Loop
      (until requirement ready)
```

### Three-Agent Roles

1. **Analyzer Agent (Requirement Analyzer)**
   - Normalizes raw requirements
   - Detects ambiguity, inconsistency, incompleteness, conflicts, and missing context
   - Outputs structured issue lists and clarifying questions
   - Determines whether requirements are ready for code generation

2. **Corrector Agent (Requirement Corrector)**
   - Receives issues detected by the analyzer
   - Resolves each issue while remaining faithful to the original intent
   - Proposes reasonable defaults when information is missing
   - Returns improved requirements to the analyzer, forming an improvement loop

3. **Writer Agent (Code Generator)**
   - Once the analyzer confirms requirements are ready, generates production-ready Python code
   - Adds inline comments, basic observability hooks, and lightweight usage/test snippets
   - Lists residual assumptions to improve visibility

## Core Features

- **Iterative Requirement Clarification**: Automatically detects and fixes requirement issues before code generation
- **Multi-LLM Support**: Supports multiple large models including OpenAI, Claude, Gemini, DeepSeek, Qwen, Llama, etc.
- **Flexible Configuration**: Can configure different models and parameters for each agent individually
- **Complete Tracing**: Records all agent interaction processes for auditing and debugging
- **Rate Limit Management**: Built-in intelligent rate limiter to avoid API call limits
- **Function Signature Protection**: Ensures generated code strictly maintains original function signatures

## Installation

### 1. Clone the Repository

```bash
git clone <repository_url>
cd CodeGen_SecondVersion
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install all dependencies
pip install -e ".[all]"

# Or install basic dependencies only
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
python generate_code_from_requirement.py --help
```

## Configuration

### Configuration File Structure

The configuration file is located at `config/agent_config.yaml`. Copy from the example configuration for first-time use:

```bash
# Copy example configuration
cp config/example_config.yaml config/agent_config.yaml

# Edit configuration file
notepad config/agent_config.yaml  # Windows
nano config/agent_config.yaml     # Linux/macOS
```

### Supported LLM Providers

| Provider | type value | Requires api_key | Requires api_base |
|----------|------------|------------------|-------------------|
| OpenAI | `openai` | ✓ | ✗ (Optional) |
| Anthropic Claude | `claude` | ✓ | ✗ (Optional) |
| Google Gemini | `gemini` | ✓ | ✓ (Usually required) |
| DeepSeek | `deepseek` | ✓ | ✓ |
| Alibaba Qwen | `qwen` | ✓ | ✓ |
| Llama | `llama` | ✓ | ✓ |
| HuggingFace (Local) | `huggingface` | ✗ | ✗ |

### API Key Configuration

#### Method 1: Global Configuration (Recommended)

All agents share the same LLM configuration:

```yaml
llm:
  type: "openai"                      # LLM provider type
  api_key: "your-api-key-here"        # Replace with your API key
  model: "gpt-4o-mini"                # Model name
  temperature: 0.1                    # Temperature parameter (0-1)
  max_output_tokens: 12288            # Maximum output tokens
  max_input_tokens: 100000            # Maximum input tokens
  # api_base: "https://api.openai.com/v1"  # Optional: custom API endpoint
```

#### Method 2: Per-Agent Configuration

Use different models or parameters for each agent:

```yaml
# Global default configuration
llm:
  type: "openai"
  api_key: "your-api-key-here"
  model: "gpt-4o-mini"
  temperature: 0.1
  max_output_tokens: 12288
  max_input_tokens: 100000

# Agent-specific configuration (optional, overrides global config)
agent_llms:
  analyzer:
    type: "openai"
    api_key: "your-api-key-here"
    model: "gpt-4o-mini"
    temperature: 0.0              # Analyzer uses lower temperature
    max_output_tokens: 4096
  
  corrector:
    type: "claude"                # Corrector uses Claude
    api_key: "your-claude-api-key"
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.2
    max_output_tokens: 4096
  
  writer:
    type: "openai"
    api_key: "your-api-key-here"
    model: "gpt-4o"               # Code generator uses stronger model
    temperature: 0.1
    max_output_tokens: 12288
```

### Configuration Examples for Different Providers

#### OpenAI GPT

```yaml
llm:
  type: "openai"
  api_key: "sk-..."
  model: "gpt-4o-mini"            # Or "gpt-4o", "gpt-3.5-turbo"
  temperature: 0.1
  max_output_tokens: 12288
  # api_base: "https://api.openai.com/v1"  # Required when using proxy
```

#### Anthropic Claude

```yaml
llm:
  type: "claude"
  api_key: "sk-ant-..."
  model: "claude-3-5-sonnet-20241022"  # Or other Claude models
  temperature: 0.1
  max_output_tokens: 4096
```

#### Google Gemini

```yaml
llm:
  type: "gemini"
  api_key: "your-gemini-api-key"
  model: "gemini-1.5-flash"       # Or "gemini-1.5-pro"
  api_base: "https://generativelanguage.googleapis.com/v1beta"
  temperature: 0.1
  max_output_tokens: 4096
```

#### DeepSeek

```yaml
llm:
  type: "deepseek"
  api_key: "your-deepseek-api-key"
  model: "deepseek-chat"
  api_base: "https://api.deepseek.com/v1"
  temperature: 0.1
  max_output_tokens: 4096
```

#### Qwen

```yaml
llm:
  type: "qwen"
  api_key: "your-qwen-api-key"
  model: "qwen-turbo"             # Or "qwen-plus", "qwen-max"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  temperature: 0.1
  max_output_tokens: 4096
```

#### Llama (via OpenAI-compatible service)

```yaml
llm:
  type: "llama"
  api_key: "your-api-key"
  model: "meta-llama/Llama-3.1-70b"
  api_base: "https://api.siliconflow.cn/v1"
  temperature: 0.1
  max_output_tokens: 4096
```

#### HuggingFace (Local Model)

```yaml
llm:
  type: "huggingface"
  model: "deepseek-ai/deepseek-coder-6.7b-instruct"
  device: "cuda"                  # Or "cpu"
  torch_dtype: "float16"          # Or "float32"
  # Local models do not require api_key
```

### Rate Limit Configuration

Configure rate limits for each provider (optional, for cost control and avoiding limits):

```yaml
rate_limits:
  openai:
    requests_per_minute: 500
    input_tokens_per_minute: 200000
    output_tokens_per_minute: 100000
    input_token_price_per_million: 0.15    # Input token price (USD/million)
    output_token_price_per_million: 0.60   # Output token price (USD/million)
  
  claude:
    requests_per_minute: 50
    input_tokens_per_minute: 20000
    output_tokens_per_minute: 8000
    input_token_price_per_million: 3.0
    output_token_price_per_million: 15.0
  
  # ... Similar for other providers
```

### Workflow Parameter Configuration

```yaml
requirement_flow:
  max_iterations: 5               # Maximum Analyzer/Corrector iterations
```

## Usage

### Basic Usage

#### Direct Input from Command Line

```bash
python generate_code_from_requirement.py \
  --requirement "Implement a function that receives two strings and returns their longest common substring"
```

#### Read Requirement from File

```bash
python generate_code_from_requirement.py \
  --requirement-file req.txt
```

#### Specify Configuration File

```bash
python generate_code_from_requirement.py \
  --requirement "Your requirement description" \
  --config-path config/agent_config.yaml
```

#### Save Output Results

```bash
python generate_code_from_requirement.py \
  --requirement "Your requirement description" \
  --output-path output/result.json
```

#### Complete Example

```bash
python generate_code_from_requirement.py \
  --requirement-file req.txt \
  --config-path config/agent_config.yaml \
  --output-path output/result.json \
  --max-iterations 5 \
  --save-interactions traces/trace.md \
  --save-raw-json traces/raw.md \
  --show-interactions
```

### Command Line Arguments

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--requirement` | Direct input of requirement text | - |
| `--requirement-file` | Read requirement from file | `req.txt` |
| `--config-path` | Configuration file path | `config/agent_config.yaml` |
| `--output-path` | Path to save JSON output | - |
| `--max-iterations` | Maximum iterations (overrides config) | 5 |
| `--metadata` | JSON-formatted metadata string | - |
| `--save-interactions` | File path to save interaction trace | `traces/interaction_trace.md` |
| `--save-raw-json` | File path to save raw JSON blocks | `traces/raw_json_trace.md` |
| `--no-save-interactions` | Disable saving interaction trace | False |
| `--no-save-raw-json` | Disable saving raw JSON | False |
| `--show-interactions` | Display detailed interactions in terminal | False |
| `--interaction-summary` | Display interaction summary | True |
| `--no-interaction-summary` | Disable interaction summary | - |

### Output Description

#### Terminal Output

The system outputs to terminal:

1. **Interaction Summary**: Shows iteration count and issue count
2. **Final Requirement**: Complete requirement description after clarification
3. **Generated Code**: Directly runnable Python code
4. **Suggested Tests**: Usage examples and test cases
5. **Assumptions List**: Assumptions made when generating code

#### JSON Output File

JSON file saved using `--output-path` contains:

```json
{
  "finalized_requirement": "Final requirement text",
  "code": "Generated code",
  "tests": "Test code",
  "assumptions": ["Assumption 1", "Assumption 2"],
  "trace": [...],  // Complete agent interaction history
  "correction_iterations": 2  // Number of corrections
}
```

#### Interaction Trace Files

- `traces/interaction_trace.md`: Human-readable interaction process
- `traces/raw_json_trace.md`: Raw JSON communication records

## Examples

### Example 1: Simple Function Generation

Requirement file `req.txt`:

```
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
```

Run:

```bash
python generate_code_from_requirement.py --requirement-file req.txt
```

Output:

```python
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers
    
    Args:
        a: First integer
        b: Second integer
        
    Returns:
        Sum of the two integers
    """
    return a + b
```

### Example 2: Complex Requirement (Requires Iterative Clarification)

Requirement:

```
Implement a function that processes a list of strings and returns some result.
```

The system will:

1. **Analyzer** detects that "some result" is ambiguous
2. **Corrector** infers specific behavior based on function signature and common patterns
3. Iterate multiple times until requirements are clear
4. **Writer** generates final code

### Example 3: Using Different Model Combinations

Configuration:

```yaml
agent_llms:
  analyzer:
    type: "openai"
    model: "gpt-4o-mini"  # Fast, economical analysis
  corrector:
    type: "claude"
    model: "claude-3-5-sonnet-20241022"  # Strong reasoning capability
  writer:
    type: "openai"
    model: "gpt-4o"  # High-quality code generation
```

This balances performance, cost, and quality.

## Troubleshooting

### Common Issues

#### 1. API Key Error

**Error Message**: `ValueError: API key must be specified directly in the config file`

**Solution**:
- Ensure the `api_key` field in `config/agent_config.yaml` is filled in
- Check if API key format is correct (usually starts with specific prefix like `sk-`)

#### 2. Model Not Found

**Error Message**: `Model not found` or `Invalid model name`

**Solution**:
- Check if the `model` field is a model name supported by the provider
- Refer to each provider's documentation for correct model names

#### 3. API Endpoint Error

**Error Message**: Connection timeout or 404 error

**Solution**:
- For providers requiring `api_base`, ensure the URL is correct
- Check network connection and firewall settings
- If using a proxy, ensure `api_base` points to the proxy address

#### 4. Rate Limit Exceeded

**Error Message**: `Rate limit exceeded` or 429 error

**Solution**:
- Adjust `rate_limits` configuration to reduce call frequency
- Consider using a higher-tier API subscription plan
- Reduce `max_iterations` value

#### 5. Out of Memory (When Using Local Models)

**Error Message**: `CUDA out of memory`

**Solution**:
- Reduce `max_output_tokens` and `max_input_tokens`
- Use a smaller model
- Set `device: "cpu"` to use CPU (slower but doesn't require GPU memory)

### Debugging Tips

#### Enable Verbose Logging

```bash
# Set environment variable
export PYTHONPATH=.

# Use Python logging
python -u generate_code_from_requirement.py \
  --requirement "..." \
  --show-interactions \
  2>&1 | tee debug.log
```

#### View Interaction Trace

```bash
# Save detailed trace
python generate_code_from_requirement.py \
  --requirement "..." \
  --save-interactions traces/debug_trace.md \
  --save-raw-json traces/debug_raw.md

# View files
cat traces/debug_trace.md
```

#### Test Configuration

Create a simple test requirement:

```bash
echo "def hello() -> str: return 'Hello'" > test_req.txt

python generate_code_from_requirement.py \
  --requirement-file test_req.txt \
  --max-iterations 1
```

## Project Structure

```
CodeGen_SecondVersion/
├── config/
│   ├── agent_config.yaml       # Your configuration (needs to be created)
│   └── example_config.yaml     # Configuration template
├── src/
│   └── agent/
│       ├── base.py             # Base agent class
│       ├── llm/                # LLM wrappers
│       │   ├── factory.py      # LLM factory
│       │   ├── openai_llm.py
│       │   ├── claude_llm.py
│       │   ├── gemini_llm.py
│       │   ├── deepseek_llm.py
│       │   ├── qwen_llm.py
│       │   ├── llama_llm.py
│       │   └── huggingface_llm.py
│       └── requirement_codegen/
│           ├── analyzer.py     # Requirement analyzer
│           ├── corrector.py    # Requirement corrector
│           ├── code_writer.py  # Code generator
│           ├── orchestrator.py # Workflow coordinator
│           └── types.py        # Type definitions
├── visualizer/
│   └── codegen_status.py       # Terminal status visualization
├── generate_code_from_requirement.py  # Main entry script
├── req.txt                     # Example requirement file
└── README.md                   # This document
```

## Contributing

Issues and Pull Requests are welcome!

Before submitting a PR, please ensure:

1. Code passes all tests
2. Necessary documentation has been added
3. Project code style is followed
4. Related README descriptions are updated

## License

This project is licensed under the MIT License. See the license file in the project for details.

## Acknowledgments

Thanks to all LLM providers for making this project possible, and to the open-source community for their contributions.

---

**Issue Feedback**: If you encounter any problems, please submit them in GitHub Issues with error messages and configuration files (hide API keys).
