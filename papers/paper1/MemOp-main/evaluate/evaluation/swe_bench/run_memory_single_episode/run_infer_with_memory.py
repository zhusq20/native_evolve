import os
import copy
import json
import toml
import asyncio
import pandas as pd
from typing import Any, Literal
from datasets import load_dataset
from jinja2 import Environment, FileSystemLoader

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
    filter_dataset,
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
MAX_RETRY = 10  # increase if your device is unstable

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

def filter_dataset(dataset: pd.DataFrame, filter_column: str, target_ids: list = None) -> pd.DataFrame:
    # If target_ids is provided, use it directly for filtering
    if target_ids is not None:
        logger.info(f'Filtering {len(target_ids)} tasks from provided target_ids...')
        subset = dataset[dataset[filter_column].isin(target_ids)]
        logger.info(f'Retained {subset.shape[0]} tasks after filtering')
        return subset
    
    # Rest of the original logic for config.toml and environment variables
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = toml.load(file)
            if 'selected_ids' in data:
                selected_ids = data['selected_ids']
                logger.info(f'Filtering {len(selected_ids)} tasks from "selected_ids"...')
                subset = dataset[dataset[filter_column].isin(selected_ids)]
                logger.info(f'Retained {subset.shape[0]} tasks after filtering')
                return subset
            if 'selected_repos' in data:
                selected_repos = data['selected_repos']
                if isinstance(selected_repos, str):
                    selected_repos = [selected_repos]
                assert isinstance(selected_repos, list)
                logger.info(f'Filtering {selected_repos} tasks from "selected_repos"...')
                subset = dataset[dataset['repo'].isin(selected_repos)]
                logger.info(f'Retained {subset.shape[0]} tasks after filtering')
                return subset

    skip_ids = os.environ.get('SKIP_IDS', '').split(',')
    if len(skip_ids) > 0:
        logger.info(f'Filtering {len(skip_ids)} tasks from "SKIP_IDS"...')
        return dataset[~dataset[filter_column].isin(skip_ids)]
    
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

    args, _ = parser.parse_known_args()
    args.eval_output_dir = args.eval_output_dir.rstrip('/') + f"_with_memory__trajectory{args.memory_candidate[0]+1}_candidate{args.memory_candidate[1]+1}"

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

    target_instance_ids = list(all_memory_candidates.keys())
    swe_bench_tests = filter_dataset(dataset.to_pandas(), 'instance_id', target_instance_ids)
    
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
        instances = prepare_dataset(swe_bench_tests, output_file, args.eval_n_limit)
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
            max_retries=MAX_RETRY,
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
                swe_bench_tests, cur_output_file, args.eval_n_limit, eval_ids=eval_ids
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
                max_retries=MAX_RETRY,
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