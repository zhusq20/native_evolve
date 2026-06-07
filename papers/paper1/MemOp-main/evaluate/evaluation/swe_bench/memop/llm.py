import os
import copy
import litellm
import logging
from typing import List, Dict, Tuple, Any


class LiteLLMAPI:
    """
    LiteLLM API handler with automatic cost calculation
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        input_cost_per_token: float = None,
        output_cost_per_token: float = None,
        log_completions: bool = True,
        truncation_method: str = "last",
        max_input_token: int = 128000,
    ):
        """
        Initialize the LiteLLM API handler

        Args:
            model: Model name (e.g., "litellm_proxy/mistral/devstral-small-2505")
            api_key: API key for authentication
            base_url: Base URL for the API
            temperature: Sampling temperature (0.0 for deterministic)
            input_cost_per_token: Cost per input token
            output_cost_per_token: Cost per output token
            log_completions: Whether to log completion details
            truncation_method: How to truncate trajectory when too long.
                "middle" (default for agent/llm.py): remove from the middle, preserving beginning (context) and end (results).
                "first": remove from the beginning (oldest items first).
                "last" (default): remove from the end (newest items first).
            max_input_token: Maximum input tokens before truncation kicks in.
                Different models have different limits (e.g., 8k, 32k, 128k).
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.input_cost_per_token = input_cost_per_token
        self.output_cost_per_token = output_cost_per_token
        self.log_completions = log_completions
        self.truncation_method = truncation_method
        self.reduce_rate = 0.9
        self.max_input_token = max_input_token
        
        # Configure LiteLLM
        litellm.api_key = self.api_key
        litellm.api_base = self.base_url
        
        if self.log_completions:
            litellm.set_verbose = True
            logging.basicConfig(level=logging.INFO)
    
    def count_tokens(self, text: str, model: str = None) -> int:
        """
        Count tokens in text using LiteLLM's token counting
        
        Args:
            text: Text to count tokens for
            model: Model name (uses self.model if not provided)
            
        Returns:
            Number of tokens
        """
        try:
            model_name = model or self.model
            return litellm.token_counter(model=model_name, text=text)
        except Exception as e:
            # Fallback: rough estimation (1 token ≈ 4 characters for most models)
            logging.warning(f"Token counting failed: {e}. Using rough estimation.")
            return len(text) // 4
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate the total cost based on input and output tokens
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Total cost in USD
        """
        if self.input_cost_per_token is None or self.output_cost_per_token is None:
            return 0.0
        
        input_cost = input_tokens * self.input_cost_per_token
        output_cost = output_tokens * self.output_cost_per_token
        total_cost = input_cost + output_cost
        
        if self.log_completions:
            logging.info(f"Cost breakdown - Input: ${input_cost:.6f} ({input_tokens} tokens), "
                        f"Output: ${output_cost:.6f} ({output_tokens} tokens), "
                        f"Total: ${total_cost:.6f}")
        
        return total_cost
    
    def interact_without_limit(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        """
        Interact with the LLM and calculate cost
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
        
        Returns:
            Tuple of (response_content, total_cost)
        """
        try:
            # Calculate input tokens
            input_text = ""
            for message in messages:
                input_text += f"{message.get('role', '')}: {message.get('content', '')}\n"
            
            input_tokens = self.count_tokens(input_text)
            
            # Make API call
            response = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                api_key=self.api_key,
                api_base=self.base_url,
                timeout=120,  # 2 minutes
                max_retries=2,
                drop_params=True,
                num_retries=2,
            )
            
            # Extract response content
            response_content = response.choices[0].message.content
            
            # Calculate output tokens
            output_tokens = self.count_tokens(response_content)
            
            # Calculate cost
            total_cost = self.calculate_cost(input_tokens, output_tokens)
            
            if self.log_completions:
                logging.info(f"API call completed - Model: {self.model}, "
                           f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, "
                           f"Cost: ${total_cost:.6f}")
            
            return response_content, total_cost
            
        except Exception as e:
            logging.error(f"API interaction failed: {e}")
            raise e

    def interact(self, messages: List[Dict[str, str]], user_input: List) -> Tuple[str, float]:
        """
        Interact with the LLM and calculate cost with intelligent fallback
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                    Example: [{"role": "system", "content": "..."}, {"role": "user", "content": str(raw_trajectory)}]
            user_input: Raw trajectory list (list of dicts) that will be progressively reduced
        
        Returns:
            Tuple of (response_content, total_cost)
        """
        
        def estimate_tokens(msgs):
            """Estimate total tokens for a list of messages"""
            total_text = ""
            for message in msgs:
                total_text += f"{message.get('role', '')}: {message.get('content', '')}\n"
            return self.count_tokens(total_text)
        
        def make_api_call(msgs, timeout=120):
            """Make the actual API call"""
            # Force disable caching to ensure fresh requests
            response = litellm.completion(
                model=self.model,
                messages=msgs,
                temperature=self.temperature,
                api_key=self.api_key,
                api_base=self.base_url,
                timeout=timeout,
                max_retries=1,  # Reduced to let our logic handle retries
                drop_params=True,
                cache={"no-cache": True},  # Force disable caching
                **{"extra_body": {}}  # Ensure fresh request
            )
            return response
        
        # Work with copies to avoid modifying original data
        current_user_input = user_input.copy()
        max_attempt = len(current_user_input)

        for attempt in range(max_attempt):
            try:
                # Create completely fresh message list with updated trajectory content
                current_messages = []
                for message in messages:
                    if message.get('role') == 'user':
                        # Rebuild user message with current trajectory
                        user_content = str(current_user_input)
                        current_messages.append({
                            "role": "user",
                            "content": user_content
                        })
                        
                        # Debug: Log actual content length being sent
                        if self.log_completions and attempt > 0:
                            logging.info(f"DEBUG: User content length: {len(user_content)} chars, "
                                    f"Trajectory items: {len(current_user_input)}")
                    else:
                        # Keep other messages (like system) unchanged
                        current_messages.append({
                            "role": message.get('role'),
                            "content": message.get('content')
                        })
                
                # Estimate input size and set appropriate timeout
                estimated_tokens = estimate_tokens(current_messages)

                # Pre-validate and aggressively reduce to avoid costly failed API calls
                if estimated_tokens > self.max_input_token:
                    if self.log_completions:
                        logging.info(f"Pre-validation: Estimated {estimated_tokens} tokens > 195k limit. "
                                f"Aggressively reducing context to avoid failed API calls...")
                    
                    while estimated_tokens > self.max_input_token and len(current_user_input) > 10:
                        # Remove one trajectory item based on truncation method
                        if self.truncation_method == "middle":
                            current_user_input.pop(len(current_user_input) // 2)
                        elif self.truncation_method == "first":
                            current_user_input.pop(0)
                        else:  # "last"
                            current_user_input.pop()
                        
                        # Rebuild messages with reduced trajectory
                        current_messages = []
                        for message in messages:
                            if message.get('role') == 'user':
                                user_content = str(current_user_input)
                                current_messages.append({
                                    "role": "user", 
                                    "content": user_content
                                })
                            else:
                                current_messages.append({
                                    "role": message.get('role'),
                                    "content": message.get('content')
                                })
                        
                        # Recalculate tokens
                        estimated_tokens = estimate_tokens(current_messages)
                        
                        if self.log_completions:
                            logging.info(f"Pre-validation: Reduced to {len(current_user_input)} trajectory items "
                                    f"(~{estimated_tokens} tokens)")
                
                # Dynamic timeout based on input size
                if estimated_tokens > 120000:
                    timeout = 240  # 5 minutes for very large inputs
                elif estimated_tokens > 100000:
                    timeout = 180  # 4 minutes for large inputs
                elif estimated_tokens > 50000:
                    timeout = 120  # 3 minutes for medium inputs
                else:
                    timeout = 60  # 2 minutes for normal inputs
                
                if self.log_completions:
                    if attempt == 0:
                        logging.info(f"Attempting API call with {len(current_messages)} messages "
                                f"(~{estimated_tokens} tokens, {timeout}s timeout)")
                    else:
                        logging.info(f"Retry {attempt}: Reduced to {len(current_user_input)} trajectory histories "
                                f"(~{estimated_tokens} tokens, {timeout}s timeout)")
                
                # Calculate input tokens for cost calculation
                input_text = ""
                for message in current_messages:
                    input_text += f"{message.get('role', '')}: {message.get('content', '')}\n"
                input_tokens = self.count_tokens(input_text)
                
                # Debug: Log message structure being sent
                if self.log_completions and attempt > 0:
                    for i, msg in enumerate(current_messages):
                        content_preview = msg.get('content', '')[:100] + "..." if len(msg.get('content', '')) > 100 else msg.get('content', '')
                        logging.info(f"DEBUG: Message {i} ({msg.get('role')}): {content_preview}")
                
                # Make API call
                response = make_api_call(current_messages, timeout)
                
                # Success! Extract response content
                response_content = response.choices[0].message.content
                
                # Calculate output tokens and cost
                output_tokens = self.count_tokens(response_content)
                total_cost = self.calculate_cost(input_tokens, output_tokens)
                
                if self.log_completions:
                    success_msg = f"✅ API call successful"
                    if attempt > 0:
                        success_msg += f" after {attempt + 1} attempts (reduced from {max_attempt} to {len(current_user_input)} trajectory histories)"
                    success_msg += f" - Model: {self.model}, Input tokens: {input_tokens}, Output tokens: {output_tokens}, Cost: ${total_cost:.6f}"
                    logging.info(success_msg)
                
                return response_content, total_cost
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a timeout, token limit, or similar issue that might be resolved by reducing input
                is_size_related = any(keyword in error_msg for keyword in [
                    'timeout', 'too long', 'token limit', 'context length', 'maximum context',
                    'content too large', 'request too large', 'payload too large', 'context window',
                    'prompt is too long', 'maximum'
                ])
                
                if attempt < max_attempt - 1 and len(current_user_input) > 0:
                    # Remove one trajectory item based on truncation method
                    if self.truncation_method == "middle":
                        current_user_input.pop(len(current_user_input) // 2)
                    elif self.truncation_method == "first":
                        current_user_input.pop(0)
                    else:  # "last"
                        current_user_input.pop()
                    
                    if self.log_completions:
                        if is_size_related:
                            logging.warning(f"❌ Attempt {attempt + 1} failed (Context/Token limit: {type(e).__name__}). "
                                        f"Removing the last trajectory history and retrying... "
                                        f"({len(current_user_input)}/{max_attempt} trajectory histories remaining)")
                        else:
                            logging.warning(f"❌ Attempt {attempt + 1} failed ({type(e).__name__}). "
                                        f"Removing the last trajectory history and retrying... "
                                        f"({len(current_user_input)}/{max_attempt} trajectory histories remaining)")
                    
                    # Force garbage collection and clear any potential caches
                    import gc
                    gc.collect()
                    
                    continue  # Try again with reduced input
                
                else:
                    # Final attempt failed or no more items to remove
                    if self.log_completions:
                        logging.error(f"❌ All attempts failed. Final error with {len(current_user_input)} trajectory histories: {e}")
                    
                    raise Exception(f"API interaction failed after {attempt + 1} attempts. "
                                f"Reduced from {max_attempt} to {len(current_user_input)} trajectory histories. "
                                f"Final error: {e}")
        
        # This should never be reached, but just in case
        raise Exception("Unexpected end of retry loop")
