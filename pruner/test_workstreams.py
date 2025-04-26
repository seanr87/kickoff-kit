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
            log("GitHub token not found in secrets.yaml", "ERROR")
            sys.exit(1)
            
        return secrets
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
    parser.add_argument("--config-dir", required=True, help="Directory containing secrets.yaml file")
    parser.add_argument("--project-id", required=True, help="GitHub Project ID")
    args = parser.parse_args()
    
    # Display header
    print(f"\n{Colors.HEADER}===== GitHub Project Field Detector ====={Colors.ENDC}")
    
    try:
        # Load configuration
        log(f"Loading configuration from {args.config_dir}")
        config = load_config(args.config_dir)
        github_token = config['github_token']
        
        # Get project fields
        project_data = get_project_fields(github_token, args.project_id)
        
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
            print(f"\n{Colors.HEADER}Sample Configuration:{Colors.ENDC}")
            print(f"""
# Add to your .pruner.config file:
custom_fields:
  workstream_field_id: "{workstream_field['name']}"
  status_field_id: "Status"  # Adjust based on your project
  done_status_value: "Done"  # Adjust based on your project
""")
        else:
            print(f"  {Colors.YELLOW}No dedicated Workstream field found.{Colors.ENDC}")
            print("  You'll need to identify which field represents workstreams in your project")
            print("  and update your .pruner.config accordingly.")
        
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