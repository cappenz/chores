import tkinter as tk
import pytest
import sys
import os

# Add the parent directory to path to import the chores module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chores import ChoreStatus

def test_say_text():
    """Test the voice announcement functionality."""
    test_window = tk.Tk()
    test_chores = ChoreStatus(test_window)
    
    test_chores.say_text("This is a test.")
    
    test_window.destroy()
    
    # No assertion needed as we're just testing if the function runs without errors
    # In a real test, you might want to mock the ElevenLabs client 