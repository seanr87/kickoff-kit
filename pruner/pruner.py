#!/usr/bin/env python3
"""
pruner.py - GitHub Project Board Manager

This script automatically manages GitHub Project boards by labeling — not deleting — 
old, irrelevant, or non-actionable Issues to keep boards clean and focused.
"""

import argparse
from pathlib import Path
import yaml
import sys
import os
import time
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("pruner")

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

def load_config(config_dir: str) -> Dict[str, Any]:
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

def load_pruner_config(config_path: str) -> Dict[str, Any]:
    """Load pruner configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        required_keys = ["project_id", "done_age_days", "done_overflow_limit"]
        for key in required_keys:
            if key not in config:
                log(f"Required key '{key}' not found in pruner config", "ERROR")
                sys.exit(1)
                
        return config
    except Exception as e:
        log(f"Failed to load pruner config: {str(e)}", "ERROR")
        sys.exit(1)

def get_project_fields(github_token: str, project_id: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Get project field information including custom fields using GitHub's GraphQL API
    
    Returns:
        Tuple containing:
        - dict mapping field names to their details
        - list of all workstream options
    """
    import requests
    
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
    
    # Extract field information
    project_data = data["data"]["node"]
    fields = {}
    workstream_options = []
    
    for field in project_data["fields"]["nodes"]:
        fields[field["name"]] = field
        
        # If this is a single select field with options, store the options
        if "options" in field:
            if field["name"].lower() == "workstream":
                workstream_options = [option["name"] for option in field["options"]]
    
    log(f"Found {len(fields)} fields in project")
    log(f"Project URL: {project_data['url']}")
    
    return fields, workstream_options

