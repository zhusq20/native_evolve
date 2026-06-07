"""
JSON Utils
"""

import os
import json
from typing import List, Dict, Union

def ensure_parent_directory(file_path):
    # Get the parent directory
    parent_dir = os.path.dirname(file_path)
    
    # Create the parent directory if it doesn't exist
    if parent_dir:  # Check if parent_dir is not empty
        os.makedirs(parent_dir, exist_ok=True)

def save_to_json(data: Union[List[Dict], Dict], file_path: str) -> None:
    """
    Save a dictionary or list of dictionaries to a JSON file at the specified file path.

    :param data (dict or list of dict): The data to be saved. Can be a single dictionary or a list of dictionaries.
    :param file_path (str): The path where the JSON file will be saved.
    :return: None
    """
    ensure_parent_directory(file_path)
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4)


def save_to_jsonl(data: Union[List[Dict], Dict], file_path: str) -> None:
    """
    Save a dictionary or list of dictionaries to a JSONL file at the specified file path.

    :param data (dict or list of dict): A single dictionary or a list of dictionaries to be saved, where each dictionary represents a single JSON object.
    :param file_path (str): The path where the JSONL file will be saved.
    :return: None
    """
    ensure_parent_directory(file_path)
    
    # Ensure data is a list of dictionaries
    if isinstance(data, Dict):
        sorted_dict = dict(sorted(data.items()))
        data = [sorted_dict]

    with open(file_path, 'w', encoding='utf-8') as jsonl_file:
        for entry in data:
            json_line = json.dumps(entry)
            jsonl_file.write(json_line + '\n')


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
    

def read_from_jsonl(file_path: str) -> list:
    """
    Reads JSONL data from a file and returns it as a list of dictionaries.
    Each line in the file represents a JSON object.

    :param file_path: The path of the JSONL file to be read.
    :return: List of dictionaries containing the JSON data, or an empty list if the file does not exist or is empty.
    """
    data = []
    
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:  # check if the file exists and is not empty
        with open(file_path, 'r', encoding='utf-8') as jsonl_file:
            for line in jsonl_file:
                data.append(json.loads(line.strip()))
    
    return data

def sanitize_for_json(obj):
    """
    Recursively convert a structure to be JSON serializable.
    """
    import subprocess
    
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_json(item) for item in obj)
    elif isinstance(obj, subprocess.CompletedProcess):
        # CompletedProcess has args instead of cmd
        return {
            'returncode': obj.returncode,
            'args': str(obj.args),
            'stdout': str(obj.stdout) if hasattr(obj, 'stdout') else None,
            'stderr': str(obj.stderr) if hasattr(obj, 'stderr') else None,
            'type': obj.__class__.__name__
        }
    elif isinstance(obj, subprocess.CalledProcessError):
        # CalledProcessError has cmd
        return {
            'returncode': obj.returncode,
            'cmd': str(obj.cmd),
            'stdout': str(obj.stdout) if hasattr(obj, 'stdout') else None,
            'stderr': str(obj.stderr) if hasattr(obj, 'stderr') else None,
            'type': obj.__class__.__name__
        }
    elif hasattr(obj, '__dict__'):  # For other custom objects
        return str(obj)
    else:
        return obj
        