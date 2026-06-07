"""
Reorganize coding agent's trajectory to memory structure
"""

import os
from tqdm import tqdm
from typing import List, Dict, Tuple

from llm import LiteLLMAPI
from json_util import read_from_json, save_to_json, read_from_jsonl
from system_prompt import SYSTEM_PROMPT_FOR_SINGLE_EPISODE, SYSTEM_PROMPT_FOR_CROSS_EPISODE
from conv_converter import parse_single_instance
from openhands.core.logger import openhands_logger as logger


class MemoryGenerator:
    def __init__(self, args):
        """
        Generate memory from coding trajectories.
        """
        self.args = args
        self.memory_cross_episode = args.memory_cross_episode
        self.raw_trajectory_idx = args.raw_trajectory_idx
        self.trajectories = read_from_jsonl(args.data_path)
        self.baseline_evals = read_from_json(args.eval_path)
        self.instance_num = len(self.trajectories)
        self.instance_ids = [self.trajectories[i]["instance_id"] for i in range(self.instance_num)]

        # Debug check
        logger.debug(f"self.instance_ids: {self.instance_ids}")
        logger.debug(f"self.instance_num: {self.instance_num}")

        # LLM API
        self.log_completions = True
        self.llm_api = LiteLLMAPI(
            model=args.memory_agent,
            api_key=args.api_key,
            base_url=args.base_url,
            temperature=args.temperature,
            input_cost_per_token=args.input_cost_per_token,
            output_cost_per_token=args.output_cost_per_token,
            log_completions=self.log_completions
        )

        # Memory generation
        self.memory_candidate_num = args.memory_candidate_num
        self.cost_info = {"total_cost": 0, "details": {}}
        self.reorganized_memories = {}
        self.save_dir = args.save_dir
        self._init_dir(self.save_dir)
        self._init_reorganized_memories_and_cost()

    def _init_dir(self, dir: str):
        """Check if directory exists, create it if not"""
        if not os.path.exists(dir):
            os.makedirs(dir)
            logger.info(f"Directory '{dir}' created.")
        else:
            logger.info(f"Directory '{dir}' already exists. Skipping creation...")

    def _init_reorganized_memories_and_cost(self):
        # Reorganized memory
        save_path = os.path.join(self.save_dir, "all_reorganized_memories.json")
        if os.path.exists(save_path):
            self.reorganized_memories = read_from_json(save_path)
        else:
            self.reorganized_memories = {}

        # Cost info
        cost_save_path = os.path.join(self.save_dir, "cost_info.json")
        if os.path.exists(cost_save_path):
            self.cost_info = read_from_json(cost_save_path)
        else:
            self.cost_info = {"total_cost": 0, "details": {}}
    
    def _init_task(self):
        """Concise memory generation for coding agent continuation"""
        if self.memory_cross_episode:
            return SYSTEM_PROMPT_FOR_CROSS_EPISODE
        else:
            return SYSTEM_PROMPT_FOR_SINGLE_EPISODE
    
    def _parse_model_response(self, response: str):
        # First try to extract content from <snippet> tags
        if "<snippet>" in response and "</snippet>" in response:
            memory_snippet = response.split("<snippet>")[1].split("</snippet>")[0].strip()
            return memory_snippet
        
        # If no snippet tags, but response exists, use the whole response as memory
        if response and response.strip():
            response = response.replace("<snippet>", "").replace("</snippet>", "").strip()            
            return response.strip()
        
        # Only return None if response is truly empty
        return None

    def memory_reorganization(self):
        """Memory reorganization"""
        for progress_idx in tqdm(range(self.instance_num)):
            # Read raw trajectory
            instance_id = self.trajectories[progress_idx]["instance_id"]
            baseline_eval = self.baseline_evals[instance_id]["final_eval"]

            # Convert llm completions to raw trajectory
            instance_trajectory_dir = os.path.join(self.args.conv_dir, instance_id)
            raw_trajectory = parse_single_instance(instance_trajectory_dir)

            if instance_id not in self.reorganized_memories:
                self.reorganized_memories[instance_id] = {}

            # Continue if already exists
            if f"raw_trajectory_{self.raw_trajectory_idx}" in self.reorganized_memories[instance_id]:
                logger.info(
                    f"Memory snippets for the raw trajectory {self.raw_trajectory_idx} has already been generated for instance `{instance_id}`"
                    f"\nSkipping current instance and continuing to the next instance..."
                )
                continue
            
            else:
                # Init new dict for current instance
                self.reorganized_memories[instance_id][f"raw_trajectory_{self.raw_trajectory_idx}"] = {
                    "raw_trajectory": raw_trajectory,
                    "trajectory_with_memory": None,
                    "baseline_eval": baseline_eval,
                    "memory_candidates": [],
                }

                logger.info(
                    f"Generating memory snippets for instance `{instance_id}`: raw trajectory {self.raw_trajectory_idx}"                   
                )

            for mem_candidate_idx in range(1, self.memory_candidate_num+1):
                logger.info(
                    f"{'=' * 100}"
                    f"\n        [Progress]         Instance: {progress_idx+1} / {self.instance_num}    ||    Memory Candidate: {mem_candidate_idx} / {self.memory_candidate_num}"
                    f"\n        [Memory LLM]       {self.args.memory_agent}"
                    f"\n        [Total Cost]     $ {self.cost_info['total_cost']}"
                    f"\n{'=' * 100}"
                )

                # Reorganize memory
                self.system_prompt = self._init_task()
                input_prompt = [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": str(raw_trajectory)
                    },
                ]

                # Get memory agent's reponse and cost
                memory_snippet = None
                while memory_snippet is None:
                    model_response, model_cost = self.llm_api.interact(messages=input_prompt, user_input=raw_trajectory)
                    memory_snippet = self._parse_model_response(model_response)

                # Parse response
                self.cost_info["total_cost"] += model_cost
                if f"candidate_{mem_candidate_idx}" in self.cost_info["details"]:
                    self.cost_info["details"][f"candidate_{mem_candidate_idx}"] += model_cost
                else:
                    self.cost_info["details"][f"candidate_{mem_candidate_idx}"] = model_cost

                # Save to dict
                new_memory_candidate = {
                    "candidate_id": mem_candidate_idx,
                    "memory_snippet": memory_snippet,
                    "delta_performance": None,
                    "eval_result": None,
                    "metadata": {
                        "base_llm": self.args.memory_agent,
                        "temperature": self.args.temperature,
                    },
                }
                self.reorganized_memories[instance_id][f"raw_trajectory_{self.raw_trajectory_idx}"]["memory_candidates"].append(new_memory_candidate)
                
            # Save to file
            save_path = os.path.join(self.save_dir, "per_instances", f"instance_id__{instance_id}.json")
            self._init_dir(os.path.join(self.save_dir, "per_instances"))
            save_to_json(self.reorganized_memories[instance_id], save_path)

            # Save all to file
            save_path = os.path.join(self.save_dir, "all_reorganized_memories.json")
            save_to_json(self.reorganized_memories, save_path)

            # Save cost info to file
            cost_save_path = os.path.join(self.save_dir, "cost_info.json")
            save_to_json(self.cost_info, cost_save_path)

        ##############################  Final Save  ##############################
        # Save all to file
        save_path = os.path.join(self.save_dir, "all_reorganized_memories.json")
        save_to_json(self.reorganized_memories, save_path)

        # Save cost info to file
        cost_save_path = os.path.join(self.save_dir, "cost_info.json")
        save_to_json(self.cost_info, cost_save_path)

        logger.info(
            f"{'=' * 120}"
            f"\n        [Completed]        {progress_idx+1} / {self.instance_num}"
            f"\n        [Total Cost]     $ {self.cost_info['total_cost']}"
            f"\n        [Memory LLM]       {self.args.memory_agent}"
            f"\n        [Saved To]         {save_path}"
            f"\n{'=' * 120}"
        )