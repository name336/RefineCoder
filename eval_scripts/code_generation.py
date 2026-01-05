import argparse
import json
import os
import subprocess
import sys
import random
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
from src.agent.requirement_codegen import generate_code_from_requirement

# Import code fixing utilities
from code_fixes import (
    find_main_function_to_replace,
    replace_function_name,
)


def extract_function_name(code: str) -> str:
    """Extract the first function name from code."""
    pattern = r'^\s*def\s+(\w+)\s*\('
    for line in code.split('\n'):
        match = re.match(pattern, line)
        if match:
            return match.group(1)
    return ''


def extract_function_name_from_requirement(requirement: str) -> str:
    """Extract the primary function name from requirement text."""
    match = re.search(r'def\s+(\w+)\s*\(', requirement)
    return match.group(1) if match else ''


def requirement_uses_candidate(requirement: str) -> bool:
    """Check if the requirement uses 'candidate' as the function name."""
    return extract_function_name_from_requirement(requirement) == 'candidate'


def preprocess_requirement_for_function_name(requirement: str, entry_point: str) -> str:
    """Replace 'candidate' with entry_point in requirement if needed."""
    if not requirement_uses_candidate(requirement):
        return requirement
    
    processed = re.sub(r'def\s+candidate\s*\(', f'def {entry_point}(', requirement)
    processed = re.sub(r'\bcandidate\s*\(', f'{entry_point}(', processed)
    return processed


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


def solution_evaluation(solution, test_cases, demo_file, call_demo_file_base, entry_point, time_limit, candidate_index, original_uses_candidate=True):
    """Evaluate solution with test cases."""
    passed_case = []
    case_status = []

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


def is_valid_code(code: str) -> tuple[bool, str]:
    """Check if the generated code is valid.
    
    Validates that:
    1. Code is not empty
    2. Code does not contain unparsed XML/JSON tags
    3. Code contains valid Python syntax (at least a function definition)
    """
    if not code or code.strip() == '':
        return False, "empty code"
    
    code_lower = code.lower()
    
    # Check for unparsed XML tags from agent outputs
    invalid_tags = [
        '<code_deliverable>', '</code_deliverable>',
        '<final_requirement>', '</final_requirement>',
        '<analysis>', '</analysis>',
        '<correction>', '</correction>',
    ]
    for tag in invalid_tags:
        if tag in code_lower:
            return False, f"contains unparsed tag: {tag} (output parsing failed)"
    
    # Check for raw JSON structure
    if code.strip().startswith('{') and '"code"' in code:
        return False, "contains raw JSON structure (JSON parsing failed)"
    
    # Check for valid Python code (should contain at least one function definition)
    if 'def ' not in code:
        return False, "no function definition found (invalid Python code)"
    
    return True, ""


def generate_code_with_codegen(requirement, config_path='config/agent_config.yaml', max_retries=3, entry_point=None):
    """Generate code using CodeGen project with retry mechanism.
    
    Returns:
        tuple: (code, correction_iterations) where correction_iterations is the number of analyzer-corrector rounds
    """
    resolved_path = resolve_config_path(config_path)
    
    
    for attempt in range(1, max_retries + 1):
        try:
            result = generate_code_from_requirement(
                requirement=requirement,
                config_path=resolved_path,
                max_iterations=None,
            )
            code = result.code
            correction_iterations = result.correction_iterations
            
            is_valid, error_reason = is_valid_code(code)
            
            if is_valid:
                if attempt > 1:
                    print(f'[Retry success on attempt {attempt}]', end=' ', flush=True)
                return code, correction_iterations
            else:
                print(f'\n     [Code Gen] Attempt {attempt}/{max_retries} failed: {error_reason}', flush=True)
                if result.assumptions:
                    print(f'     [Code Gen] Assumptions/Errors: {result.assumptions}', flush=True)
                if attempt < max_retries:
                    print(f'     [Code Gen] Retrying...', flush=True)
                else:
                    print(f'     [Code Gen] All {max_retries} attempts failed, returning empty code', flush=True)
                    return '', 0
                    
        except Exception as e:
            import traceback
            print(f'\n     [Code Gen] Attempt {attempt}/{max_retries} exception: {e}', flush=True)
            print(f'     [Code Gen] Traceback: {traceback.format_exc()[:500]}', flush=True)
            if attempt < max_retries:
                print(f'     [Code Gen] Retrying...', flush=True)
            else:
                print(f'     [Code Gen] All {max_retries} attempts failed due to exceptions', flush=True)
                return '', 0
    
    return '', 0


