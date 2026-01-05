"""
Evaluation script for ablation study: Direct LLM API code generation.

This script evaluates code generation by directly calling LLM API
without using the multi-agent collaboration framework.
"""

import argparse
import json
import os
import subprocess
import sys
import random
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from code_generation import (
    generate_code_with_direct_llm,
)

# Import code fixing utilities from parent directory
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
from code_fixes import (
    find_main_function_to_replace,
    replace_function_name,
)


def solution_evaluation(solution, test_cases, demo_file, call_demo_file_base, entry_point, time_limit, candidate_index, original_uses_candidate=None):
    """Evaluate solution with test cases."""
    passed_case = []
    case_status = []

    # Fix function name to match entry_point (for ablation study)
    main_function_to_replace = find_main_function_to_replace(solution, entry_point)
    if main_function_to_replace:
        solution = replace_function_name(solution, main_function_to_replace, entry_point)
    # Also replace any remaining 'candidate(' calls
    if 'candidate(' in solution:
        solution = solution.replace('candidate(', entry_point + '(')
    
    solution = solution.replace('print(', '# print(')

    with open(demo_file, 'w', encoding='utf-8') as f:
        f.write(solution)
    
    demo_dir = os.path.dirname(os.path.abspath(demo_file))
    demo_module = os.path.splitext(os.path.basename(demo_file))[0]
    
    if demo_dir not in sys.path:
        sys.path.insert(0, demo_dir)
    
    for i in range(len(test_cases)):
        call_demo_file = f"{call_demo_file_base}_{i}.py"
        
        if test_cases[i]['relation'] == '==':
            with open(call_demo_file, 'w', encoding='utf-8') as f:
                f.write('import sys\n')
                f.write(f"sys.path.insert(0, r'{demo_dir}')\n")
                f.write(f'from {demo_module} import {entry_point}\n')
                f.write(f'print({entry_point}({test_cases[i]["input"]}))\n')
            try:
                output = subprocess.run([sys.executable, call_demo_file], capture_output=True, text=True, timeout=time_limit, cwd=SCRIPT_DIR)
            except subprocess.TimeoutExpired:
                case_status.append('Timeout')
                continue
            except Exception:
                case_status.append('Exception')
                continue
            if output.returncode != 0:
                case_status.append('execution error: %s' % output.returncode)
            else:
                case_status.append(output.stdout.strip())
            if test_cases[i]['output'].strip() == output.stdout.strip():
                passed_case.append(i)
        else:
            if '$input$' in test_cases[i]['relation'] or '$demo$' in test_cases[i]['relation']:
                with open(call_demo_file, 'w', encoding='utf-8') as f:
                    f.write('import sys\n')
                    f.write(f"sys.path.insert(0, r'{demo_dir}')\n")
                    f.write(f'from {demo_module} import {entry_point}\n')
                    relation_code = test_cases[i]['relation'].replace('$input$', str(test_cases[i]['input'])).replace('$demo$', demo_module)
                    f.write(relation_code)
                try:
                    output = subprocess.run([sys.executable, call_demo_file], capture_output=True, text=True, timeout=time_limit, cwd=SCRIPT_DIR)
                except subprocess.TimeoutExpired:
                    case_status.append('Timeout')
                    continue
                except Exception:
                    case_status.append('Exception')
                    continue
                if output.returncode != 0:
                    case_status.append('execution error: %s' % output.returncode)
                else:
                    case_status.append(output.stdout.strip())
                if output.stdout.strip() == 'True':
                    passed_case.append(i)
            else:
                with open(call_demo_file, 'w', encoding='utf-8') as f:
                    f.write('import sys\n')
                    f.write(f"sys.path.insert(0, r'{demo_dir}')\n")
                    f.write(f'from {demo_module} import {entry_point}\n')
                    relation_code = test_cases[i]['relation'].replace('candidate', entry_point)
                    f.write(f'print({relation_code})')
                try:
                    output = subprocess.run([sys.executable, call_demo_file], capture_output=True, text=True, timeout=time_limit, cwd=SCRIPT_DIR)
                except subprocess.TimeoutExpired:
                    case_status.append('Timeout')
                    continue
                except Exception:
                    case_status.append('Exception')
                    continue
                if output.returncode != 0:
                    case_status.append('execution error: %s' % output.returncode)
                else:
                    case_status.append(output.stdout.strip())
                if output.stdout.strip() == 'True':
                    passed_case.append(i)

    return passed_case, case_status