def get_project_issues(github_token: str, project_id: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all issues from a project with their metadata including custom fields
    """
    import requests
    
    log(f"Fetching issues for project ID: {project_id}")
    
    # Get project fields
    fields, workstream_options = get_project_fields(github_token, project_id)
    
    # Extract field IDs from the field map
    workstream_field = None
    status_field = None
    
    # Find the workstream and status fields
    workstream_field_id = config.get("custom_fields", {}).get("workstream_field_id", "Workstream")
    status_field_id = config.get("custom_fields", {}).get("status_field_id", "Status")
    
    for name, field in fields.items():
        if name.lower() == workstream_field_id.lower():
            workstream_field = field
        if name.lower() == status_field_id.lower():
            status_field = field
    
    # Log field information for debugging
    if config.get("verbose", False):
        log(f"Workstream field: {workstream_field['name'] if workstream_field else 'Not found'}")
        log(f"Status field: {status_field['name'] if status_field else 'Not found'}")
        log(f"Workstream options: {', '.join(workstream_options)}")
    
    # GraphQL query to get project issues with custom field values
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              content {
                ... on Issue {
                  id
                  number
                  title
                  state
                  stateReason
                  updatedAt
                  labels(first: 10) {
                    nodes {
                      name
                    }
                  }
                  repository {
                    name
                    owner {
                      login
                    }
                  }
                }
              }
              fieldValues(first: 20) {
                nodes {
                  ... on ProjectV2ItemFieldTextValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    text
                  }
                  ... on ProjectV2ItemFieldDateValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    date
                  }
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    # Make the API request with pagination
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    issues = []
    has_next_page = True
    cursor = None
    
    while has_next_page:
        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={"query": query, "variables": {"projectId": project_id, "cursor": cursor}}
        )
        
        if response.status_code != 200:
            log(f"Failed to fetch project issues: {response.text}", "ERROR")
            sys.exit(1)
            
        data = response.json()
        
        if "errors" in data:
            log(f"GraphQL errors: {data['errors']}", "ERROR")
            sys.exit(1)
        
        # Process issues
        items = data["data"]["node"]["items"]
        
        for item in items["nodes"]:
            # Skip non-issue items
            if not item["content"] or item["content"].get("__typename") != "Issue":
                continue
                
            issue = item["content"]
            
            # Extract custom field values
            field_values = {}
            for field_value in item["fieldValues"]["nodes"]:
                if field_value.get("field") and field_value["field"].get("name"):
                    field_name = field_value["field"]["name"]
                    field_values[field_name] = field_value.get("text") or field_value.get("date") or field_value.get("name")
            
            # Get workstream and status values
            workstream = field_values.get(workstream_field_id, "Unknown")
            status = field_values.get(status_field_id, "Unknown")
            
            # Build issue object
            issue_obj = {
                "number": issue["number"],
                "title": issue["title"],
                "status": status,
                "workstream": workstream,
                "closed": issue["state"] == "CLOSED",
                "closed_reason": issue["stateReason"],
                "updated_at": issue["updatedAt"],
                "labels": [label["name"] for label in issue["labels"]["nodes"]],
                "repository": f"{issue['repository']['owner']['login']}/{issue['repository']['name']}"
            }
            
            issues.append(issue_obj)
        
        # Check for next page
        has_next_page = items["pageInfo"]["hasNextPage"]
        cursor = items["pageInfo"]["endCursor"] if has_next_page else None
    
    log(f"Found {len(issues)} issues in project")
    return issues

def apply_label(github_token: str, repo_owner: str, repo_name: str, issue_number: int, label: str) -> bool:
    """Add a label to an issue"""
    import requests
    
    log(f"Applying label '{label}' to issue #{issue_number} in {repo_owner}/{repo_name}")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Try to add the label
    try:
        response = requests.post(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}/labels",
            headers=headers,
            json={"labels": [label]}
        )
        
        if response.status_code == 404:
            # Label might not exist, try to create it
            color = "808080" if label == "Archive" else "ff0000"  # Gray for Archive, Red for Not Planned
            
            create_response = requests.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/labels",
                headers=headers,
                json={"name": label, "color": color}
            )
            
            if create_response.status_code not in [201, 422]:  # 422 means label already exists
                log(f"Failed to create label: {create_response.text}", "ERROR")
                return False
                
            # Try adding the label again
            response = requests.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}/labels",
                headers=headers,
                json={"labels": [label]}
            )
        
        if response.status_code not in [200, 201]:
            log(f"Failed to apply label: {response.text}", "ERROR")
            return False
            
        return True
    except Exception as e:
        log(f"Error applying label: {str(e)}", "ERROR")
        return False

def update_audit_log(github_token: str, repo_owner: str, repo_name: str, wiki_page_name: str, actions: List[Dict[str, Any]]) -> bool:
    """Update the audit log wiki page"""
    import requests
    from base64 import b64encode, b64decode
    
    if not actions:
        log("No actions to log", "INFO")
        return True
        
    log(f"Updating audit log on wiki page: {wiki_page_name}")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # First try to get the existing page
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{wiki_page_name}.md",
            headers=headers
        )
        
        if response.status_code == 200:
            # Page exists, update it
            page_data = response.json()
            existing_content = b64decode(page_data["content"]).decode("utf-8")
            sha = page_data["sha"]
            
            # Append new actions
            new_content = existing_content + f"\n\n## Pruner Actions - {datetime.now().strftime('%Y-%m-%d')}\n\n"
            
            for action in actions:
                new_content += f"- Issue #{action['issue']} in {action['repository']}: {action['action']} - {action['reason']} ({action['timestamp']})\n"
                
            # Update the page
            update_response = requests.put(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{wiki_page_name}.md",
                headers=headers,
                json={
                    "message": "Update Pruner audit log",
                    "content": b64encode(new_content.encode("utf-8")).decode("utf-8"),
                    "sha": sha
                }
            )
            
            if update_response.status_code != 200:
                log(f"Failed to update wiki page: {update_response.text}", "ERROR")
                return False
                
            log("Audit log updated successfully", "SUCCESS")
            return True
        elif response.status_code == 404:
            # Page doesn't exist, create it
            new_content = f"# {wiki_page_name}\n\nThis page automatically tracks actions taken by the Pruner tool.\n\n"
            new_content += f"## Pruner Actions - {datetime.now().strftime('%Y-%m-%d')}\n\n"
            
            for action in actions:
                new_content += f"- Issue #{action['issue']} in {action['repository']}: {action['action']} - {action['reason']} ({action['timestamp']})\n"
                
            create_response = requests.put(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{wiki_page_name}.md",
                headers=headers,
                json={
                    "message": "Create Pruner audit log",
                    "content": b64encode(new_content.encode("utf-8")).decode("utf-8")
                }
            )
            
            if create_response.status_code != 201:
                log(f"Failed to create wiki page: {create_response.text}", "ERROR")
                return False
                
            log("Audit log created successfully", "SUCCESS")
            return True
        else:
            log(f"Failed to access wiki page: {response.text}", "ERROR")
            return False
    except Exception as e:
        log(f"Error updating audit log: {str(e)}", "ERROR")
        return False

def run_pruner(config: Dict[str, Any], github_token: str) -> Dict[str, Any]:
    """Run the pruner with the provided configuration"""
    
    # Initialize result
    result = {
        "success": False,
        "not_planned_count": 0,
        "archived_count": 0,
        "total_processed": 0,
        "error": None
    }
    
    try:
        # Validate required configuration
        required_keys = ["project_id", "done_age_days", "done_overflow_limit"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration: {key}")
                
        # Extract repository from configuration or use default
        repo_parts = config.get("repository", "").split("/")
        repo_owner = repo_parts[0] if len(repo_parts) > 1 else None
        repo_name = repo_parts[1] if len(repo_parts) > 1 else None
        
        # Get issues from project
        issues = get_project_issues(github_token, config["project_id"], config)
        result["total_processed"] = len(issues)
        
        # Initialize list for audit log actions
        actions = []
        
        # Process not planned issues
        if not config.get("dry_run", False):
            # Find not planned issues
            not_planned_issues = [
                issue for issue in issues
                if issue["closed"] and issue["closed_reason"] == "not_planned"
            ]
            
            result["not_planned_count"] = len(not_planned_issues)
            log(f"Found {len(not_planned_issues)} issues to label as 'Not Planned'")
            
            # Apply labels
            for issue in not_planned_issues:
                # Extract repository owner and name
                repo_parts = issue["repository"].split("/")
                owner = repo_parts[0]
                repo = repo_parts[1]
                
                # Apply the label
                if apply_label(github_token, owner, repo, issue["number"], "Not Planned"):
                    actions.append({
                        "issue": issue["number"],
                        "repository": issue["repository"],
                        "action": "Applied label: Not Planned",
                        "reason": 'Closed with reason "not planned"',
                        "timestamp": datetime.now().isoformat()
                    })
            
            # Find issues that have been in Done status for too long
            done_status_value = config.get("custom_fields", {}).get("done_status_value", "Done")
            threshold_date = datetime.now() - timedelta(days=config["done_age_days"])
            
            old_done_issues = [
                issue for issue in issues
                if issue["status"] == done_status_value and 
                   datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00")) < threshold_date
            ]
            
            log(f"Found {len(old_done_issues)} issues to archive (Done for {config['done_age_days']}+ days)")
            
            # Apply labels to old done issues
            for issue in old_done_issues:
                repo_parts = issue["repository"].split("/")
                owner = repo_parts[0]
                repo = repo_parts[1]
                
                if apply_label(github_token, owner, repo, issue["number"], "Archive"):
                    actions.append({
                        "issue": issue["number"],
                        "repository": issue["repository"],
                        "action": "Applied label: Archive",
                        "reason": f"In '{done_status_value}' status for more than {config['done_age_days']} days",
                        "timestamp": datetime.now().isoformat()
                    })
                    result["archived_count"] += 1
            
            # Group issues by workstream
            workstream_groups = {}
            for issue in issues:
                if issue["status"] == done_status_value and issue["workstream"]:
                    if issue["workstream"] not in workstream_groups:
                        workstream_groups[issue["workstream"]] = []
                    
                    workstream_groups[issue["workstream"]].append(issue)
            
            # Process each workstream for overflow
            for workstream, workstream_issues in workstream_groups.items():
                if len(workstream_issues) > config["done_overflow_limit"]:
                    # Sort by updated date (oldest first)
                    workstream_issues.sort(key=lambda x: x["updated_at"])
                    
                    # Get issues to archive (beyond the limit)
                    overflow_count = len(workstream_issues) - config["done_overflow_limit"]
                    to_archive = workstream_issues[:overflow_count]
                    
                    log(f"Found {len(to_archive)} overflow issues to archive in workstream: {workstream}")
                    
                    # Apply labels
                    for issue in to_archive:
                        repo_parts = issue["repository"].split("/")
                        owner = repo_parts[0]
                        repo = repo_parts[1]
                        
                        if apply_label(github_token, owner, repo, issue["number"], "Archive"):
                            actions.append({
                                "issue": issue["number"],
                                "repository": issue["repository"],
                                "action": "Applied label: Archive",
                                "reason": f"Overflow in '{done_status_value}' status for workstream '{workstream}'",
                                "timestamp": datetime.now().isoformat()
                            })
                            result["archived_count"] += 1
            
            # Update audit log if there are any actions
            if actions and config.get("wiki_page_name"):
                update_audit_log(
                    github_token,
                    repo_owner or actions[0]["repository"].split("/")[0],
                    repo_name or actions[0]["repository"].split("/")[1],
                    config["wiki_page_name"],
                    actions
                )
        else:
            # Dry run mode - just count what would be done
            not_planned_issues = [
                issue for issue in issues
                if issue["closed"] and issue["closed_reason"] == "not_planned"
            ]
            result["not_planned_count"] = len(not_planned_issues)
            
            done_status_value = config.get("custom_fields", {}).get("done_status_value", "Done")
            threshold_date = datetime.now() - timedelta(days=config["done_age_days"])
            
            old_done_issues = [
                issue for issue in issues
                if issue["status"] == done_status_value and 
                   datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00")) < threshold_date
            ]
            
            # Count overflow issues per workstream
            overflow_count = 0
            workstream_groups = {}
            
            for issue in issues:
                if issue["status"] == done_status_value and issue["workstream"]:
                    if issue["workstream"] not in workstream_groups:
                        workstream_groups[issue["workstream"]] = []
                    
                    workstream_groups[issue["workstream"]].append(issue)
            
            for workstream, workstream_issues in workstream_groups.items():
                if len(workstream_issues) > config["done_overflow_limit"]:
                    overflow_count += len(workstream_issues) - config["done_overflow_limit"]
                    log(f"DRY RUN: Would label {len(workstream_issues) - config['done_overflow_limit']} issues as 'Archive' in workstream '{workstream}' (overflow)")
            
            result["archived_count"] = len(old_done_issues) + overflow_count
            
            log(f"DRY RUN: Would label {result['not_planned_count']} issues as 'Not Planned'")
            log(f"DRY RUN: Would label {len(old_done_issues)} issues as 'Archive' (Done for {config['done_age_days']}+ days)")
            log(f"DRY RUN: Would label {overflow_count} issues as 'Archive' (overflow)")
            log(f"DRY RUN: Total issues that would be labeled: {result['not_planned_count'] + result['archived_count']}")
        
        # Mark as successful
        result["success"] = True
        
    except Exception as e:
        log(f"Pruner failed: {str(e)}", "ERROR")
        result["success"] = False
        result["error"] = str(e)
        
    return result

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automatically manage GitHub Project boards by labeling issues")
    parser.add_argument("--config-dir", required=True, help="Directory containing secrets.yaml file")
    parser.add_argument("--pruner-config", required=True, help="Path to pruner configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Run without applying labels")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logging information")
    args = parser.parse_args()
    
    # Display header
    print(f"\n{Colors.HEADER}===== Pruner - GitHub Project Manager ====={Colors.ENDC}")
    log("Starting pruner process...")
    
    try:
        # Load configurations
        log(f"Loading configuration from {args.config_dir}")
        secrets = load_config(args.config_dir)
        github_token = secrets["github_token"]
        
        log(f"Loading pruner config from {args.pruner_config}")
        config = load_pruner_config(args.pruner_config)
        
        # Override dry run if specified on command line
        if args.dry_run:
            config["dry_run"] = True
            log("Dry run mode enabled via command line", "WARNING")
        
        # Enable verbose logging if specified
        if args.verbose:
            config["verbose"] = True
            log("Verbose logging enabled", "INFO")
        
        # Run the pruner
        log(f"Running pruner for project ID: {config['project_id']}")
        result = run_pruner(config, github_token)
        
        # Display results
        if result["success"]:
            log("Pruner completed successfully!", "SUCCESS")
            log(f"Labeled {result['not_planned_count']} issues as \"Not Planned\"", "INFO")
            log(f"Labeled {result['archived_count']} issues as \"Archive\"", "INFO")
            log(f"Total issues processed: {result['total_processed']}", "INFO")
        else:
            log(f"Pruner failed: {result['error']}", "ERROR")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n")
        log("Process interrupted by user. Exiting.", "WARNING")
        sys.exit(0)
    except Exception as e:
        log(f"Unexpected error: {str(e)}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()