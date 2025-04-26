#!/usr/bin/env python3
"""
test_workstreams.py - Test script to detect custom fields in GitHub Projects

This script helps identify the custom fields in a GitHub Project, including
the "Workstream" field and its options.
"""

import argparse
import yaml
import sys
import os
import json
import requests
from pathlib import Path

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

def load_config():
    """
    Load configuration from secrets.yaml and config.yaml
    
    The configuration files are expected to be in the parent directory of kickoff-kit.
    """
    try:
        # Get the parent directory (go up from the current script location)
        current_dir = Path(__file__).resolve().parent  # pruner directory
        kickoff_kit_dir = current_dir.parent  # kickoff-kit directory
        parent_dir = kickoff_kit_dir.parent  # parent of kickoff-kit
        
        # Load secrets.yaml from parent directory
        secrets_path = parent_dir / "secrets.yaml"
        if not secrets_path.exists():
            log(f"Secrets file not found: {secrets_path}", "ERROR")
            sys.exit(1)
            
        with open(secrets_path, 'r') as f:
            secrets = yaml.safe_load(f)
            
        if 'github_token' not in secrets:
            log("GitHub token not found in secrets.yaml", "ERROR")
            sys.exit(1)
        
        # Load config.yaml from parent directory
        config_path = parent_dir / "config.yaml"
        if not config_path.exists():
            log(f"Config file not found: {config_path}", "ERROR")
            sys.exit(1)
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return {
            "github_token": secrets["github_token"],
            "config": config
        }
    except Exception as e:
        log(f"Failed to load configuration: {str(e)}", "ERROR")
        sys.exit(1)

def get_project_fields(github_token, project_id):
    """
    Get project field information including custom fields using GitHub's GraphQL API
    """
    log(f"Fetching project fields for project ID: {project_id}")
    
    # GraphQL query to get project fields
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          id
          title
          url
          fields(first: 20) {
            nodes {
              ... on ProjectV2Field {
                id
                name
                dataType
              }
              ... on ProjectV2IterationField {
                id
                name
                dataType
              }
              ... on ProjectV2SingleSelectField {
                id
                name
                dataType
                options {
                  id
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    """
    
    # Make the API request
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={"query": query, "variables": {"projectId": project_id}}
    )
    
    if response.status_code != 200:
        log(f"Failed to fetch project fields: {response.text}", "ERROR")
        sys.exit(1)
        
    data = response.json()
    
    if "errors" in data:
        log(f"GraphQL errors: {data['errors']}", "ERROR")
        sys.exit(1)
    
    return data["data"]["node"]

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Detect custom fields in GitHub Projects")
    parser.add_argument("--project-id", help="GitHub Project ID (optional, will try to detect from config.yaml)")
    args = parser.parse_args()
    
    # Display header
    print(f"\n{Colors.HEADER}===== GitHub Project Field Detector ====={Colors.ENDC}")
    
    try:
        # Load configuration
        log("Loading configuration from parent directory")
        config_data = load_config()
        github_token = config_data["github_token"]
        
        # Determine project ID
        project_id = args.project_id
        
        # If project_id not provided, try to get it from config
        if not project_id:
            if "pruner" in config_data["config"] and "project_id" in config_data["config"]["pruner"]:
                project_id = config_data["config"]["pruner"]["project_id"]
                log(f"Using project ID from config.yaml: {project_id}")
            elif "create_project" in config_data["config"]:
                # We need to find the project ID based on the project_title
                log("Project ID not found in config. Please provide it manually.")
                project_id = input("Enter project ID: ").strip()
                if not project_id:
                    log("No project ID provided. Exiting.", "ERROR")
                    sys.exit(1)
        
        if not project_id:
            log("Project ID not specified. Exiting.", "ERROR")
            sys.exit(1)
        
        # Get project fields
        project_data = get_project_fields(github_token, project_id)
        
        # Display project information
        print(f"\n{Colors.GREEN}Project:{Colors.ENDC} {project_data['title']}")
        print(f"{Colors.GREEN}URL:{Colors.ENDC} {project_data['url']}")
        
        # Display field information
        print(f"\n{Colors.HEADER}Fields:{Colors.ENDC}")
        for field in project_data["fields"]["nodes"]:
            field_type = field.get("dataType", "unknown")
            print(f"  {Colors.BOLD}{field['name']}{Colors.ENDC} ({field_type})")
            
            # If it's a single select field with options, show options
            if "options" in field:
                print(f"    {Colors.YELLOW}Options:{Colors.ENDC}")
                for option in field["options"]:
                    print(f"      - {option['name']} ({option['color']})")
        
        # Look for workstream field
        workstream_field = None
        
        # First try the exact name from config if available
        workstream_field_name = None
        if "pruner" in config_data["config"] and "custom_fields" in config_data["config"]["pruner"]:
            workstream_field_name = config_data["config"]["pruner"]["custom_fields"].get("workstream_field_id")
        
        # If not in pruner config, check create_project custom_fields
        if not workstream_field_name and "create_project" in config_data["config"] and "custom_fields" in config_data["config"]["create_project"]:
            for field in config_data["config"]["create_project"]["custom_fields"]:
                if field["name"].lower() == "workstream":
                    workstream_field_name = field["name"]
                    break
        
        # If we found a workstream field name, look for it in the project
        if workstream_field_name:
            for field in project_data["fields"]["nodes"]:
                if field["name"].lower() == workstream_field_name.lower():
                    workstream_field = field
                    break
        
        # If still not found, try generic search
        if not workstream_field:
            for field in project_data["fields"]["nodes"]:
                if field["name"].lower() == "workstream" or "workstream" in field["name"].lower():
                    workstream_field = field
                    break
        
        # Display workstream information
        print(f"\n{Colors.HEADER}Workstream Field Detection:{Colors.ENDC}")
        if workstream_field:
            print(f"  {Colors.GREEN}Found Workstream field:{Colors.ENDC} {workstream_field['name']}")
            if "options" in workstream_field:
                print(f"  {Colors.GREEN}Available options:{Colors.ENDC}")
                for option in workstream_field["options"]:
                    print(f"    - {option['name']}")
            
            # Create sample configuration
            print(f"\n{Colors.HEADER}Sample Configuration for config.yaml:{Colors.ENDC}")
            print(f"""
# Add to your config.yaml file:
pruner:
  project_id: "{project_id}"
  done_age_days: 14
  done_overflow_limit: 3
  wiki_page_name: "Pruner Audit Log"
  dry_run: true
  custom_fields:
    workstream_field_id: "{workstream_field['name']}"
    status_field_id: "Status"  # Adjust based on your project
    done_status_value: "Done"  # Adjust based on your project
""")
        else:
            print(f"  {Colors.YELLOW}No dedicated Workstream field found.{Colors.ENDC}")
            print("  You'll need to identify which field represents workstreams in your project")
            print("  and update your config.yaml accordingly.")
        
        log("Field detection complete!", "SUCCESS")
        
    except KeyboardInterrupt:
        print("\n")
        log("Process interrupted by user. Exiting.", "WARNING")
        sys.exit(0)
    except Exception as e:
        log(f"Unexpected error: {str(e)}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()