GPU_ID="0"

# ====== Task ======
MEM_TASK="memory_generation"
CANDIDATE_NUM=4
TRAJECTORY_IDX=4



# ====== Memory Model ======
SE_AGENT="Qwen3-Coder-30B-A3B-Instruct"
MODEL_NAME="memory__ours__rl_from_sft__qwen3_4b_instruct"
MEMORY_MODEL="openai/xuehang/${MODEL_NAME}"

API_KEY="(input your API key here)"
BASE_URL="(input your base URL here)"
TEMPERATURE=1.0
INPUT_COST_PER_TOKEN=0.0
OUTPUT_COST_PER_TOKEN=0.0

# TRUNCATION_METHOD="middle"
TRUNCATION_METHOD="last"



# ====== Path ======
DATA_PATH="/path/to/your/raw_trajectories.json"
CONV_DIR="/path/to/your/conversation_histories.json"
EVAL_PATH="/path/to/your/evaluation_results.json"
SAVE_DIR="./outputs/saves__memory_${MODEL_NAME}__code_${SE_AGENT}"
CACHE_DIR="/path/to/save/caches"  # you may want to choose somewhere with larger space
TMP_DIR="/path/to/tmps"  # you may want to choose somewhere with larger space



args=(
  "--memory-task" "$MEM_TASK"
  "--memory-candidate-num" "$CANDIDATE_NUM"
  "--raw-trajectory-idx" "$TRAJECTORY_IDX"
  "--truncation-method" "$TRUNCATION_METHOD"
  "--memory-agent" "$MEMORY_MODEL"
  "--api-key" "$API_KEY"
  "--base-url" "$BASE_URL"
  "--temperature" "$TEMPERATURE"
  "--input-cost-per-token" "$INPUT_COST_PER_TOKEN"
  "--output-cost-per-token" "$OUTPUT_COST_PER_TOKEN"
  "--data-path" "$DATA_PATH"
  "--conv-dir" "$CONV_DIR"
  "--eval-path" "$EVAL_PATH"
  "--save-dir" "$SAVE_DIR"
  "--cache-dir" "$CACHE_DIR"
  "--tmp-dir" "$TMP_DIR"
)

export LITELLM_PORT=8236
CUDA_VISIBLE_DEVICES=$GPU_ID PYTHONDONTWRITEBYTECODE=1 python -m main "${args[@]}"
