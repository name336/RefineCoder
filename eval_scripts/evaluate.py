#!/usr/bin/env python3
"""
Unified evaluation script for HumanEvalComm dataset.

Steps:
1. Generate code and run tests (code_generation.py)
2. Generate final report (generate_report.py)
"""

import argparse
import sys
import os
import json
import random

DEFAULT_CONFIG = {
    'experiment': 'codegen_second_version',
    'model': 'gpt-3.5-turbo',
    'topn': 1,
    'temperature': '0.1',
    'config_path': 'config/agent_config.yaml',
    'step': '1,2',
    'max_problems': 1,
    'random_seed': None,
    'test_all_prompts': True
}

sys.path.insert(0, os.path.dirname(__file__))

from code_generation import run_evaluation
from generate_report import store_all_prompts_xlsx, store_results_xlsx, calculate_metrics

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

ALL_PROMPT_TYPES = ['prompt', 'prompt1a', 'prompt1c', 'prompt1p', 'prompt2ac', 'prompt2ap', 'prompt2cp']


def get_available_prompt_types(benchmark_file):
    """
    Scan dataset to find which prompt types actually exist.
    
    Returns:
        dict: mapping from prompt_type to list of problem names that have this prompt type
    """
    if not os.path.exists(benchmark_file):
        raise FileNotFoundError(f'Benchmark file not found: {benchmark_file}')
    
    prompt_type_problems = {pt: [] for pt in ALL_PROMPT_TYPES}
    total_problems = 0
    
    with open(benchmark_file, 'r', encoding='utf-8') as f:
        for line in f:
            problem = json.loads(line)
            problem_name = problem['name']
            total_problems += 1
            for pt in ALL_PROMPT_TYPES:
                if pt in problem and problem[pt] and problem[pt].strip():
                    prompt_type_problems[pt].append(problem_name)
    
    available_prompt_types = {pt: problems for pt, problems in prompt_type_problems.items() if problems}
    
    print(f"\n{'='*60}")
    print(f"Dataset Prompt Type Availability ({total_problems} total problems)")
    print(f"{'='*60}")
    for pt in ALL_PROMPT_TYPES:
        count = len(prompt_type_problems[pt])
        percentage = (count / total_problems * 100) if total_problems > 0 else 0
        status = "[Y]" if count > 0 else "[N]"
        print(f"  {status} {pt:12s}: {count:3d} problems ({percentage:5.1f}%)")
    print(f"{'='*60}")
    
    return available_prompt_types


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


def load_correction_stats_from_file(stats_file):
    """Load correction statistics from file.
    
    Returns:
        dict: Statistics about correction iterations {iterations_count: problem_count}
    """
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
             
                result = {}
                for key, value in data.items():
                    try:
                        int_key = int(key)
                        if int_key in result:
                            result[int_key] += value
                        else:
                            result[int_key] = value
                    except (ValueError, TypeError):
                        continue
                return result
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def run_step1(experiment, model, topn, temperature, config_path, max_problems=None, random_seed=None, prompt_type='', selected_problem_names=None):
    """Step 1: Generate code and run tests
    
    Returns:
        tuple: (output_file, correction_stats) where correction_stats is a dict of iteration counts
    """
    output_file = f"{experiment}_model_{model}_topn_{topn}_temperature_{temperature}.0.log_0"
    correction_stats = run_evaluation(output_file, topn, config_path, max_problems, random_seed, prompt_type, selected_problem_names)
    log_record_dir = os.path.join(SCRIPT_DIR, 'log', 'record')
    stats_file = os.path.join(log_record_dir, output_file.replace('.log_0', '_correction_stats.json'))
    file_stats = load_correction_stats_from_file(stats_file)
    if file_stats:
        correction_stats = file_stats
    
    return output_file, correction_stats


