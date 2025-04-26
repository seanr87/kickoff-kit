"""
validator.py - Validation module for input parameters

This module handles validation of CSV files, GitHub URLs,
and other input parameters to ensure they meet requirements.
"""

import csv
import os
import re
from pathlib import Path

def log(message):
    """Simple logging function"""
    print(f"[validator] {message}")

def validate_csv(csv_path):
    """
    Validate that a CSV file exists and contains required columns
    Returns True if valid, False otherwise
    """
    # Check if file exists
    if not os.path.exists(csv_path):
        log(f"CSV file not found: {csv_path}")
        return False
    
    # Check if file is readable
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            if not headers:
                log(f"CSV file has no headers")
                return False
            
            # Check for required 'title' column
            title_header = None
            for header in headers:
                if header.lower() == 'title':
                    title_header = header
                    break
            
            if not title_header:
                log(f"CSV file must contain a 'title' column")
                return False
            
            # Check if there's at least one row
            first_row = next(reader, None)
            if not first_row:
                log(f"CSV file has no data rows")
                return False
                
            # Check if title column has a value in the first row
            if not first_row.get(title_header):
                log(f"First row does not have a value for 'title' column")
                return False
            
            return True
    except Exception as e:
        log(f"Error validating CSV file: {str(e)}")
        return False

def validate_github_urls(repo_url, project_url):
    """
    Validate GitHub repository and project URLs
    Returns tuple of (repo_owner, repo_name, project_number) if valid,
    otherwise returns (None, None, None)
    """
    # Validate repository URL
    repo_match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/?.*', repo_url)
    if not repo_match:
        log(f"Invalid repository URL format: {repo_url}")
        log("URL should be in format: https://github.com/owner/repo")
        return None, None, None
    
    repo_owner = repo_match.group(1)
    repo_name = repo_match.group(2)
    
    # Remove .git suffix if present
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    
    # Validate project URL
    project_match = re.match(r'https?://github\.com/(?:orgs|users)/([^/]+)/projects/(\d+).*', project_url)
    if not project_match:
        log(f"Invalid project URL format: {project_url}")
        log("URL should be in format: https://github.com/orgs/owner/projects/number")
        return None, None, None
    
    project_number = int(project_match.group(2))
    
    return repo_owner, repo_name, project_number

def validate_field_values(field_name, field_values, existing_options=None):
    """
    Validate field values for compatibility with GitHub Projects
    Returns tuple of (is_valid, message)
    """
    if not field_values:
        return True, None
    
    # Check for length limits on field names (50 char limit in GitHub)
    if len(field_name) > 50:
        return False, f"Field name '{field_name}' exceeds GitHub's 50 character limit"
    
    # Check for option count limit (50 options per field in GitHub)
    if len(field_values) > 50:
        return False, f"Field '{field_name}' has {len(field_values)} unique values, exceeding GitHub's limit of 50 options"
    
    # Check for option name length limit (50 char limit in GitHub)
    for value in field_values:
        if len(value) > 50:
            return False, f"Option '{value}' for field '{field_name}' exceeds GitHub's 50 character limit"
    
    return True, None