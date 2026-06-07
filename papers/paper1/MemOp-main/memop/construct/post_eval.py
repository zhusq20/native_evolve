import os
import json
from copy import deepcopy
from typing import List, Dict
from json_util import read_from_json, read_from_jsonl, save_to_json


def post_eval_merger(
    total_num_raw_trajectory: int,
    total_num_memory_candidate: int,
    trajectory_with_memory_dir: str,
    agent_config: str,
    source_memory_path: str,
    output_save_path: str,
    ):
    """
    Args:
        - total_num_raw_trajectory: Total number of raw trajectories
        - total_num_memory_candidate: Total number of memory snippet generated for each raw trajectories
        - trajectory_with_memory_dir: Directory to evaluation outputs (the parent dir of path/to/output.jsonl)
        - agent_config: Agent subfolder name
        - source_memory_path: Path to the JSON file of the reorganized memories (path/to/all_reorganized_memories.json)
        - output_save_path: JSON path to save the merged output

    Return: 
        merged_trj_w_evals = {
            <instance_id>: {
                "instance_id": <instance_id>,
                "initial_trajectory_1": {
                    "initial_trajectory_id": 1,
                    "initial_trajectory": <initial_trajectory_1>,
                    "baseline_eval": <loc_eval_without_memory>,
                    "memory_candidates": {
                        "candidate_1": {
                            "candidate_id": 1,
                            "memory_snippet": <string of memory snippet>,
                            "delta_performance": <delta performance>,
                            "loc_eval": <loc eval of current trajectory_with_memory>,
                            "trajectory_with_memory": <trajectory_with_memory>,
                        }
                    }
                },
                "initial_trajectory_2": ...
                ...
            },
            ...
        }
    """
    # Read all generated memory snippets
    all_source_memories = read_from_json(source_memory_path)
    merged_trj_w_evals = {}
    inst_progress = 0

    for instance_id in all_source_memories:
        inst_progress += 1

        if instance_id not in merged_trj_w_evals:
            merged_trj_w_evals[instance_id] = {"instance_id": instance_id}

        for trj_idx in range(1, total_num_raw_trajectory+1):  # start from 1
            # Initial raw trajectory of current instance
            initial_raw_trajectory = all_source_memories[instance_id][f"raw_trajectory_{trj_idx}"]["raw_trajectory"]
            baseline_eval = all_source_memories[instance_id][f"raw_trajectory_{trj_idx}"]["baseline_eval"]  # initial_raw_trajectory's loc eval

            # Init new trajectory entry
            new_trajectory_entry = {
                "initial_trajectory_id": trj_idx,
                "initial_trajectory": initial_raw_trajectory,
                "baseline_eval": baseline_eval,
                "memory_candidates": {},
            }

            for mem_idx in range(1, total_num_memory_candidate+1):  # start from 1
                print(f"[Progress] Instance: {inst_progress}/{len(all_source_memories)}    |    Trajectory {trj_idx}/{total_num_raw_trajectory} - Memory Candidate {mem_idx}/{total_num_memory_candidate}")

                # Init new memory entry
                new_memory_candidate_entry = {
                    "candidate_id": mem_idx,
                    "memory_snippet": all_source_memories[instance_id][f"raw_trajectory_{trj_idx}"]["memory_candidates"][mem_idx-1]["memory_snippet"],
                    "delta_performance": None,
                    "loc_eval": None,
                    "trajectory_with_memory": None,
                }
                
                # Read all trajectory_with_memory for current trj_idx & mem_idx
                eval_root_dir = f"{trajectory_with_memory_dir}/outputs_with_memory__trajectory{trj_idx}_candidate{mem_idx}/princeton-nlp__SWE-bench_Verified-test/CodeActAgent/{agent_config}"
                all_trajectories_with_memories = read_from_jsonl(f"{eval_root_dir}/output.jsonl")
            
                # Extract current trajectory_with_memory
                for new_trajectory_output in all_trajectories_with_memories:
                    if new_trajectory_output["instance_id"] == instance_id:
                        new_memory_candidate_entry["trajectory_with_memory"] = new_trajectory_output["history"]
                        break

                # Read loc eval
                loc_eval_path = f"{eval_root_dir}/loc_eval/loc_eval_results/loc_acc/all_loc_evals.json"
                curr_loc_eval = read_from_json(loc_eval_path)[instance_id]["final_eval"]
                new_memory_candidate_entry["loc_eval"] = curr_loc_eval

                # Compute delta loc_eval
                max_turn = curr_loc_eval["max turn"]
                delta_performance = {
                    "loc_acc (%)": {
                        "la_file (%)": {
                            "la_file_micro": curr_loc_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_micro"] - baseline_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_micro"],
                            "la_file_macro": curr_loc_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_macro"] - baseline_eval["localization"]["loc_acc (%)"]["la_file (%)"]["la_file_macro"],
                        },
                        "la_func (%)": {
                            "la_func_micro": curr_loc_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_micro"] - baseline_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_micro"],
                            "la_func_macro": curr_loc_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_macro"] - baseline_eval["localization"]["loc_acc (%)"]["la_func (%)"]["la_func_macro"],
                        }
                    },
                    "resolve_rate (%)": (100.00 if curr_loc_eval["task_success"]["resolved"] else 0.00) - (100.00 if baseline_eval["task_success"]["resolved"] else 0.00),
                    "efficiency (%)": {
                        "localization": {
                            "file": {
                                "micro": (baseline_eval["localization"]["turn_idx"]["file"]["micro"] - curr_loc_eval["localization"]["turn_idx"]["file"]["micro"]) / max_turn * 100,
                                "macro": (baseline_eval["localization"]["turn_idx"]["file"]["macro"] - curr_loc_eval["localization"]["turn_idx"]["file"]["macro"]) / max_turn * 100,
                            },
                            "function": {
                                "micro": (baseline_eval["localization"]["turn_idx"]["function"]["micro"] - curr_loc_eval["localization"]["turn_idx"]["function"]["micro"]) / max_turn * 100,
                                "macro": (baseline_eval["localization"]["turn_idx"]["function"]["macro"] - curr_loc_eval["localization"]["turn_idx"]["function"]["macro"]) / max_turn * 100,
                            }
                        },
                        "resolution": (baseline_eval["task_success"]["resolve_index"] - curr_loc_eval["task_success"]["resolve_index"]) / max_turn * 100,
                    }
                }
                new_memory_candidate_entry["delta_performance"] = delta_performance

                # Save memory entry
                new_trajectory_entry["memory_candidates"][f"candidate_{mem_idx}"] = new_memory_candidate_entry

            # Save trajectory entry
            merged_trj_w_evals[instance_id][f"initial_trajectory_{trj_idx}"] = new_trajectory_entry

    # Save merged_trj_w_evals
    save_to_json(merged_trj_w_evals, output_save_path)
    print(f"Successfully saved delta-performance for trajectories with memories: {output_save_path}")
