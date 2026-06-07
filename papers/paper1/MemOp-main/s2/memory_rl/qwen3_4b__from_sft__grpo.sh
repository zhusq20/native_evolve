#!/bin/bash

set -x
export WANDB_PROJECT="memop"
export RAY_memory_usage_threshold=0.95

CUDA_IDS=0,1,2,3,4,5,6,7
N_GPU=8

MODEL_PATH="./sft/output/memory_sft_qwen3_4b"

TOTAL_EPOCHES=1
MAX_STEPS=150
GLOBAL_BATCH_SIZE=8
ROLLOUT_BATCH_SIZE=8
ROLLOUT_N=4
VAL_N=1
VAL_BATCH_SIZE=4
MAX_PROMPT_LENGTH=4096
MAX_RESPONSE_LENGTH=1024
MAX_NUM_BATCHED_TOKENS=5120
PER_DEVICE_UPDATE_MINI_BATCH=4
PER_DEVICE_EXP_MINI_BATCH=16

WANDB_PROJECT="memory_rl"
CAND_NUM=4
EXP_NAME="rl__qwen3_4b__cand${CAND_NUM}__maxstep_${MAX_STEPS}_rb${ROLLOUT_BATCH_SIZE}_rn${ROLLOUT_N}_gb${GLOBAL_BATCH_SIZE}"

CONFIG_FILE="memory_rl/configs/config.yaml"
TRAIN_FILE="dataset/rl_data/train.parquet"
TEST_FILE="dataset/rl_data/test.parquet"

FORMAT_PROMPT="memory_rl/configs/memory_offline.jinja"
REWARD_FUNCTION="memory_rl/reward/memory_offline.py:compute_score"

python3 -m verl.trainer.main \
    config=${CONFIG_FILE} \
    data.train_files=${TRAIN_FILE} \
    data.val_files=${TEST_FILE} \
    data.val_batch_size=${VAL_BATCH_SIZE} \
    data.rollout_batch_size=${ROLLOUT_BATCH_SIZE} \
    data.format_prompt=${FORMAT_PROMPT} \
    worker.rollout.tensor_parallel_size=1 \
    worker.rollout.n=${ROLLOUT_N} \
    worker.rollout.val_override_config.n=${VAL_N} \
    worker.rollout.max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS} \
    worker.actor.model.model_path=${MODEL_PATH} \
    worker.actor.global_batch_size=${GLOBAL_BATCH_SIZE} \
    trainer.experiment_name=${EXP_NAME} \
    trainer.n_gpus_per_node=${N_GPU} \
    trainer.total_epochs=${TOTAL_EPOCHES} \
    trainer.project_name=${WANDB_PROJECT} \
    trainer.max_steps=${MAX_STEPS} \
    trainer.logger=["console","wandb"] \
    worker.reward.reward_function=${REWARD_FUNCTION} \
    data.max_prompt_length=${MAX_PROMPT_LENGTH} \
    data.max_response_length=${MAX_RESPONSE_LENGTH} \
    worker.actor.micro_batch_size_per_device_for_update=${PER_DEVICE_UPDATE_MINI_BATCH} \
    worker.actor.micro_batch_size_per_device_for_experience=${PER_DEVICE_EXP_MINI_BATCH} \
    data.filter_overlong_prompts=false \
    trainer.val_before_train=true
