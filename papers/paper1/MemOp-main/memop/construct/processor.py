import os
import json
import copy
from typing import Dict, List
from utils.json_util import read_from_json, save_to_json
from utils.logger import logger


class MemoryDeltaProcessor:
    def __init__(self, args):
        """Init memory processor"""
        self.args = args
        self.all_reorganized_memories = read_from_json(args.generated_memory)
        self.memory_evals = self._memory_eval_paths_parser(args.memory_evals)
        self.save_json_path = os.path.join(args.save_dir, "all_with_delta.json")

    def _memory_eval_paths_parser(self, path_str):
        """Parse JSON string to eval dict"""
        mem_evals = json.loads(path_str) if path_str else {}
        return mem_evals

    def compute_memory_performance(self):
        """Compare the performance of coding agent w/ different memory methods (0-9)"""

        for instance_id in self.all_reorganized_memories:
            # List of candidates
            memory_candidates = self.all_reorganized_memories[instance_id]["memory_candidates"]
            baseline_eval = self.all_reorganized_memories[instance_id]["baseline_eval"]
            new_memory_candidates = []

            for memory_cand in memory_candidates:
                candidate_id = memory_cand["candidate_id"]
                eval_result = read_from_json(self.memory_evals[f"method_{candidate_id}"])

                # Save eval
                memory_cand["eval_result"] = eval_result[instance_id]["final_eval"]

                # Compute delta
                delta_la_file_micro = memory_cand["eval_result"]["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_micro"] \
                    - baseline_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_micro"]
                delta_la_file_macro = memory_cand["eval_result"]["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_macro"] \
                    - baseline_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_macro"]
                delta_la_func_micro = memory_cand["eval_result"]["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_micro"] \
                    - baseline_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_micro"]
                delta_la_func_macro = memory_cand["eval_result"]["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_macro"] \
                    - baseline_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_macro"]
                
                performance_delta = {
                    "delta_loc_acc (%)": {
                        "la_file (%)": {
                            "la_file_micro": delta_la_file_micro,
                            "la_file_macro": delta_la_file_macro,
                        },
                        "la_func (%)": {
                            "la_func_micro": delta_la_func_micro,
                            "la_func_macro": delta_la_func_macro,
                        },
                    },
                    "delta_resolve_rate (%)": None
                }

                if memory_cand["eval_result"]["task_success"] and baseline_eval["eval_result"]["task_success"]:
                    delta_resolve_rate = memory_cand["eval_result"]["task_success"]["resolve_rate"] - baseline_eval["eval_result"]["task_success"]["resolve_rate"]
                    performance_delta["delta_resolve_rate (%)"] = delta_resolve_rate

                # Save
                memory_cand["delta_performance"] = performance_delta
                new_memory_candidates.append(memory_cand)

            # Save to all
            self.all_reorganized_memories[instance_id]["memory_candidates"] = copy.deepcopy(new_memory_candidates)

        # Save to JSON
        save_to_json(self.all_reorganized_memories, self.save_json_path)
        logger.info(f"Evaluation of memory candidates with performance delta is saved to: {self.save_json_path}")



