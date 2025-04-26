"""
issues package for GitHub Issue creation from CSV files

This package provides modules for analyzing CSV files,
validating inputs, and creating GitHub Issues with proper
field values based on the CSV data.
"""

__version__ = "1.0.0"

# Import all modules
from . import analyzer
from . import creator
from . import validator