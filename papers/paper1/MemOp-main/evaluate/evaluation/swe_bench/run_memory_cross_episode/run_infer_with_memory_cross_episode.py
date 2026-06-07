import os
import sys
import copy
import json
import toml
import asyncio
import pandas as pd
from tqdm import tqdm
from typing import Any, Literal
from datasets import load_dataset
from jinja2 import Environment, FileSystemLoader

# Add memop to path for cross-episode memory imports
MEMOP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'memop')
sys.path.insert(0, MEMOP_DIR)

import openhands.agenthub
from openhands.core.config import (
    get_parser,
    get_llm_config_arg,
)
from evaluation.utils.shared import (
    EvalException,
    EvalMetadata,
    EvalOutput,
    assert_and_raise,
    codeact_user_response,
    get_default_sandbox_config_for_eval,
    get_metrics,
    is_fatal_evaluation_error,
    make_metadata,
    prepare_dataset,
    reset_logger_for_multiprocessing,
    run_evaluation,
    update_llm_config_for_completions_logging,
)
from evaluation.swe_bench.run_infer import (
    set_dataset_type,
    _get_swebench_workspace_dir_name,
    get_config,
    initialize_runtime,
    complete_runtime,
    # filter_dataset,
)
from openhands.critic import AgentFinishedCritic
from openhands.events.action import MessageAction
from openhands.controller.state.state import State
from openhands.utils.async_utils import call_async_from_sync
from openhands.core.logger import openhands_logger as logger
from openhands.core.main import create_runtime, run_controller
from openhands.core.config.utils import get_condenser_config_arg
from openhands.core.config.condenser_config import NoOpCondenserConfig
from openhands.events.serialization.event import event_from_dict, event_to_dict
from evaluation.swe_bench.resource.swt_bench_constants import MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE


################################
#         Memory Macro
################################
# RUN_WITH_MEMORY = os.environ.get('RUN_WITH_MEMORY', 'false').lower() == 'true'
RUN_WITH_MEMORY = True

################################
#        Inference Macro
################################
USE_HINT_TEXT = os.environ.get('USE_HINT_TEXT', 'false').lower() == 'true'
RUN_WITH_BROWSING = os.environ.get('RUN_WITH_BROWSING', 'false').lower() == 'true'
ENABLE_LLM_EDITOR = os.environ.get('ENABLE_LLM_EDITOR', 'false').lower() == 'true'
BenchMode = Literal['swe', 'swt', 'swt-ci']

# Global variable to track dataset type
DATASET_TYPE = 'SWE-bench'

AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {
    'CodeActAgent': codeact_user_response,
}

# TODO: migrate all swe-bench docker to ghcr.io/openhands
DEFAULT_DOCKER_IMAGE_PREFIX = os.environ.get(
    'EVAL_DOCKER_IMAGE_PREFIX', 'docker.io/xingyaoww/'
)
logger.info(f'Default docker image prefix: {DEFAULT_DOCKER_IMAGE_PREFIX}')



def get_instruction(instance: pd.Series, metadata: EvalMetadata) -> MessageAction:
    workspace_dir_name = _get_swebench_workspace_dir_name(instance)
    mode = metadata.details['mode']
    llm_model = metadata.llm_config.model

    # Determine the template file based on mode and LLM
    if mode.startswith('swt'):
        template_name = 'swt.j2'
    elif mode == 'swe':
        if 'claude' in llm_model:
            template_name = 'swe_claude.j2'
        elif 'gemini' in llm_model:
            template_name = 'swe_gemini.j2'
        elif 'gpt-4.1' in llm_model:
            template_name = 'swe_gpt4.j2'
        else:
            template_name = (
                'swe_default.j2'  # Default for 'swe' mode (regular swe-bench)
            )
    else:
        # Fallback or error handling if mode is unexpected
        logger.error(f'Unexpected evaluation mode: {mode}. Falling back to default.')
        template_name = 'swe_default.j2'

    # Set up Jinja2 environment
    # Assuming templates are in 'evaluation/swe_bench/prompts' relative to this script
    prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
    env = Environment(loader=FileSystemLoader(prompts_dir))
    template = env.get_template(template_name)

    # Prepare context for rendering
    context = {
        'instance': instance,
        'workspace_dir_name': workspace_dir_name,
        'metadata': metadata,  # Pass metadata if needed in templates
    }

    # Add specific context for swt-ci mode if needed
    if mode == 'swt-ci':
        context['test_instructions'] = (
            f'The following command can be used to run the tests: `{list(MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE[instance.repo].values())[0]}`. Make sure they fail in the expected way.\n'
        )
    else:
        context['test_instructions'] = ''  # Ensure it's defined for other modes

    # Render the instruction
    instruction = template.render(context)

    if RUN_WITH_BROWSING:
        instruction += (
            '<IMPORTANT!>\nYou SHOULD NEVER attempt to browse the web. </IMPORTANT!>\n'
        )

    if RUN_WITH_MEMORY:
        instruction += (
            "\n[TASK INSTRUCTION]"
            f"\nHere are some information about this repository that may be helpful to you:\n{metadata.details['memory'][instance.instance_id]}"
        )

    if 'image_assets' in instance:
        assets = json.loads(instance['image_assets'])
        assert 'problem_statement' in assets, (
            'problem_statement is required in image_assets'
        )
        image_urls = assets['problem_statement']
        return MessageAction(content=instruction, image_urls=image_urls)
    return MessageAction(content=instruction)

