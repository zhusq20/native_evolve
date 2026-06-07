from openai import OpenAI
from typing import List
from utils.logger import logger

def count_tokens_with_api(
    message_list: List,
    model_name: str = "openhands-lm-32b-v0.1",
    temperature: float = 0.7
):
    """
    Use the OpenAI API to count tokens in messages.
    This is more accurate but requires an API call.
    """
    client = OpenAI(
        base_url="http://localhost:1234/v1",  # Using the port from your working curl example
        api_key="dummy"  # Use a non-empty dummy value
    )
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=message_list,
            temperature=temperature,
            max_tokens=1,  # Set to 0 to just get token count without generating a response
        )

        # The response includes prompt_tokens, completion_tokens, and total_tokens
        return response.usage.prompt_tokens

    except Exception as e:
        return 'Exceeded'
    
    

def openhands_model_interact(
    message_list: List,
    model_name: str = "openhands-lm-32b-v0.1",
    max_token: int = 8192,
    max_output_token: int = 512,
    temperature: float = 0.7
):
    cost = 0
    client = OpenAI(
        base_url="http://localhost:1234/v1",  # Using the port from your working curl example
        api_key="dummy"  # Use a non-empty dummy value
    )

    input_token_num = count_tokens_with_api(message_list, model_name)
    if input_token_num == 'Exceeded':
        input_token_num = max_token
        
    max_input_token = max_token - max_output_token
    if input_token_num > max_input_token:
        exceed = (
            f"[WARNING] Current message has exceeded max token limit:"
            f"\nmax tokens = {max_token}\ncurrent tokens = {input_token_num} + 512"
            f"\nWill skip remaining turns and move on to the next instance..."
        )
        logger.warning(exceed)
        return exceed, cost

    response = client.chat.completions.create(
        model=model_name,
        messages=message_list,
        temperature=temperature,
        max_tokens=max_output_token
    )
    
    return response.choices[0].message.content, cost