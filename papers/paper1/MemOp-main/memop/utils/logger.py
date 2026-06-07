import os
import json
import datetime
import inspect


class Logger:
    def __init__(
        self
        ) -> None:
        self.hex_color_dict = {
            "content": "#000000",
            "info": "#00ff00",
            "success": "#00ff00",
            "failure": "#C2736A",
            "warning": "#ffff00",
            "testing": "#0598FF",
            "debug": "#4392F3",
            "error": "#ff0000",
            "yellow_light": "#FFFCA3",
            "pink_light": "#FFD1EA",
            "cyan_light": "#ADEEE1",
            "green_light": "#90E9AF",
            "blue_light": "#91D2FF",
            "cyan": "#30C0B4",
            "red": "#F85C63",
            "green": "#27BF60",
            "blue": "#0598FF",
        }
        self.write_path = os.path.dirname(os.path.abspath(__file__)).split('utils')[0] + '/logs/storycoder.txt'
        self.auto_write = False

    def write(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"

        # Write to save
        with open(self.write_path, 'a+') as file:
            file.write(f"\n{msg_detail}\n{msg}\n")
    
    def _auto_write(self, msg_with_detail: str) -> None:
        if self.auto_write:
            # Write to save
            with open(self.write_path, 'a+') as file:
                file.write(f"\n{msg_with_detail}\n")

    # Show plain print
    def pinfo(self, msg: str) -> None:
        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    # Exposed public method to print an info message
    def info(self, msg: str) -> None:
        self._info(msg)

    # Exposed public method to print a success message
    def success(self, msg: str) -> None:
        self._success(msg)

    # Exposed public method to print a failure message
    def failure(self, msg: str) -> None:
        self._failure(msg)

    # Exposed public method to print an error message
    def error(self, msg: str) -> None:
        self._error(msg)

    # Exposed public method to print an warning message
    def warning(self, msg: str) -> None:
        self._warning(msg)

    # Exposed public method to print an testing output
    def testing(self, msg: str) -> None:
        self._testing(msg)

    # Exposed public method to print an denugging output
    def debug(self, msg: str) -> None:
        self._debug(msg)

    # Exposed public method to print colorted text
    def colored_text(self, text: str, hex_color: str):
        self._colored_text(text, hex_color)

    # Print info messages with specific color
    def _info(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        self._colored_text(msg_detail, self.hex_color_dict["info"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    def _success(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] SUCCESS - {filename}: {line_number}"
        self.colored_text(msg_detail, self.hex_color_dict["success"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    def _failure(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] FAILURE - {filename}: {line_number}"
        self.colored_text(msg_detail, self.hex_color_dict["failure"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    
    # Print error messages with specific color
    def _error(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] ERROR - {filename}: {line_number}"
        self._colored_text(msg_detail, self.hex_color_dict["error"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    # Print warning messages with specific color
    def _warning(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] WARNING - {filename}: {line_number}"
        self._colored_text(msg_detail, self.hex_color_dict["warning"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    # Print testing output with specific color
    def _testing(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] TESTING OUTPUT - {filename}: {line_number}"
        self._colored_text(msg_detail, self.hex_color_dict["testing"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    # Print debugging output with specific color
    def _debug(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] DEBUG OUTPUT - {filename}: {line_number}"
        self._colored_text(msg_detail, self.hex_color_dict["debug"])

        # Log message content
        self._colored_text(msg, self.hex_color_dict["content"])

    def _hex_to_rgb(self, hex_color: str):
        """
        Convert a hex color code to an RGB tuple.

        Args:
            hex_color (str): The hex color string (e.g., "#e6194b").

        Returns:
            tuple: An (r, g, b) tuple with RGB values.
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    

    def _colored_text(self, text: str, hex_color: str):
        """
        Print text with a specific hex color in the terminal.

        Args:
            text (str): The text to print.
            hex_color (str): The hex color code (e.g., "#e6194b").
        """
        # Convert hex color to RGB
        r, g, b = self._hex_to_rgb(hex_color)

        # ANSI escape code for 24-bit RGB colors
        ansi_code = f"\033[38;2;{r};{g};{b}m"

        # Reset color after text
        reset_code = "\033[0m"

        # Print the colored text
        print(f"{ansi_code}{text}{reset_code}")
        
        # Auto-write logs
        self._auto_write(text)
    
    def info_with_yellow_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        # Set background color using ANSI escape codes
        r, g, b = self._hex_to_rgb(self.hex_color_dict["yellow_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        # Print with colored background
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        # Auto-write logs
        self._auto_write(msg_detail)

    def info_with_pink_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["pink_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_cyan_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["cyan_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_green_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["green_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_blue_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["blue_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)
        

# Logger
logger = Logger()
