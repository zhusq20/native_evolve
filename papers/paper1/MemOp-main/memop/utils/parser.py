import ast
from utils.logger import logger

def recover_list_from_string(input_string):
    try:
        # Use ast.literal_eval to safely parse the string
        recovered_list = ast.literal_eval(input_string)
        # Ensure the result is a list
        if isinstance(recovered_list, list):
            return recovered_list
        else:
            raise ValueError("Input string is not a list representation.")
    except (ValueError, SyntaxError) as e:
        logger.error(f"Error recovering list: {e}")
        return None

def recover_dict_from_string(dict_str):
    try:
        # Use literal_eval to safely parse the string to a dictionary
        real_dict = ast.literal_eval(dict_str)
        if isinstance(real_dict, dict):
            return real_dict
        else:
            raise ValueError(f"Input string is not a dictionary representation.")
    except (ValueError, SyntaxError):
        logger.error(f"Error: '{dict_str}' is not a valid dictionary string.")