def run_step2(experiment, model, topn, temperature, available_prompt_types, prompt_type='', test_all_prompts=False):
    """Step 2: Generate final report"""
    import generate_report as gr
    
    gr.experiment = experiment
    gr.dataset = 'HumanEvalComm'
    gr.model = model
    gr.temperature = temperature
    gr.topn = topn
    
    if test_all_prompts:
        excel_path = store_all_prompts_xlsx(
            experiment, 'HumanEvalComm', model, topn, temperature, prompt_type, 
            available_prompt_types, suppress_warnings=True
        )
    else:
        metrics = calculate_metrics(prompt_type)
        output_file = f"{experiment}_dataset_HumanEvalComm_model_{model}_topn_{topn}_temperature_{temperature}{prompt_type}"
        excel_path = store_results_xlsx(metrics, output_file, suppress_warnings=True)
    
    return excel_path


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation pipeline for HumanEvalComm dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all steps
  python evaluate.py -e codegen -m codegen -n 5 -t 1 -c config/agent_config.yaml
  
  # Run only step 1 (code generation)
  python evaluate.py -e codegen -m codegen -n 5 -t 1 -c config/agent_config.yaml --step 1
  
  # Run only step 2 (report generation)
  python evaluate.py -e codegen -m codegen -n 5 -t 1 --step 2
  
  # Quick test: only process 5 random problems
  python evaluate.py -e test -m test -n 1 -t 1 -c config/agent_config.yaml --max-problems 5
  
  # Process with fixed random seed for reproducibility
  python evaluate.py -e test -m test -n 1 -t 1 -c config/agent_config.yaml --max-problems 10 --random-seed 42
        """
    )
    
    parser.add_argument("--config-file", type=str, help="Path to JSON configuration file", default=None)
    parser.add_argument("-e", "--experiment", type=str, help="Experiment name", default=None)
    parser.add_argument("-m", "--model", type=str, help="Model name", default=None)
    parser.add_argument("-n", "--topn", type=int, help="Top N candidates", default=None)
    parser.add_argument("-t", "--temperature", type=str, help="Temperature parameter", default=None)
    parser.add_argument("-c", "--config", type=str, help="CodeGen config file path", default=None)
    parser.add_argument("-pt", "--prompt_type", type=str, 
                        choices=['', 'prompt1a', 'prompt1c', 'prompt1p', 'prompt2ac', 'prompt2ap', 'prompt2cp'],
                        help="Prompt type", default=None)
    parser.add_argument("--test-all-prompts", action="store_true", help="Calculate metrics for all prompt types in step 2")
    parser.add_argument("--step", type=str, help="Steps to run (1, 2, or comma-separated)", default=None)
    parser.add_argument("--max-problems", type=int, help="Max problems to process", default=None)
    parser.add_argument("--random-seed", type=int, help="Random seed for problem selection", default=None)
    
    args = parser.parse_args()
    
    config = DEFAULT_CONFIG.copy()
    if args.config_file and os.path.exists(args.config_file):
        with open(args.config_file, 'r', encoding='utf-8') as f:
            config.update(json.load(f))
    
    if args.experiment is not None:
        config['experiment'] = args.experiment
    if args.model is not None:
        config['model'] = args.model
    if args.topn is not None:
        config['topn'] = args.topn
    if args.temperature is not None:
        config['temperature'] = args.temperature
    if args.config is not None:
        config['config_path'] = args.config
    if args.prompt_type is not None:
        config['prompt_type'] = args.prompt_type
    if args.step is not None:
        config['step'] = args.step
    if args.test_all_prompts:
        config['test_all_prompts'] = True
    
    config['config_path'] = resolve_config_path(config['config_path'])
    
    if not config.get('experiment'):
        print("Error: Experiment name is required (-e/--experiment)")
        sys.exit(1)
    
    if not config.get('model'):
        print("Error: Model name is required (-m/--model)")
        sys.exit(1)
    
    steps_to_run = [int(s.strip()) for s in config['step'].split(',')]
    
    if 1 in steps_to_run:
        if not os.path.exists(config['config_path']):
            print(f"Error: Config file not found: {config['config_path']}")
            sys.exit(1)
    
    benchmark_file = os.path.join(SCRIPT_DIR, 'Benchmark', 'HumanEvalComm_v2.jsonl')
    if not os.path.exists(benchmark_file):
        benchmark_file = 'Benchmark/HumanEvalComm_v2.jsonl'
    
    available_prompt_types = get_available_prompt_types(benchmark_file)
    
    log_file = None
    excel_file = None
    
    try:
        if 1 in steps_to_run:
            max_problems = args.max_problems if args.max_problems is not None else config.get('max_problems')
            random_seed = args.random_seed if args.random_seed is not None else config.get('random_seed')
            prompt_type = config.get('prompt_type', '')
            
            log_files = []
            selected_problem_names = None
            all_correction_stats = {}  # Collect all correction stats across prompt types
            comm_requirements = 0  # Total number of requirements for specific prompt types (1a, 1c, 1p, 2ac, 2cp, 2ap)
            
            if max_problems is not None and max_problems > 0:
                print(f"\n{'='*60}")
                print(f"Selecting {max_problems} problems from HumanEvalComm dataset")
                print(f"{'='*60}")
                
                problem_list = []
                with open(benchmark_file, 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        problem_list.append(json.loads(line))
                
                unique_problem_names = list(set([p['name'] for p in problem_list]))
                
                if random_seed is not None:
                    random.seed(random_seed)
                    print(f'Using random seed: {random_seed}', flush=True)
                
                if len(unique_problem_names) > max_problems:
                    selected_problem_names = random.sample(unique_problem_names, max_problems)
                    print(f'Selected {max_problems} problems: {selected_problem_names}', flush=True)
                else:
                    selected_problem_names = unique_problem_names
            
            for pt in ALL_PROMPT_TYPES:
                if pt not in available_prompt_types:
                    print(f"\n{'='*60}")
                    print(f"Skipping prompt type: {pt} (not found in dataset)")
                    print(f"{'='*60}")
                    continue
                
                problems_with_pt = available_prompt_types[pt]
                if selected_problem_names:
                    problems_to_process = [p for p in selected_problem_names if p in problems_with_pt]
                else:
                    problems_to_process = problems_with_pt
                
                if not problems_to_process:
                    print(f"\n{'='*60}")
                    print(f"Skipping prompt type: {pt} (no selected problems have this prompt type)")
                    print(f"{'='*60}")
                    continue
                
                print(f"\n{'='*60}")
                print(f"Processing prompt type: {pt} ({len(problems_to_process)} problems)")
                print(f"{'='*60}")
                log_file, correction_stats = run_step1(config['experiment'], config['model'], config['topn'], 
                         config['temperature'], config['config_path'], None, None, pt, problems_to_process)
                log_files.append(log_file)
                
                # Only count requirements for specific prompt types (exclude 'prompt')
                if pt in ['prompt1a', 'prompt1c', 'prompt1p', 'prompt2ac', 'prompt2cp', 'prompt2ap']:
                    comm_requirements += len(problems_to_process)
                    log_record_dir = os.path.join(SCRIPT_DIR, 'log', 'record')
                    stats_file = os.path.join(log_record_dir, log_file.replace('.log_0', '_correction_stats.json'))
                    file_stats = load_correction_stats_from_file(stats_file)
                    stats_to_merge = file_stats if file_stats else correction_stats
                    for iterations, count in stats_to_merge.items():
                        if iterations not in all_correction_stats:
                            all_correction_stats[iterations] = 0
                        all_correction_stats[iterations] += count
            
            log_file = log_files[0] if log_files else None
            
          
            if log_file:
                log_record_dir = os.path.join(SCRIPT_DIR, 'log', 'record')
                stats_file = os.path.join(log_record_dir, log_file.replace('.log_0', '_correction_stats.json'))
                final_file_stats = load_correction_stats_from_file(stats_file)
                if final_file_stats:
                    all_correction_stats = final_file_stats
            
            # Print correction statistics summary
            if all_correction_stats or comm_requirements > 0:
                print(f"\n{'='*60}")
                print("Correction Iterations Statistics (HumanEvalComm Dataset)")
                print(f"{'='*60}")
                print("Only includes prompt types: 1a, 1c, 1p, 2ac, 2cp, 2ap")
                print(f"{'='*60}")
                print(f"Total requirements processed: {comm_requirements}")
                print(f"\nDistribution of correction iterations:")
                for i in range(5):  # 0 to 4 iterations
                    count = all_correction_stats.get(i, 0)
                    percentage = (count / comm_requirements * 100) if comm_requirements > 0 else 0
                    bar = '█' * int(percentage / 2)  # Visual bar (50% = 25 chars)
                    print(f"  {i} iterations: {count:4d} requirements ({percentage:5.1f}%) {bar}")
                print(f"{'='*60}\n")
        
        if 2 in steps_to_run:
            if 1 not in steps_to_run:
                available_prompt_types = get_available_prompt_types(benchmark_file)
            test_all_prompts = config.get('test_all_prompts', False)
            excel_file = run_step2(config['experiment'], config['model'], 
                     config['topn'], config['temperature'], available_prompt_types, 
                     config.get('prompt_type', ''), test_all_prompts)
        
        print()
        if log_file:
            print(f"Log file: log/record/{log_file}")
        if excel_file:
            print(f"Excel file: {excel_file}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
