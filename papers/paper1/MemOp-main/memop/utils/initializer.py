import os

def path_initializer(path):
    """
    Check if the input path exists, create it if it doesn't exist.
    
    Args:
        path (str): File or directory path
        
    Returns:
        bool: True if path already existed, False if created
    """
    # Check if the path is a file path (has extension) or directory path
    path_components = os.path.split(path)
    filename = path_components[-1]
    
    # Determine if this is a file path
    is_file_path = '.' in filename and filename not in ['.', '..']
    
    # Get the directory path
    if is_file_path:
        directory_path = os.path.dirname(path)
    else:
        directory_path = path
    
    # Check if directory exists and create if needed
    if os.path.exists(directory_path):
        print(f"Directory '{directory_path}' already exists.")
        path_existed = True
    else:
        print(f"Creating directory '{directory_path}'...")
        os.makedirs(directory_path, exist_ok=True)
        path_existed = False
    
    return path_existed