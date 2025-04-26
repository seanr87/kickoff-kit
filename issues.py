#!/usr/bin/env python3
"""
issues.py - Main orchestrator for GitHub issue creation from CSV files

This script manages the workflow for analyzing CSV files, checking GitHub Project
fields and options, and creating issues with appropriate field values.
"""

import argparse
from pathlib import Path
import yaml
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import supporting modules - use direct imports to avoid package issues
from workflow_issues.analyzer import analyze_csv_and_project, check_project_access
from workflow_issues.creator import create_sample_issue, create_issues
from workflow_issues.validator import validate_csv, validate_github_urls

# Terminal colors for better readability
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(message, level="INFO"):
    """Log a message with appropriate formatting"""
    prefix = {
        "INFO": f"{Colors.BLUE}[INFO]{Colors.ENDC}",
        "SUCCESS": f"{Colors.GREEN}[SUCCESS]{Colors.ENDC}",
        "WARNING": f"{Colors.YELLOW}[WARNING]{Colors.ENDC}",
        "ERROR": f"{Colors.RED}[ERROR]{Colors.ENDC}",
        "PROMPT": f"{Colors.BOLD}{Colors.GREEN}[PROMPT]{Colors.ENDC}",
    }.get(level, f"[{level}]")
    
    print(f"{prefix} {message}")

def get_input(prompt, options=None):
    """Get user input with optional validation against allowed options"""
    while True:
        log(prompt, "PROMPT")
        user_input = input("> ").strip().lower()
        
        if options and user_input not in options:
            log(f"Please enter one of: {', '.join(options)}", "WARNING")
        else:
            return user_input

def load_config(config_dir):
    """Load configuration from secrets.yaml"""
    try:
        secrets_path = Path(config_dir) / "secrets.yaml"
        if not secrets_path.exists():
            log(f"Secrets file not found: {secrets_path}", "ERROR")
            sys.exit(1)
            
        with open(secrets_path, 'r') as f:
            secrets = yaml.safe_load(f)
            
        if 'github_token' not in secrets:
            log("Github token not found in secrets.yaml", "ERROR")
            sys.exit(1)
            
        return secrets
    except Exception as e:
        log(f"Failed to load configuration: {str(e)}", "ERROR")
        sys.exit(1)

def process_fields_and_options(analysis_results):
    """Process fields and options found in analysis, with user interaction"""
    # Handle standard fields
    log(f"Found {len(analysis_results['standard_fields'])} standard fields in CSV:")
    for field in analysis_results['standard_fields']:
        log(f"  - {field}")
    
    # Handle existing custom fields
    if analysis_results['existing_custom_fields']:
        log(f"Found {len(analysis_results['existing_custom_fields'])} existing custom fields in project:")
        for field in analysis_results['existing_custom_fields']:
            log(f"  - {field}")
    
    # Handle missing fields
    create_fields = []
    if analysis_results['missing_fields']:
        log(f"Found {len(analysis_results['missing_fields'])} custom fields in CSV that need to be created:", "WARNING")
        for field, values in analysis_results['missing_fields'].items():
            log(f"  - {field} (with values: {', '.join(values)})")
            
            choice = get_input(
                f"Would you like to create the field '{field}'? (yes/no)", 
                options=["yes", "no", "y", "n"]
            )
            
            if choice in ["yes", "y"]:
                create_fields.append(field)
            else:
                log(f"Field '{field}' will not be created. This may affect issue creation.", "WARNING")
    
    # Handle missing options
    missing_options = analysis_results['missing_options']
    if missing_options:
        for field, options in missing_options.items():
            log(f"Field '{field}' is missing the following options:", "WARNING")
            for option in options:
                log(f"  - {option}")
            
            log("Please add these options manually in the GitHub UI:")
            log(f"1. Go to the project: {analysis_results['project_url']}")
            log("2. Click on Project settings (gear icon)")
            log(f"3. Find the '{field}' field and add the missing options")
            
            confirmation = get_input(
                "Press ENTER when done, or type 'skip' to continue without these options",
                options=["", "skip"]
            )
            
            if confirmation == "skip":
                log(f"Continuing without adding options to '{field}'.", "WARNING")
    
    return create_fields

def main():
    parser = argparse.ArgumentParser(description="Create GitHub issues from CSV with project field support")
    parser.add_argument("--config-dir", required=True, help="Directory containing secrets.yaml file")
    parser.add_argument("--csv", required=True, help="Path to CSV file with issue data")
    parser.add_argument("--repo-url", required=True, help="GitHub repository URL")
    parser.add_argument("--project-url", required=True, help="GitHub project URL")
    args = parser.parse_args()
    
    # Display header
    print(f"\n{Colors.HEADER}===== GitHub Issue Creator ====={Colors.ENDC}")
    log("Starting issue creation process...")
    
    # Load configuration
    log(f"Loading configuration from {args.config_dir}")
    config = load_config(args.config_dir)
    github_token = config['github_token']
    
    # Validate inputs
    log("Validating inputs...")
    if not validate_csv(args.csv):
        log("CSV validation failed. Exiting.", "ERROR")
        sys.exit(1)
    
    repo_owner, repo_name, project_number = validate_github_urls(args.repo_url, args.project_url)
    if not repo_owner or not repo_name or not project_number:
        log("GitHub URL validation failed. Exiting.", "ERROR")
        sys.exit(1)
    
    # Check GitHub access
    log("Checking GitHub access...")
    project_id = check_project_access(github_token, repo_owner, repo_name, project_number)
    if not project_id:
        log("GitHub access check failed. Please check your token and permissions.", "ERROR")
        sys.exit(1)
    
    # Analyze CSV and Project
    log("Analyzing CSV and Project structure...")
    analysis_results = analyze_csv_and_project(
        args.csv, 
        github_token, 
        repo_owner, 
        repo_name, 
        project_number,
        project_id,
        args.project_url
    )
    
    # Process fields and options with user interaction
    log("Processing fields and options...")
    fields_to_create = process_fields_and_options(analysis_results)
    
    # Create sample issue
    log("Creating sample issue...")
    sample_result = create_sample_issue(
        args.csv,
        github_token,
        repo_owner,
        repo_name,
        project_id,
        fields_to_create,
        analysis_results
    )
    
    if not sample_result['success']:
        log(f"Sample issue creation failed: {sample_result['error']}", "ERROR")
        sys.exit(1)
    
    # Ask for confirmation
    log(f"Sample issue created successfully: {sample_result['issue_url']}", "SUCCESS")
    continue_choice = get_input(
        "Would you like to continue creating all issues? (yes/no)",
        options=["yes", "no", "y", "n"]
    )
    
    if continue_choice not in ["yes", "y"]:
        log("Process cancelled by user. Exiting.", "WARNING")
        sys.exit(0)
    
    # Create all issues
    log("Creating all issues...")
    result = create_issues(
        args.csv,
        github_token,
        repo_owner,
        repo_name,
        project_id,
        fields_to_create,
        analysis_results,
        sample_issue_number=sample_result['issue_number']
    )
    
    # Display results
    if result['success']:
        log(f"Successfully created {result['created']} issues", "SUCCESS")
        if result['skipped']:
            log(f"Skipped {result['skipped']} issues", "WARNING")
    else:
        log(f"Issues creation process encountered errors: {result['error']}", "ERROR")
        sys.exit(1)
    
    log("Issue creation process complete!", "SUCCESS")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n")
        log("Process interrupted by user. Exiting.", "WARNING")
        sys.exit(0)
    except Exception as e:
        log(f"Unexpected error: {str(e)}", "ERROR")
        sys.exit(1)