GPU_ID="0"

# ====== Task ======
MEM_TASK="post_eval"

# Number of raw trajectories per instance, and memory candidates per raw trajectory.
# These must match what was used during memory generation (see run_memory.sh).
RAW_TRAJECTORY_NUM=1
MEMORY_CANDIDATE_NUM=1



# ====== Memory / Agent (match run_memory.sh) ======
SE_AGENT="Qwen3-Coder-30B-A3B-Instruct"
MODEL_NAME="memory__ours__rl_from_sft__qwen3_4b_instruct"

# Agent sub-folder name produced by the evaluation runs (under .../CodeActAgent/).
AGENT_CONFIG="${SE_AGENT}_maxiter_100_N_v0.45.0-no-hint-run_1"



# ====== Path (relative) ======
# Save dir of the generated memories (same convention as run_memory.sh's SAVE_DIR).
SAVE_DIR="./outputs/saves__memory_${MODEL_NAME}__code_${SE_AGENT}"
# Parent dir holding outputs_with_memory__trajectory*_candidate*/ from the evaluation runs.
TRAJECTORY_WITH_MEMORY_DIR="../evaluate/evaluation/evaluation_outputs"
# Reorganized memories produced by run_memory.sh.
GENERATED_MEMORY="${SAVE_DIR}/all_reorganized_memories.json"
# Where to save the merged delta-performance results.
OUTPUT_SAVE_PATH="${SAVE_DIR}/all_trajectories_evals.json"



args=(
  "--memory-task" "$MEM_TASK"
  "--raw-trajectory-num" "$RAW_TRAJECTORY_NUM"
  "--memory-candidate-num" "$MEMORY_CANDIDATE_NUM"
  "--trajectory-with-memory-dir" "$TRAJECTORY_WITH_MEMORY_DIR"
  "--agent-config" "$AGENT_CONFIG"
  "--generated-memory" "$GENERATED_MEMORY"
  "--output-save-path" "$OUTPUT_SAVE_PATH"
  "--save-dir" "$SAVE_DIR"
)

CUDA_VISIBLE_DEVICES=$GPU_ID PYTHONDONTWRITEBYTECODE=1 python -m main "${args[@]}"