def process_instance(
    instance: pd.Series,
    metadata: EvalMetadata,
    reset_logger: bool = True,
    runtime_failure_count: int = 0,
) -> EvalOutput:
    config = get_config(instance, metadata)

    # Setup the logger properly, so you can run multi-processing to parallelize the evaluation
    if reset_logger:
        log_dir = os.path.join(metadata.eval_output_dir, 'infer_logs')
        reset_logger_for_multiprocessing(logger, instance.instance_id, log_dir)
    else:
        logger.info(f'Starting evaluation for instance {instance.instance_id}.')

    # Increase resource_factor with increasing attempt_id
    if runtime_failure_count > 0:
        config.sandbox.remote_runtime_resource_factor = min(
            config.sandbox.remote_runtime_resource_factor * (2**runtime_failure_count),
            8,
        )
        logger.warning(
            f'This is the {runtime_failure_count + 1}th attempt for instance {instance.instance_id}, setting resource factor to {config.sandbox.remote_runtime_resource_factor}'
        )

    metadata = copy.deepcopy(metadata)
    metadata.details['runtime_failure_count'] = runtime_failure_count
    metadata.details['remote_runtime_resource_factor'] = (
        config.sandbox.remote_runtime_resource_factor
    )

    runtime = create_runtime(config)
    call_async_from_sync(runtime.connect)

    try:
        initialize_runtime(runtime, instance, metadata)

        message_action = get_instruction(instance, metadata)

        # Here's how you can run the agent (similar to the `main` function) and get the final task state
        state: State | None = asyncio.run(
            run_controller(
                config=config,
                initial_user_action=message_action,
                runtime=runtime,
                fake_user_response_fn=AGENT_CLS_TO_FAKE_USER_RESPONSE_FN[
                    metadata.agent_class
                ],
            )
        )

        # if fatal error, throw EvalError to trigger re-run
        if is_fatal_evaluation_error(state.last_error):
            raise EvalException('Fatal error detected: ' + state.last_error)

        # ======= THIS IS SWE-Bench specific =======
        # Get git patch
        if DATASET_TYPE == 'SWE-bench-Live':
            from evaluation.swe_bench.live_utils import (
                complete_runtime as complete_runtime_fn,
            )
        else:
            complete_runtime_fn = complete_runtime
        return_val = complete_runtime_fn(runtime, instance)
        git_patch = return_val['git_patch']
        logger.info(
            f'Got git diff for instance {instance.instance_id}:\n--------\n{git_patch}\n--------'
        )
    finally:
        runtime.close()
    # ==========================================

    # ======= Attempt to evaluate the agent's edits =======
    # we use eval_infer.sh to evaluate the agent's edits, not here
    # because the agent may alter the environment / testcases
    test_result = {
        'git_patch': git_patch,
    }

    # If you are working on some simpler benchmark that only evaluates the final model output (e.g., in a MessageAction)
    # You can simply get the LAST `MessageAction` from the returned `state.history` and parse it for evaluation.
    if state is None:
        raise ValueError('State should not be None.')

    # NOTE: this is NO LONGER the event stream, but an agent history that includes delegate agent's events
    histories = [event_to_dict(event) for event in state.history]
    metrics = get_metrics(state)

    # Save the output
    instruction = message_action.content
    if message_action.image_urls:
        instruction += (
            '\n\n<image_urls>' + '\n'.join(message_action.image_urls) + '</image_urls>'
        )
    output = EvalOutput(
        instance_id=instance.instance_id,
        instruction=instruction,
        instance=instance.to_dict(),  # SWE Bench specific
        test_result=test_result,
        metadata=metadata,
        history=histories,
        metrics=metrics,
        error=state.last_error if state and state.last_error else None,
    )
    return output



####################################
#         Memory Functions
####################################

def shuffle_and_sample_dataset(dataset: pd.DataFrame, eval_n_limit: int) -> pd.DataFrame:
    """Randomly shuffle the dataset and take the first eval_n_limit samples."""
    shuffled = dataset.sample(frac=1, random_state=42).reset_index(drop=True)
    sampled = shuffled.head(eval_n_limit)
    logger.info(f'Shuffled and sampled {len(sampled)} instances from {len(dataset)} (eval_n_limit={eval_n_limit})')
    return sampled

