import re
from typing import Any

# Metadata
REWARD_NAME = "memory_offline"
REWARD_TYPE = "sequential"


# Format
def format_reward(response: str) -> float:
    """Evaluate format reward"""
    pattern = re.compile(r"<think>.*?</think>\s*<answer>.*?</answer>", re.DOTALL)
    format_match = re.fullmatch(pattern, response)
    return 1.0 if format_match else 0.0


# Answer
def answer_reward(model_answer: str, gt_answer: str) -> float:
    """Evaluate answer reward with proper multi-choice handling"""

    # Exact match
    if model_answer == gt_answer:
        return 1.0
    
    # Parse model answer
    if "," in model_answer:
        model_answer_set = set(opt.strip() for opt in model_answer.split(",") if opt.strip())
    else:
        model_answer_set = {model_answer.strip()} if model_answer.strip() else set()
    
    # Parse ground truth answer
    if "," in gt_answer:
        gt_answer_set = set(opt.strip() for opt in gt_answer.split(",") if opt.strip())
    else:
        gt_answer_set = {gt_answer.strip()} if gt_answer.strip() else set()
    
    # Exact match
    if model_answer_set == gt_answer_set:
        return 1.0
    
    # No match at all
    if not model_answer_set or not gt_answer_set:
        return 0.0
    
    # Partial credit based on F1-like score
    # Calculate true positives, false positives, false negatives
    true_positives = len(model_answer_set & gt_answer_set)
    false_positives = len(model_answer_set - gt_answer_set)
    false_negatives = len(gt_answer_set - model_answer_set)
    
    if true_positives == 0:
        return 0.0
    
    # Use F1 score for partial credit
    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)
    f1_score = 2 * (precision * recall) / (precision + recall)
    
    return f1_score


def accuracy_reward(response: str, ground_truth: str) -> float:
    try:
        content_match = re.search(r"<answer>(.*?)</answer>", response)
        model_answer = content_match.group(1).strip() if content_match else response.strip()
        return answer_reward(model_answer.strip(), ground_truth.strip())
    except Exception:
        pass
    return 0.0


def compute_score(reward_input: dict[str, Any], format_weight: float = 0.2) -> dict[str, float]:
    format_score = format_reward(reward_input["response"])
    accuracy_score = accuracy_reward(reward_input["response"], reward_input["ground_truth"])
    return {
        "overall": (1 - format_weight) * accuracy_score + format_weight * format_score,
        "format": format_score,
        "accuracy": accuracy_score,
    }