def run_evaluation(
    output_file, 
    topn, 
    config_path='config/agent_config.yaml',
    temperature=0.3,
    max_problems=None, 
    random_seed=None, 
    prompt_type='', 
    selected_problem_names=None
):
    """Main evaluation process for HumanEvalComm dataset using direct LLM API."""
    # Use the same temp_files and log directories as the main evaluation script
    eval_scripts_dir = os.path.dirname(SCRIPT_DIR)
    temp_files_base = os.path.join(eval_scripts_dir, 'temp_files')
    os.makedirs(temp_files_base, exist_ok=True)
    
    dataset_name = 'HumanEvalComm'
    names = []
    
    log_record_dir = os.path.join(eval_scripts_dir, 'log', 'record')
    os.makedirs(log_record_dir, exist_ok=True)
    record_file = os.path.join(log_record_dir, output_file)
    
    if not os.path.exists(record_file):
        with open(record_file, 'w') as f:
            f.write('')
    else:
        with open(record_file, 'r') as f:
            for line in f.readlines():
                if line.strip():
                    content = json.loads(line)
                    names.append(content['name'])
    
    problem_list = []
    # Try multiple paths for benchmark file
    benchmark_file = os.path.join(SCRIPT_DIR, '..', 'Benchmark', 'HumanEvalComm_v2.jsonl')
    if not os.path.exists(benchmark_file):
        benchmark_file = os.path.join(PROJECT_ROOT, 'eval_scripts', 'Benchmark', 'HumanEvalComm_v2.jsonl')
    if not os.path.exists(benchmark_file):
        # Fallback to relative path from eval_scripts
        benchmark_file = os.path.join(os.path.dirname(SCRIPT_DIR), 'Benchmark', 'HumanEvalComm_v2.jsonl')
    
    if not os.path.exists(benchmark_file):
        raise FileNotFoundError(f'Benchmark file not found: {benchmark_file}')
    
    with open(benchmark_file, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            problem_list.append(json.loads(line))

    problem_info = {}
    for i in range(len(problem_list)):
        original_name = problem_list[i]['name']
        
        if selected_problem_names is not None and original_name not in selected_problem_names:
            continue
        
        if selected_problem_names is None:
            if prompt_type and prompt_type != 'prompt':
                name_with_prompt = f"{original_name}_{prompt_type}"
                if name_with_prompt in names:
                    continue
            else:
                if original_name in names:
                    continue
        
        problem_info[original_name] = {
            'name': original_name,
            'index_num': i,
            'time_limit': 3
        }

    problem_items = list(problem_info.items())
    
    if selected_problem_names is not None:
        problem_items = [(name, info) for name, info in problem_items if name in selected_problem_names]
        if len(problem_items) > 0:
            print(f'Processing {len(problem_items)} pre-selected problem(s) for prompt type: {prompt_type if prompt_type else "prompt"}', flush=True)
    elif max_problems is not None and max_problems > 0:
        if random_seed is not None:
            random.seed(random_seed)
            print(f'Using random seed: {random_seed}', flush=True)
        
        if len(problem_items) > max_problems:
            problem_items = random.sample(problem_items, max_problems)
            print(f'Randomly selected {max_problems} problems from {len(problem_info)} total problems', flush=True)
    
    problem_dic = {}
    total_problems = len(problem_items)
    processed_count = 0
    
    for name, info in problem_items:
        problem_key = name
        
        if prompt_type and prompt_type != 'prompt':
            problem_key_with_prompt = f"{problem_key}_{prompt_type}"
        else:
            problem_key_with_prompt = problem_key
        
        if problem_key_with_prompt in names:
            continue
        
        processed_count += 1
        print(f'\n[{processed_count}/{total_problems}] Processing: {problem_key_with_prompt}', flush=True)
        
        problem_dic[problem_key_with_prompt] = {
            'name': problem_key_with_prompt,
            'code_candidates': []
        }
        
        problem = problem_list[info['index_num']]
        test_set = problem['test_case']
        time_limit = info['time_limit']
        
        problem_name_parts = problem_key.split('/')
        if len(problem_name_parts) >= 2:
            problem_id = problem_name_parts[1]
        else:
            problem_id = problem_key.replace('/', '_')
        
        dataset_dir = os.path.join(temp_files_base, dataset_name)
        os.makedirs(dataset_dir, exist_ok=True)
        problem_dir = os.path.join(dataset_dir, f'{dataset_name}_{problem_id}')
        os.makedirs(problem_dir, exist_ok=True)
        
        if prompt_type:
            prompt_dir = os.path.join(problem_dir, f'{dataset_name}_{problem_id}_{prompt_type}')
            os.makedirs(prompt_dir, exist_ok=True)
            problem_dir = prompt_dir
        
        if prompt_type == 'prompt' or not prompt_type:
            requirement = problem.get('prompt', '')
        elif prompt_type in problem and problem[prompt_type] and problem[prompt_type].strip():
            requirement = problem[prompt_type]
        else:
            print(f'Skipping: prompt type "{prompt_type}" not found in this problem', flush=True)
            continue
        
        candidate_results = []
        entry_point = problem['entry_point']
        
        for index in range(topn):
            print(f'Generating candidate {index + 1}/{topn}...', end=' ', flush=True)
            
            code = generate_code_with_direct_llm(
                requirement, 
                config_path, 
                temperature=temperature,
                entry_point=entry_point
            )
            
            demo_file = os.path.join(problem_dir, f'demo_{index}.py')
            call_demo_file_base = os.path.join(problem_dir, f'call_demo_{index}')
            
            test_case_solved = ['', '']
            if code == '':
                print('FAILED (code generation)', flush=True)
                test_case_solved = [[], []]
            else:
                test_case_solved = solution_evaluation(
                    code, test_set, demo_file, call_demo_file_base, 
                    entry_point, time_limit, index
                )
                pass_count = len(test_case_solved[0])
                total_tests = len(test_set)
                print(f'{pass_count}/{total_tests} tests passed', flush=True)
            
            res = {
                'code': code,
                'index': index,
                'passed_case': test_case_solved[0],
                'case_status': test_case_solved[1],
            }
            problem_dic[problem_key_with_prompt]['code_candidates'].append(res)
            candidate_results.append((len(test_case_solved[0]), len(test_set)))
        
        best_pass = max([r[0] for r in candidate_results], default=0)
        total_tests = candidate_results[0][1] if candidate_results else 0
        print(f'Completed: Best result {best_pass}/{total_tests} tests passed', flush=True)
        
        problem_dic[problem_key_with_prompt]['dataset'] = dataset_name
        if prompt_type:
            problem_dic[problem_key_with_prompt]['prompt_type'] = prompt_type
        
        json_str = json.dumps(problem_dic[problem_key_with_prompt])
        with open(record_file, 'a') as f:
            f.write(json_str + '\n')
        problem_dic.pop(problem_key_with_prompt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=str, help="Output filename", required=True)
    parser.add_argument("-n", "--topn", type=int, help="Top N candidates", default=5)
    parser.add_argument("-c", "--config", type=str, help="LLM config file path", default="config/agent_config.yaml")
    parser.add_argument("-t", "--temperature", type=float, help="Temperature parameter", default=0.3)
    parser.add_argument("--max-problems", type=int, help="Max problems to process", default=None)
    parser.add_argument("--random-seed", type=int, help="Random seed for problem selection", default=None)

    args = parser.parse_args()
    run_evaluation(
        args.file, 
        args.topn, 
        args.config, 
        temperature=args.temperature,
        max_problems=args.max_problems, 
        random_seed=args.random_seed
    )