def filter_dataset(dataset: pd.DataFrame, filter_column: str, eval_n_limit: int = None, target_ids: list = None) -> pd.DataFrame:
    # If target_ids is provided, use it directly for filtering
    if target_ids is not None:
        logger.info(f'Filtering {len(target_ids)} tasks from provided target_ids...')
        subset = dataset[dataset[filter_column].isin(target_ids)]
        logger.info(f'Retained {subset.shape[0]} tasks after filtering')
        if eval_n_limit is not None and subset.shape[0] > eval_n_limit:
            subset = shuffle_and_sample_dataset(subset, eval_n_limit)
        return subset

    # Rest of the original logic for config.toml and environment variables
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = toml.load(file)
            if 'selected_ids' in data and len(data['selected_ids']) > 0:
                selected_ids = data['selected_ids']
                logger.info(f'Filtering {len(selected_ids)} tasks from "selected_ids"...')
                subset = dataset[dataset[filter_column].isin(selected_ids)]
                logger.info(f'Retained {subset.shape[0]} tasks after filtering')
                if eval_n_limit is not None and subset.shape[0] > eval_n_limit:
                    subset = shuffle_and_sample_dataset(subset, eval_n_limit)
                return subset
            if 'selected_repos' in data:
                selected_repos = data['selected_repos']
                if isinstance(selected_repos, str):
                    selected_repos = [selected_repos]
                assert isinstance(selected_repos, list)
                logger.info(f'Filtering {selected_repos} tasks from "selected_repos"...')
                subset = dataset[dataset['repo'].isin(selected_repos)]
                logger.info(f'Retained {subset.shape[0]} tasks after filtering')
                if eval_n_limit is not None and subset.shape[0] > eval_n_limit:
                    subset = shuffle_and_sample_dataset(subset, eval_n_limit)
                return subset

    skip_ids = os.environ.get('SKIP_IDS', '').split(',')
    if len(skip_ids) > 0:
        logger.info(f'Filtering {len(skip_ids)} tasks from "SKIP_IDS"...')
        subset = dataset[~dataset[filter_column].isin(skip_ids)]
        if eval_n_limit is not None and subset.shape[0] > eval_n_limit:
            subset = shuffle_and_sample_dataset(subset, eval_n_limit)
        return subset

    # No filtering applied — sample from the full dataset if needed
    if eval_n_limit is not None and dataset.shape[0] > eval_n_limit:
        return shuffle_and_sample_dataset(dataset, eval_n_limit)
    return dataset