def load_correction_stats(stats_file):
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


def save_correction_stats(stats_file, correction_stats):
    """Save correction statistics to file.
    
    Args:
        stats_file: Path to statistics file
        correction_stats: Dictionary of statistics {iterations_count: problem_count}
    """
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(correction_stats, f, indent=2)
    except IOError as e:
        print(f'Warning: Failed to save correction statistics: {e}', flush=True)


def run_evaluation(output_file, topn, config_path='config/agent_config.yaml', max_problems=None, random_seed=None, prompt_type='', selected_problem_names=None):
    """Main evaluation process for HumanEvalComm dataset.
    
    Returns:
        dict: Statistics about correction iterations (only for HumanEvalComm prompt types)
    """
    temp_files_base = os.path.join(SCRIPT_DIR, 'temp_files')
    os.makedirs(temp_files_base, exist_ok=True)
    
    dataset_name = 'HumanEvalComm'
    names = []
    
    log_record_dir = os.path.join(SCRIPT_DIR, 'log', 'record')
    os.makedirs(log_record_dir, exist_ok=True)
    record_file = os.path.join(log_record_dir, output_file)
    
    # Statistics file for persistent storage
    stats_file = os.path.join(log_record_dir, output_file.replace('.log_0', '_correction_stats.json'))
    
    # Load existing correction statistics (only for specific prompt types)
    correction_stats = load_correction_stats(stats_file)  # {iterations_count: problem_count}
    
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
    benchmark_file = os.path.join(SCRIPT_DIR, 'Benchmark', 'HumanEvalComm_v2.jsonl')
    if not os.path.exists(benchmark_file):
        benchmark_file = 'Benchmark/HumanEvalComm_v2.jsonl'
    
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
        original_uses_candidate = requirement_uses_candidate(requirement)
        
        for index in range(topn):
            print(f'Generating candidate {index + 1}/{topn}...', end=' ', flush=True)
            
            code, correction_iterations = generate_code_with_codegen(requirement, config_path, entry_point=entry_point)
            
            # Collect correction statistics for all prompt types
            if index == 0 and (prompt_type in ['prompt', 'prompt1a', 'prompt1c', 'prompt1p', 'prompt2ac', 'prompt2cp', 'prompt2ap'] or not prompt_type):
                if correction_iterations not in correction_stats:
                    correction_stats[correction_iterations] = 0
                correction_stats[correction_iterations] += 1
                # Save statistics immediately to prevent data loss on interruption
                save_correction_stats(stats_file, correction_stats)
            
            demo_file = os.path.join(problem_dir, f'demo_{index}.py')
            call_demo_file_base = os.path.join(problem_dir, f'call_demo_{index}')
            
            test_case_solved = ['', '']
            if code == '':
                print('FAILED (code generation)', flush=True)
                test_case_solved = [[], []]
            else:
                test_case_solved = solution_evaluation(
                    code, test_set, demo_file, call_demo_file_base, 
                    entry_point, time_limit, index,
                    original_uses_candidate=original_uses_candidate
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
    
    # Final save of correction statistics
    save_correction_stats(stats_file, correction_stats)
    
    return correction_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=str, help="Output filename", required=True)
    parser.add_argument("-n", "--topn", type=int, help="Top N candidates", default=5)
    parser.add_argument("-c", "--config", type=str, help="CodeGen config file path", default="config/agent_config.yaml")
    parser.add_argument("--max-problems", type=int, help="Max problems to process", default=None)
    parser.add_argument("--random-seed", type=int, help="Random seed for problem selection", default=None)

    args = parser.parse_args()
    run_evaluation(args.file, args.topn, args.config, args.max_problems, args.random_seed)

