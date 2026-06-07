import os
import argparse
from itertools import combinations

from utils.logger import logger
from utils.json_util import read_from_json


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Task
    parser.add_argument('--memory-task', type=str, default='memory_generation',
                        help='Define current task.',
                        choices=['memory_generation', 'post_process', 'post_eval'])
    parser.add_argument('--gpu-ids', type=str, default="0,1,2,3", help='Comma-separated list of GPU IDs')

    # Agent
    parser.add_argument('--memory-agent', type=str, default=None, help='Please set your memory agent.')
    parser.add_argument('--api-key', type=str, default='your-api-key', help='Please enter your API Key.')
    parser.add_argument('--base-url', type=str, default=None, help='Please set the base url of your memory agent.')
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--input-cost-per-token', type=float, default=None)
    parser.add_argument('--output-cost-per-token', type=float, default=None)

    # Memory snippet generation
    parser.add_argument('--memory-candidate-num', type=int, default=None, help='Number of memory candidates for each trajectory.')
    parser.add_argument('--raw-trajectory-idx', type=int, default=None, help='Raw trajectory index for each instance.')
    parser.add_argument('--truncation-method', type=str, default='first', choices=['first', 'middle', 'last'],
                        help='Which part of the trajectory to remove when truncating due to token limits. '
                             '"first" removes oldest items, "middle" removes from the center (preserving context and results), '
                             '"last" removes newest items. (default: first)')

    # Memory snippet optimization
    parser.add_argument('--raw-trajectory-num', type=int, default=None, help='Number of raw trajectories for each instance.')
    parser.add_argument('--initial-memory-path', type=str, default=None, help='Path to the initial memory snippets.')

    # Post processing: memory performance delta
    parser.add_argument('--generated-memory', type=str, default=None, help='Path to generated memory candidates.')
    parser.add_argument('--memory-evals', type=str, default=None, help='JSON string of evaluation paths for all memory candidates.')

    # Post evaluation: per-candidate delta on memory-augmented trajectories
    parser.add_argument('--trajectory-with-memory-dir', type=str, default=None,
                        help='Parent directory of the memory-augmented evaluation outputs '
                             '(contains outputs_with_memory__trajectory*_candidate*/). Used by post_eval task.')
    parser.add_argument('--agent-config', type=str, default=None,
                        help='Agent sub-folder name produced by the eval runs '
                             '(e.g. "<se-agent>_maxiter_<N>_N_v0.45.0-no-hint-run_1"). Used by post_eval task.')
    parser.add_argument('--output-save-path', type=str, default=None,
                        help='Path to save the merged delta-performance JSON. Used by post_eval task.')

    # Path
    parser.add_argument('--data-path', type=str, default=None, help='The output.jsonl JSONL file for raw trajectories of OpenHands')
    parser.add_argument('--eval-path', type=str, default=None, help='The all_loc_evals.json JSON file for the evaluation results of the raw trajectories of OpenHands')
    parser.add_argument('--conv-dir', type=str, default=None, help='The directory path to llm completions')
    parser.add_argument('--tmp-dir', type=str, default=None, help='Temporal directory path.')
    parser.add_argument('--save-dir', type=str, default=None, help='Save dir to save outputs.')
    parser.add_argument('--cache-dir', type=str, default='./caches', help='Cache path to save all cache files.')

    # Pass to args
    args = parser.parse_args()

    # Additional args
    if args.save_dir:
        args.save_dir = args.save_dir.rstrip('/')

    # GPUs
    if isinstance(args.gpu_ids, str):
        args.gpu_ids = [int(gpu.strip()) for gpu in args.gpu_ids.split(',')]

    """
    Launch task
    """
    if args.memory_task == 'memory_generation':
        logger.info("[MEMORY] Launch memory generation for coding agent's raw trajectories...")
        from construct.generator import MemoryGenerator
        logger.info(f"[MEMORY] Generate memory snippets using markdown memory structure for raw trajectory index: {args.raw_trajectory_idx}")
        generator = MemoryGenerator(args)
        generator.memory_reorganization()

    elif args.memory_task == 'post_process':
        logger.info("[MEMORY] Post processing for memory candidate performance delta...")
        from construct.processor import MemoryDeltaProcessor
        post_processor = MemoryDeltaProcessor(args)
        post_processor.compute_memory_performance()

    elif args.memory_task == 'post_eval':
        logger.info("[MEMORY] Merging localization-eval results into memory-augmented trajectories...")
        from construct.post_eval import post_eval_merger
        post_eval_merger(
            total_num_raw_trajectory=args.raw_trajectory_num,
            total_num_memory_candidate=args.memory_candidate_num,
            trajectory_with_memory_dir=args.trajectory_with_memory_dir,
            agent_config=args.agent_config,
            source_memory_path=args.generated_memory,
            output_save_path=args.output_save_path,
        )

    else:
        logger.error(f"[Error] Invalid task: {args.memory_task}\nPlease check your task setting and try again.")