def read_from_json(file_path: str) -> dict:
    """
    Reads JSON data from a file and returns it as a dictionary.
    If the file does not exist or is empty, returns an empty dictionary.

    :param file_path: The path of the JSON file to be read.
    :return: Dictionary containing the JSON data or an empty dictionary if the file does not exist or is empty.
    """
    if os.path.exists(file_path):
        if os.path.getsize(file_path) > 0:  # check if the file is not empty
            with open(file_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
            return data
        else:
            return {}  # return empty dict if the file is empty
    else:
        return {}  # return empty dict if the file does not exist

def parse_memory_candidate(value):
    """Parse comma-separated string into list of integers"""
    try:
        return [int(x.strip()) for x in value.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid format: '{value}'. Expected comma-separated integers like '0,1'")


####################################
#    Cross-Episode Memory Functions
####################################

def group_instances_by_repo(instances_df: pd.DataFrame) -> dict:
    """Group instance rows by repo column, maintaining the order within each repo."""
    repo_groups = {}
    for _, row in instances_df.iterrows():
        repo = row['repo']
        if repo not in repo_groups:
            repo_groups[repo] = []
        repo_groups[repo].append(row)
    return repo_groups


def _parse_memory_model_response(response: str, fallback_memory: str = "") -> str:
    """Parse memory model response, extracting content from <snippet> tags."""
    if response and "<snippet>" in response and "</snippet>" in response:
        return response.split("<snippet>")[1].split("</snippet>")[0].strip()
    if response and response.strip():
        return response.replace("<snippet>", "").replace("</snippet>", "").strip()
    return fallback_memory


def cross_episode_memory_from_trajectory(
    current_memory: str,
    trajectory: list,
    memory_llm,
    system_prompt_cross_episode: str,
    system_prompt_initial: str,
    is_first_cross_episode: bool = False,
) -> tuple:
    """
    Call the memory model to update memory based on the completed trajectory.

    Args:
        current_memory: The current memory snippet (M_{k-1}).
        trajectory: The trajectory (list of dicts) from the completed task.
        memory_llm: LiteLLMAPI instance for the memory model.
        system_prompt_cross_episode: System prompt template with {LATEST_MEMORY} placeholder.
        system_prompt_initial: System prompt for first-time memory generation (no prior memory).
        is_first_cross_episode: If True, use initial prompt (generating from scratch after first task).

    Returns:
        Tuple of (updated_memory_snippet, cost).
    """
    if is_first_cross_episode or not current_memory:
        system_prompt = system_prompt_initial
    else:
        system_prompt = system_prompt_cross_episode.replace("{LATEST_MEMORY}", current_memory)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": str(trajectory)},
    ]

    response, cost = memory_llm.interact(messages, trajectory if isinstance(trajectory, list) else [])
    updated_memory = _parse_memory_model_response(response, fallback_memory=current_memory)
    return updated_memory, cost


def get_trajectory_for_instance(output, metadata, instance_id):
    """
    Get the trajectory for a completed instance.
    Tries llm_completions dir first (via conv_converter), falls back to output.history.
    """
    # Try llm_completions directory (cleaner conversation format)
    llm_completions_dir = os.path.join(metadata.eval_output_dir, 'llm_completions', instance_id)
    if os.path.exists(llm_completions_dir):
        try:
            from conv_converter import parse_single_instance
            trajectory = parse_single_instance(llm_completions_dir)
            if trajectory:
                logger.info(f"[CrossEpisodeMemory] Loaded trajectory from llm_completions for {instance_id} ({len(trajectory)} messages)")
                return trajectory
        except Exception as e:
            logger.warning(f"[CrossEpisodeMemory] Failed to parse llm_completions for {instance_id}: {e}")

    # Fallback: use raw event history from EvalOutput
    if output.history:
        logger.info(f"[CrossEpisodeMemory] Using raw event history for {instance_id} ({len(output.history)} events)")
        return output.history

    logger.warning(f"[CrossEpisodeMemory] No trajectory available for {instance_id}")
    return []


def load_completed_instances(output_file: str) -> set:
    """Load instance IDs that have already been completed from the output file."""
    completed = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    completed.add(data['instance_id'])
                except (json.JSONDecodeError, KeyError):
                    continue
    return completed


if __name__ == '__main__':
    parser = get_parser()
    parser.add_argument(
        '--dataset',
        type=str,
        default='princeton-nlp/SWE-bench',
        help='data set to evaluate on, either full-test or lite-test',
    )
    parser.add_argument(
        '--split',
        type=str,
        default='test',
        help='split to evaluate on',
    )
    parser.add_argument(
        '--mode',
        type=str,
        default='swe',
        choices=['swe', 'swt', 'swt-ci'],
        help="mode to run the evaluation, either 'swe', 'swt', or 'swt-ci'",
    )
    parser.add_argument(
        '--memory-path',
        type=str,
        default=None,
        required=True,
        help="path to JSON memory file",
    )
    parser.add_argument(
        '--memory-candidate',
        type=parse_memory_candidate,
        default=None,
        required=True,
        help="memory candidate choices as comma-separated integers (e.g., '0,1'): [<raw_trajectory_idx>, <memory_candidate_idx>]",
    )
    # Cross-Episode Memory arguments
    parser.add_argument(
        '--memory-cross-episode',
        action='store_true',
        default=False,
        help="Enable trajectory-level cross-episode memory (sequential per-repo processing)",
    )
    parser.add_argument(
        '--memory-cross-episode-model',
        type=str,
        default=None,
        help="Model name for cross-episode memory LLM (e.g., 'litellm_proxy/anthropic/claude-4-sonnet-20250514')",
    )
    parser.add_argument(
        '--memory-cross-episode-api-key',
        type=str,
        default=None,
        help="API key for cross-episode memory LLM",
    )
    parser.add_argument(
        '--memory-cross-episode-base-url',
        type=str,
        default=None,
        help="Base URL for cross-episode memory LLM",
    )
    parser.add_argument(
        '--memory-cross-episode-temperature',
        type=float,
        default=1.0,
        help="Temperature for cross-episode memory LLM",
    )
    parser.add_argument(
        '--memory-cross-episode-input-cost',
        type=float,
        default=0.000003,
        help="Input cost per token for cross-episode memory LLM",
    )
    parser.add_argument(
        '--memory-cross-episode-output-cost',
        type=float,
        default=0.000015,
        help="Output cost per token for cross-episode memory LLM",
    )
    parser.add_argument(
        '--memory-cross-episode-regen-first',
        action='store_true',
        default=False,
        help="If set, regenerate first memory from scratch (SYSTEM_PROMPT_FOR_SINGLE_EPISODE) after repo's 1st task. "
             "If not set (default), update the pre-generated memory using SYSTEM_PROMPT_FOR_CROSS_EPISODE for all tasks including the first.",
    )
    parser.add_argument(
        '--memory-quality-threshold',
        type=int,
        default=0,
        help="Memory quality threshold. "
             "If 0 (default), no quality check — all updated memories are accepted. "
             "If > 0, updated memories shorter than this character count are rejected (previous memory is kept). "
             "If -1, updated memory is accepted only if it is strictly longer than the previous memory.",
    )
    parser.add_argument(
        '--memory-cross-episode-max-input-tokens',
        type=int,
        default=120000,
        help="Maximum input tokens for the cross-episode memory LLM before truncation. "
             "Different models have different limits (e.g., 8192 for small models, 32768 for medium, 131072 for large).",
    )
    parser.add_argument(
        '--memory-cross-episode-truncation-method',
        type=str,
        default='last',
        choices=['middle', 'first', 'last'],
        help="How to truncate trajectory when it exceeds max input tokens. "
             "'middle': remove from middle (preserves beginning context and end results). "
             "'first': remove oldest items first. "
             "'last': remove newest items first (default).",
    )

    args, _ = parser.parse_known_args()

    # Validate cross-episode memory arguments
    if args.memory_cross_episode:
        if not args.memory_cross_episode_model:
            raise ValueError("--memory-cross-episode-model is required when --memory-cross-episode is enabled")
        if not args.memory_cross_episode_api_key:
            raise ValueError("--memory-cross-episode-api-key is required when --memory-cross-episode is enabled")
        if not args.memory_cross_episode_base_url:
            raise ValueError("--memory-cross-episode-base-url is required when --memory-cross-episode is enabled")

    suffix = f"_with_memory__trajectory{args.memory_candidate[0]+1}_candidate{args.memory_candidate[1]+1}"
    if args.memory_cross_episode:
        # Extract short memory model name (e.g., "litellm_proxy/anthropic/claude-4-sonnet-20250514" -> "claude-4-sonnet-20250514")
        mem_model_short = args.memory_cross_episode_model.split('/')[-1]
        if args.memory_cross_episode_regen_first:
            suffix = f"_cross_episode_regen__{mem_model_short}" + suffix
        else:
            suffix = f"_cross_episode_pregen__{mem_model_short}" + suffix
    args.eval_output_dir = args.eval_output_dir.rstrip('/') + suffix

    # Prepare memory snippets
    all_memory_candidates = read_from_json(args.memory_path)
    memory_dict = {}
    for ins_id in all_memory_candidates:
        selected_memory_snippet = all_memory_candidates[ins_id][f"raw_trajectory_{args.memory_candidate[0]+1}"]["memory_candidates"][args.memory_candidate[1]]["memory_snippet"]
        memory_dict[ins_id] = selected_memory_snippet

    # NOTE: It is preferable to load datasets from huggingface datasets and perform post-processing
    # so we don't need to manage file uploading to OpenHands's repo
    dataset = load_dataset(args.dataset, split=args.split)

    # Set the global dataset type based on dataset name
    set_dataset_type(args.dataset)

    target_instance_ids = list(all_memory_candidates.keys()) if len(all_memory_candidates)>0 else None
    swe_bench_tests = filter_dataset(dataset.to_pandas(), 'instance_id', args.eval_n_limit, target_instance_ids)
    
    logger.info(
        f'Loaded dataset {args.dataset} with split {args.split}: {len(swe_bench_tests)} tasks'
    )
    if DATASET_TYPE == 'SWE-Gym':
        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'split',
                'swegym_verified_instances.json',
            ),
            'r',
        ) as f:
            swegym_verified_instances = json.load(f)
            swe_bench_tests = swe_bench_tests[
                swe_bench_tests['instance_id'].isin(swegym_verified_instances)
            ]
        logger.info(
            f'{len(swe_bench_tests)} tasks left after filtering for SWE-Gym verified instances'
        )

    llm_config = None
    if args.llm_config:
        llm_config = get_llm_config_arg(args.llm_config)
        llm_config.log_completions = True
        # modify_params must be False for evaluation purpose, for reproducibility and accurancy of results
        llm_config.modify_params = False

    if llm_config is None:
        raise ValueError(f'Could not find LLM config: --llm_config {args.llm_config}')

    # Get condenser config from environment variable
    condenser_name = os.environ.get('EVAL_CONDENSER')
    if condenser_name:
        condenser_config = get_condenser_config_arg(condenser_name)
        if condenser_config is None:
            raise ValueError(
                f'Could not find Condenser config: EVAL_CONDENSER={condenser_name}'
            )
    else:
        # If no specific condenser config is provided via env var, default to NoOpCondenser
        condenser_config = NoOpCondenserConfig()
        logger.debug(
            'No Condenser config provided via EVAL_CONDENSER, using NoOpCondenser.'
        )
    
    details = {'mode': args.mode, 'memory': memory_dict}
    _agent_cls = openhands.agenthub.Agent.get_cls(args.agent_cls)

    dataset_descrption = (
        args.dataset.replace('/', '__') + '-' + args.split.replace('/', '__')
    )
    metadata = make_metadata(
        llm_config,
        dataset_descrption,
        args.agent_cls,
        args.max_iterations,
        args.eval_note,
        args.eval_output_dir,
        details=details,
        condenser_config=condenser_config,
    )

    output_file = os.path.join(metadata.eval_output_dir, 'output.jsonl')
    print(f'### OUTPUT FILE: {output_file} ###')

    ################################################################
    #   Cross-Episode Memory Mode: sequential per-repo processing
    ################################################################
    if args.memory_cross_episode:
        from llm import LiteLLMAPI
        from system_prompt import SYSTEM_PROMPT_FOR_CROSS_EPISODE, SYSTEM_PROMPT_FOR_SINGLE_EPISODE

        logger.info("=" * 80)
        logger.info("  CROSS-EPISODE MEMORY MODE ENABLED")
        logger.info(f"  Memory model: {args.memory_cross_episode_model}")
        logger.info("=" * 80)

        # Initialize cross-episode memory LLM
        memory_llm = LiteLLMAPI(
            model=args.memory_cross_episode_model,
            api_key=args.memory_cross_episode_api_key,
            base_url=args.memory_cross_episode_base_url,
            temperature=args.memory_cross_episode_temperature,
            input_cost_per_token=args.memory_cross_episode_input_cost,
            output_cost_per_token=args.memory_cross_episode_output_cost,
            log_completions=False,  # Must be False to avoid litellm.set_verbose polluting SE agent stdout
            truncation_method=args.memory_cross_episode_truncation_method,
            max_input_token=args.memory_cross_episode_max_input_tokens,
        )

        # Group instances by repo (maintains order from selected_ids / dataset)
        repo_groups = group_instances_by_repo(swe_bench_tests)
        logger.info(f"Grouped {len(swe_bench_tests)} instances into {len(repo_groups)} repos: {list(repo_groups.keys())}")

        # Ensure output directory exists
        os.makedirs(metadata.eval_output_dir, exist_ok=True)

        # Cross-episode memory state file (for resume and debugging)
        memory_cross_episode_save_path = os.path.join(metadata.eval_output_dir, 'memory_cross_episode.json')

        # Load existing update state if resuming
        memory_cross_episode_log = read_from_json(memory_cross_episode_save_path)

        # Load already-completed instance IDs
        completed_ids = load_completed_instances(output_file)
        if completed_ids:
            logger.info(f"Resuming: found {len(completed_ids)} already-completed instances")

        total_cross_episode_cost = 0
        total_instances_processed = 0
        total_instances = sum(len(insts) for insts in repo_groups.values())

        for repo, repo_instances in repo_groups.items():
            logger.info(f"{'=' * 80}")
            logger.info(f"  REPO: {repo} ({len(repo_instances)} instances)")
            logger.info(f"{'=' * 80}")

            if repo not in memory_cross_episode_log:
                memory_cross_episode_log[repo] = {
                    "instances": [],
                    "memory_versions": [],
                    "total_cost": 0,
                }

            # Build a memory lookup from update log for this repo.
            # Each entry records the memory generated AFTER processing instance at instance_idx.
            # That memory is intended for the NEXT instance (instance_idx + 1).
            # We build a map: target_idx -> memory_snippet
            memory_for_idx = {}
            if memory_cross_episode_log[repo]["memory_versions"]:
                for version in memory_cross_episode_log[repo]["memory_versions"]:
                    # Memory generated after instance at version["instance_idx"]
                    # should be used by the instance at version["instance_idx"] + 1
                    target_idx = version["instance_idx"] + 1
                    memory_for_idx[target_idx] = version["memory_snippet"]
                logger.info(
                    f"[{repo}] Loaded {len(memory_for_idx)} memory versions from update log. "
                    f"Covers target indices: {sorted(memory_for_idx.keys())}"
                )

            def get_memory_for_instance_idx(target_idx):
                """Get the correct memory for an instance at a given idx.
                Looks for the latest updated memory at or before target_idx."""
                if target_idx == 0:
                    return memory_dict.get(repo_instances[0].instance_id, "")
                # Find the latest memory entry with target <= target_idx
                best_memory = memory_dict.get(repo_instances[0].instance_id, "")
                for check_idx in sorted(memory_for_idx.keys()):
                    if check_idx <= target_idx:
                        best_memory = memory_for_idx[check_idx]
                    else:
                        break
                return best_memory

            current_memory = None

            for idx, instance in enumerate(repo_instances):
                instance_id = instance.instance_id
                total_instances_processed += 1

                # Determine which memory to use for this instance
                if idx == 0 and not memory_for_idx:
                    # First instance of this repo, no prior update: use pre-generated memory
                    current_memory = memory_dict.get(instance_id, "")
                    logger.info(
                        f"[{repo}] [{total_instances_processed}/{total_instances}] "
                        f"Instance {idx + 1}/{len(repo_instances)}: {instance_id} "
                        f"- Using PRE-GENERATED memory (M1)"
                    )
                elif instance_id in completed_ids:
                    # Already completed — restore the correct memory state and skip
                    current_memory = get_memory_for_instance_idx(idx)
                    logger.info(
                        f"[{repo}] [{total_instances_processed}/{total_instances}] "
                        f"Instance {idx + 1}/{len(repo_instances)}: {instance_id} "
                        f"- Skipping (already completed)"
                    )
                    # Advance current_memory to what was updated after this instance (if available)
                    if (idx + 1) in memory_for_idx:
                        current_memory = memory_for_idx[idx + 1]
                    continue
                else:
                    # Not completed — use the correct memory from update chain
                    current_memory = get_memory_for_instance_idx(idx)
                    logger.info(
                        f"[{repo}] [{total_instances_processed}/{total_instances}] "
                        f"Instance {idx + 1}/{len(repo_instances)}: {instance_id} "
                        f"- Using {'UPDATED' if idx > 0 else 'PRE-GENERATED'} memory (M{idx + 1})"
                    )

                # Update the memory dict so get_instruction() picks up the right memory
                metadata.details['memory'][instance_id] = current_memory

                # Process the instance (with retries — higher than standard mode to protect the memory chain)
                MAX_RETRIES = 10  # TODO: increase this if your device/server is unstable
                output = None
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        runtime_failure_count = attempt
                        output = process_instance(
                            instance, metadata,
                            reset_logger=False,
                            runtime_failure_count=runtime_failure_count,
                        )
                        break  # Success
                    except Exception as e:
                        if attempt < MAX_RETRIES:
                            logger.warning(
                                f"  -> Attempt {attempt + 1}/{MAX_RETRIES + 1} FAILED for {instance_id}: {e}. Retrying..."
                            )
                        else:
                            logger.error(
                                f"  -> All {MAX_RETRIES + 1} attempts FAILED for {instance_id}: {e}"
                            )
                            import traceback
                            traceback.print_exc()

                if output is None:
                    # All retries exhausted — skip remaining instances in this repo to avoid broken memory chain
                    remaining = len(repo_instances) - idx - 1
                    logger.error(
                        f"  -> FATAL: Skipping {instance_id} after {MAX_RETRIES + 1} failed attempts. "
                        f"Abandoning remaining {remaining} instances in repo '{repo}' to preserve memory chain integrity."
                    )
                    break  # Break inner loop, move to next repo

                # Write output to file
                with open(output_file, 'a') as f:
                    f.write(output.model_dump_json() + '\n')
                    f.flush()
                completed_ids.add(instance_id)

                logger.info(f"  -> Completed: {instance_id} (patch: {bool(output.test_result.get('git_patch', ''))})")

                # === Cross-Episode Memory: update memory for the NEXT instance ===
                try:
                    trajectory = get_trajectory_for_instance(output, metadata, instance_id)

                    if trajectory:
                        logger.info(f"  -> Updating memory based on trajectory ({len(trajectory)} items)...")
                        updated_memory, cross_episode_cost = cross_episode_memory_from_trajectory(
                            current_memory=current_memory,
                            trajectory=trajectory,
                            memory_llm=memory_llm,
                            system_prompt_cross_episode=SYSTEM_PROMPT_FOR_CROSS_EPISODE,
                            system_prompt_initial=SYSTEM_PROMPT_FOR_SINGLE_EPISODE,
                            is_first_cross_episode=(idx == 0 and args.memory_cross_episode_regen_first),
                        )
                        total_cross_episode_cost += cross_episode_cost

                        # Update current memory for next instance (with quality check)
                        logger.info(f"\n[Current Memory] length = {len(current_memory)}\n{current_memory}\n\n[New Memory] length = {len(updated_memory)}\n{updated_memory}")
                        # Quality threshold semantics:
                        #   -1: accept only if new memory is strictly longer than previous memory
                        #    0: accept all (no quality check)
                        #   >0: accept only if new memory length >= threshold
                        if args.memory_quality_threshold == -1:
                            memory_accepted = len(updated_memory) > len(current_memory)
                            check_desc = f"len={len(updated_memory)} {'>' if memory_accepted else '<='} prev_len={len(current_memory)}"
                        else:
                            memory_accepted = len(updated_memory) >= args.memory_quality_threshold
                            check_desc = f"len={len(updated_memory)} {'>=' if memory_accepted else '<'} threshold={args.memory_quality_threshold}"

                        if memory_accepted:
                            current_memory = updated_memory
                            memory_status = "updated"
                            logger.info(f"√ New memory verified ({check_desc}): Memory updated.")
                        else:
                            memory_status = "unchanged"
                            logger.info(f"x New memory is low-quality ({check_desc}): Memory remains unchanged.")

                        # Log the update. memory_snippet is the memory actually in use after this instance.
                        # M{idx+2} is the version label since instance at idx used M{idx+1}, and the next instance will use M{idx+2}.
                        memory_cross_episode_log[repo]["instances"].append(instance_id)
                        memory_cross_episode_log[repo]["memory_versions"].append({
                            "instance_id": instance_id,
                            "instance_idx": idx,
                            "memory_version": f"M{idx + 2}",
                            "memory_status": memory_status,  # "updated" or "unchanged"
                            "memory_snippet": current_memory,
                            "cross_episode_cost": cross_episode_cost,
                            "trajectory_length": len(trajectory),
                        })
                        memory_cross_episode_log[repo]["total_cost"] += cross_episode_cost

                        logger.info(
                            f"  -> Memory updated: M{idx + 1} -> M{idx + 2} "
                            f"(cost: ${cross_episode_cost:.4f}, total: ${total_cross_episode_cost:.4f})"
                        )
                    else:
                        logger.warning(f"  -> No trajectory available, keeping current memory unchanged")
                        memory_cross_episode_log[repo]["instances"].append(instance_id)
                        memory_cross_episode_log[repo]["memory_versions"].append({
                            "instance_id": instance_id,
                            "instance_idx": idx,
                            "memory_version": f"M{idx + 1}_unchanged",
                            "memory_snippet": current_memory,
                            "cross_episode_cost": 0,
                            "trajectory_length": 0,
                        })
                except Exception as e:
                    logger.error(f"  -> Cross-episode memory FAILED for {instance_id}: {e}. Keeping current memory.")
                    memory_cross_episode_log[repo]["instances"].append(instance_id)
                    memory_cross_episode_log[repo]["memory_versions"].append({
                        "instance_id": instance_id,
                        "instance_idx": idx,
                        "memory_version": f"M{idx + 1}_update_failed",
                        "memory_snippet": current_memory,
                        "cross_episode_cost": 0,
                        "trajectory_length": 0,
                    })

                # Save cross-episode memory log after each instance (for crash recovery)
                with open(memory_cross_episode_save_path, 'w', encoding='utf-8') as f:
                    json.dump(memory_cross_episode_log, f, indent=2, ensure_ascii=False)

            logger.info(f"[{repo}] Completed all {len(repo_instances)} instances. Repo update cost: ${memory_cross_episode_log[repo]['total_cost']:.4f}")

        # Final summary
        logger.info(f"{'=' * 80}")
        logger.info(f"  CROSS-EPISODE MEMORY COMPLETE")
        logger.info(f"  Total instances: {total_instances}")
        logger.info(f"  Total update cost: ${total_cross_episode_cost:.4f}")
        logger.info(f"  Update log: {memory_cross_episode_save_path}")
        logger.info(f"  Output file: {output_file}")
        logger.info(f"{'=' * 80}")

    ################################################################
    #   Standard Mode (no cross-episode memory)
    ################################################################
    else:
        # Run evaluation in iterative mode:
        # If a rollout fails to output AgentFinishAction, we will try again until it succeeds OR total 3 attempts have been made.
        ITERATIVE_EVAL_MODE = (
            os.environ.get('ITERATIVE_EVAL_MODE', 'false').lower() == 'true'
        )
        ITERATIVE_EVAL_MODE_MAX_ATTEMPTS = int(
            os.environ.get('ITERATIVE_EVAL_MODE_MAX_ATTEMPTS', '3')
        )

        if not ITERATIVE_EVAL_MODE:
            # load the dataset
            instances = prepare_dataset(swe_bench_tests, output_file, args.eval_n_limit, shuffle_dataset=False)
            if len(instances) > 0 and not isinstance(
                instances['PASS_TO_PASS'][instances['PASS_TO_PASS'].index[0]], str
            ):
                for col in ['PASS_TO_PASS', 'FAIL_TO_PASS']:
                    instances[col] = instances[col].apply(lambda x: str(x))

            run_evaluation(
                instances,
                metadata,
                output_file,
                args.eval_num_workers,
                process_instance,
                timeout_seconds=8
                * 60
                * 60,  # 8 hour PER instance should be more than enough
                max_retries=5,
            )
        else:
            critic = AgentFinishedCritic()

            def get_cur_output_file_path(attempt: int) -> str:
                return (
                    f'{output_file.removesuffix(".jsonl")}.critic_attempt_{attempt}.jsonl'
                )

            eval_ids = None
            for attempt in range(1, ITERATIVE_EVAL_MODE_MAX_ATTEMPTS + 1):
                cur_output_file = get_cur_output_file_path(attempt)
                logger.info(
                    f'Running evaluation with critic {critic.__class__.__name__} for attempt {attempt} of {ITERATIVE_EVAL_MODE_MAX_ATTEMPTS}.'
                )

                # For deterministic eval, we set temperature to 0.1 for (>1) attempt
                # so hopefully we get slightly different results
                if attempt > 1 and metadata.llm_config.temperature == 0:
                    logger.info(
                        f'Detected temperature is 0 for (>1) attempt {attempt}. Setting temperature to 0.1...'
                    )
                    metadata.llm_config.temperature = 0.1

                # Load instances - at first attempt, we evaluate all instances
                # On subsequent attempts, we only evaluate the instances that failed the previous attempt determined by critic
                instances = prepare_dataset(
                    swe_bench_tests, cur_output_file, args.eval_n_limit, eval_ids=eval_ids, shuffle_dataset=False
                )
                if len(instances) > 0 and not isinstance(
                    instances['PASS_TO_PASS'][instances['PASS_TO_PASS'].index[0]], str
                ):
                    for col in ['PASS_TO_PASS', 'FAIL_TO_PASS']:
                        instances[col] = instances[col].apply(lambda x: str(x))

                # Run evaluation - but save them to cur_output_file
                logger.info(
                    f'Evaluating {len(instances)} instances for attempt {attempt}...'
                )
                run_evaluation(
                    instances,
                    metadata,
                    cur_output_file,
                    args.eval_num_workers,
                    process_instance,
                    timeout_seconds=8
                    * 60
                    * 60,  # 8 hour PER instance should be more than enough
                    max_retries=5,
                )

                # When eval is done, we update eval_ids to the instances that failed the current attempt
                instances_failed = []
                logger.info(
                    f'Use critic {critic.__class__.__name__} to check {len(instances)} instances for attempt {attempt}...'
                )
                with open(cur_output_file, 'r') as f:
                    for line in f:
                        instance = json.loads(line)
                        try:
                            history = [
                                event_from_dict(event) for event in instance['history']
                            ]
                            critic_result = critic.evaluate(
                                history, instance['test_result'].get('git_patch', '')
                            )
                            if not critic_result.success:
                                instances_failed.append(instance['instance_id'])
                        except Exception as e:
                            logger.error(
                                f'Error loading history for instance {instance["instance_id"]}: {e}'
                            )
                            instances_failed.append(instance['instance_id'])
                logger.info(
                    f'{len(instances_failed)} instances failed the current attempt {attempt}: {instances_failed}'
                )
                eval_ids = instances_failed

                # If no instances failed, we break
                if len(instances_failed) == 0:
                    break

            # Then we should aggregate the results from all attempts into the original output file
            # and remove the intermediate files
            logger.info(
                'Aggregating results from all attempts into the original output file...'
            )
            fout = open(output_file, 'w')
            added_instance_ids = set()
            for attempt in reversed(range(1, ITERATIVE_EVAL_MODE_MAX_ATTEMPTS + 1)):
                cur_output_file = get_cur_output_file_path(attempt)
                if not os.path.exists(cur_output_file):
                    logger.warning(
                        f'Intermediate output file {cur_output_file} does not exist. Skipping...'
                    )
                    continue

                with open(cur_output_file, 'r') as f:
                    for line in f:
                        instance = json.loads(line)
                        # Also make sure git_patch is not empty - otherwise we fall back to previous attempt (empty patch is worse than anything else)
                        if (
                            instance['instance_id'] not in added_instance_ids
                            and instance['test_result'].get('git_patch', '').strip()
                        ):
                            fout.write(line)
                            added_instance_ids.add(instance['instance_id'])
                logger.info(
                    f'Aggregated instances from {cur_output_file}. Total instances added so far: {len(added_instance_ids)}'
                )
            fout.close()
            logger.info(
                f'Done! Total {len(added_instance_ids)} instances added to {output_file}'
            )