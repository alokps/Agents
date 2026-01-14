#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from coder_agent.crew import CoderAgent

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    assignment = "Write a python program to calculate the first 100 terms \
        of this series: 1/n^2 where n starts from 1 and then average the result."
    
    inputs = {
        'assignment': assignment
    }
    
    try:
        result = CoderAgent().crew().kickoff(inputs=inputs)
        print(result.raw)
    except RuntimeError as e:
        raise RuntimeError(f"An error occurred while running the crew: {e}")
