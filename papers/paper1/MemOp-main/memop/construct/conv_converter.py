import json
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path


class LLMCompletionsParser:
    """
    Parser for OpenHands llm_completions files to extract standard conversation format.
    """
    
    def __init__(self):
        self.timestamp_pattern = re.compile(r'default-(\d+\.\d+)\.json')
    
    def parse_instance_conversations(self, llm_completions_dir: str) -> List[Dict[str, str]]:
        """
        Parse all llm_completions JSON files for a single instance and return standard conversation format.
        
        Args:
            llm_completions_dir: Path to the llm_completions directory for an instance
                               (e.g., ".../llm_completions/astropy__astropy-14309")
        
        Returns:
            List of conversation messages in standard format:
            [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        """
        llm_completions_path = Path(llm_completions_dir)
        
        if not llm_completions_path.exists():
            raise FileNotFoundError(f"Directory not found: {llm_completions_dir}")
        
        # Get all JSON files and sort by timestamp
        json_files = []
        for file_path in llm_completions_path.glob("*.json"):
            match = self.timestamp_pattern.match(file_path.name)
            if match:
                timestamp = float(match.group(1))
                json_files.append((timestamp, file_path))
        
        if not json_files:
            raise ValueError(f"No valid JSON files found in {llm_completions_dir}")
        
        # Sort by timestamp
        json_files.sort(key=lambda x: x[0])
        
        # Process files to extract conversation
        conversation = []
        seen_messages = set()  # To avoid duplicates
        
        for timestamp, file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract messages from this API call
                new_messages = self._extract_messages_from_api_call(data)
                
                # Add only new messages (avoiding duplicates from conversation history)
                for message in new_messages:
                    message_hash = self._hash_message(message)
                    if message_hash not in seen_messages:
                        conversation.append(message)
                        seen_messages.add(message_hash)
            
            except (json.JSONDecodeError, KeyError, Exception) as e:
                print(f"Warning: Error processing {file_path}: {e}")
                continue
        
        return conversation
    
    def _extract_messages_from_api_call(self, api_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract messages from a single API call data structure.
        
        Different API formats are handled:
        - OpenAI format: {"messages": [...]}
        - Anthropic format: {"messages": [...]}
        - Other formats with similar structure
        """
        messages = []
        
        # Try to find messages in the API call data
        if "messages" in api_data:
            # Direct messages array (most common case)
            raw_messages = api_data["messages"]
        elif "request" in api_data and "messages" in api_data["request"]:
            # Nested under request
            raw_messages = api_data["request"]["messages"]
        elif "prompt" in api_data:
            # Single prompt format - convert to messages
            return [{"role": "user", "content": api_data["prompt"]}]
        else:
            # Try to find messages in nested structures
            raw_messages = self._find_messages_recursive(api_data)
        
        if not raw_messages:
            return []
        
        # Convert to standard format
        for msg in raw_messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                # Standard format
                messages.append({
                    "role": msg["role"],
                    "content": str(msg["content"])
                })
            elif isinstance(msg, dict) and "type" in msg and "text" in msg:
                # Anthropic format
                role = msg.get("type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                messages.append({
                    "role": role,
                    "content": msg["text"]
                })
        
        # Add assistant response if present in the API response
        if "response" in api_data:
            assistant_content = self._extract_assistant_response(api_data["response"])
            if assistant_content:
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
        elif "choices" in api_data and api_data["choices"]:
            # OpenAI format response
            choice = api_data["choices"][0]
            if "message" in choice:
                content = choice["message"].get("content", "")
                if content:
                    messages.append({
                        "role": "assistant",
                        "content": content
                    })
        
        return messages
    
    def _find_messages_recursive(self, data: Any) -> List[Dict]:
        """Recursively search for messages array in nested data structures."""
        if isinstance(data, dict):
            if "messages" in data:
                return data["messages"]
            for value in data.values():
                result = self._find_messages_recursive(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_messages_recursive(item)
                if result:
                    return result
        return []
    
    def _extract_assistant_response(self, response_data: Any) -> Optional[str]:
        """Extract assistant response from various response formats."""
        if isinstance(response_data, str):
            return response_data
        elif isinstance(response_data, dict):
            # Try common response fields
            for field in ["content", "text", "message", "output"]:
                if field in response_data:
                    content = response_data[field]
                    if isinstance(content, str):
                        return content
                    elif isinstance(content, dict) and "content" in content:
                        return str(content["content"])
        return None
    
    def _hash_message(self, message: Dict[str, str]) -> str:
        """Create a hash for a message to detect duplicates."""
        return f"{message['role']}:{hash(message['content'])}"
    
    def process_multiple_instances(self, base_dir: str, instance_ids: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Process multiple instances and return conversations for each.
        
        Args:
            base_dir: Base directory containing llm_completions subdirectories
            instance_ids: List of instance IDs to process
        
        Returns:
            Dictionary mapping instance_id -> conversation list
        """
        results = {}
        
        for instance_id in instance_ids:
            instance_dir = os.path.join(base_dir, instance_id)
            try:
                conversation = self.parse_instance_conversations(instance_dir)
                results[instance_id] = conversation
                print(f"Successfully processed {instance_id}: {len(conversation)} messages")
            except Exception as e:
                print(f"Error processing {instance_id}: {e}")
                results[instance_id] = []
        
        return results
    
    def save_conversation_to_file(self, conversation: List[Dict[str, str]], output_path: str):
        """Save conversation to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
    
    def get_conversation_stats(self, conversation: List[Dict[str, str]]) -> Dict[str, int]:
        """Get statistics about the conversation."""
        stats = {"total_messages": len(conversation)}
        role_counts = {}
        
        for message in conversation:
            role = message["role"]
            role_counts[role] = role_counts.get(role, 0) + 1
        
        stats.update(role_counts)
        return stats


def parse_single_instance(llm_completions_dir: str) -> List[Dict[str, str]]:
    """
    Simple function to parse a single instance.
    
    Args:
        llm_completions_dir: Path to llm_completions directory for one instance
    
    Returns:
        Standard conversation format list
    """
    parser = LLMCompletionsParser()
    return parser.parse_instance_conversations(llm_completions_dir)


def parse_all_instances_in_directory(base_dir: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Parse all instances found in a base directory.
    
    Args:
        base_dir: Base directory containing multiple instance subdirectories
    
    Returns:
        Dictionary mapping instance_id -> conversation
    """
    parser = LLMCompletionsParser()
    
    # Find all instance directories
    base_path = Path(base_dir)
    instance_dirs = [d.name for d in base_path.iterdir() if d.is_dir()]
    
    return parser.process_multiple_instances(base_dir, instance_dirs)
