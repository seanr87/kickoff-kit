#!/usr/bin/env python3
"""
pruner.py - GitHub Project Board Manager (Simplified & Automated)

This script automatically manages GitHub Project boards by labeling — not deleting — 
old, irrelevant, or non-actionable Issues to keep boards clean and focused.
"""

import argparse
from pathlib import Path
import yaml
import sys
import os
import time
import json
from datetime import datetime, timedelta
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime, timedelta, timezone

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

def find_parent_config_files():
    """
    Find the config.yaml and secrets.yaml files in the parent directory of kickoff-kit
    Returns tuple (config_path, secrets_path)
    """
    # Get the current script path
    current_path = Path(__file__).resolve()
    
    # Navigate to the kickoff-kit directory (parent of the pruner directory)
    kickoff_kit_dir = current_path.parent.parent
    
    # The parent directory of kickoff-kit should contain config files
    parent_dir = kickoff_kit_dir.parent
    
    config_path = parent_dir / "config.yaml"
    secrets_path = parent_dir / "secrets.yaml"
    
    log(f"Looking for configuration in: {parent_dir}")
    
    if not config_path.exists():
        log(f"Config file not found: {config_path}", "ERROR")
        return None, None
        
    if not secrets_path.exists():
        log(f"Secrets file not found: {secrets_path}", "WARNING")
        
    return config_path, secrets_path

def load_config_files():
    """
    Load configuration from config.yaml and secrets.yaml
    Returns dict with combined configuration
    """
    config_path, secrets_path = find_parent_config_files()
    
    if not config_path:
        log("Configuration files not found. Please ensure config.yaml exists in the parent directory of kickoff-kit.", "ERROR")
        sys.exit(1)
    
    # Load config.yaml
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            log(f"Loaded configuration from {config_path}")
    except Exception as e:
        log(f"Error loading config file: {str(e)}", "ERROR")
        sys.exit(1)
    
    # Load secrets.yaml if it exists
    github_token = None
    if secrets_path and secrets_path.exists():
        try:
            with open(secrets_path, 'r') as f:
                secrets = yaml.safe_load(f)
                if 'github_token' in secrets:
                    github_token = secrets['github_token']
                    log(f"Loaded GitHub token from {secrets_path}")
                else:
                    log(f"GitHub token not found in {secrets_path}", "WARNING")
        except Exception as e:
            log(f"Error loading secrets file: {str(e)}", "WARNING")
    
    # Check if pruner configuration exists
    if 'pruner' not in config:
        log("No 'pruner' section found in config.yaml. Please add pruner configuration to your config.yaml file.", "ERROR")
        sys.exit(1)
    
    # Get repository details
    repository = get_repository_from_config(config)
    
    # Return combined configuration
    return {
        "github_token": github_token,
        "config": config,
        "pruner_config": config.get('pruner', {}),
        "repository": repository
    }

def get_repository_from_config(config):
    """
    Extract repository information from config
    Returns "owner/repo" string
    """
    # First check if directly specified in pruner config
    if 'pruner' in config and 'repository' in config['pruner']:
        return config['pruner']['repository']
    
    # Try to infer from other parts of config
    if 'create_project' in config and 'repo' in config['create_project']:
        return config['create_project']['repo']
    
    # Default to current repo from git
    return get_current_repo()

def get_current_repo():
    """
    Get the current repository name from git config
    Returns tuple (owner/repo) or None if not in a git repo
    """
    try:
        # Get remote URL of origin
        stream = os.popen('git config --get remote.origin.url')
        url = stream.read().strip()
        
        # Parse the URL to extract owner and repo
        # Handle different URL formats:
        # - HTTPS: https://github.com/owner/repo.git
        # - SSH: git@github.com:owner/repo.git
        if "github.com" in url:
            if url.startswith("https://"):
                pattern = r"https://github\.com/([^/]+)/([^/.]+)(\.git)?"
            else:  # SSH format
                pattern = r"git@github\.com:([^/]+)/([^/.]+)(\.git)?"
                
            match = re.match(pattern, url)
            if match:
                owner, repo = match.groups()[0:2]
                return f"{owner}/{repo}"
    except Exception as e:
        log(f"Error detecting repository: {str(e)}", "WARNING")
    
    return None

def get_github_token():
    """
    Get GitHub token from environment or secrets.yaml
    """
    # First check if already loaded from secrets
    if 'github_token' in os.environ:
        return os.environ["GITHUB_TOKEN"]
    
    # Try to get from environment variable
    if "GITHUB_TOKEN" in os.environ:
        return os.environ["GITHUB_TOKEN"]
    
    # If not found, try to get from secrets.yaml
    _, secrets_path = find_parent_config_files()
    if secrets_path and secrets_path.exists():
        try:
            with open(secrets_path, 'r') as f:
                secrets = yaml.safe_load(f)
                if 'github_token' in secrets:
                    return secrets['github_token']
        except Exception:
            pass
    
    return None

def detect_github_projects(token, owner, repo_name=None):
    """
    Detect GitHub Projects for the current user/organization and repository
    Returns a list of (project_id, title, number, url) tuples
    
    If repo_name is provided, filter projects to only those associated with the repository
    """
    log(f"Detecting GitHub Projects for {owner}")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # First try to find projects directly linked to the repository
    if repo_name:
        log(f"Looking for projects linked to {owner}/{repo_name}")
        repo_query = """
        {
          repository(owner: "%s", name: "%s") {
            projectsV2(first: 20) {
              nodes {
                id
                title
                number
                url
              }
            }
          }
        }
        """ % (owner, repo_name)
        
        try:
            response = requests.post(
                "https://api.github.com/graphql",
                headers=headers,
                json={"query": repo_query}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "repository" in data["data"] and "projectsV2" in data["data"]["repository"]:
                    projects = data["data"]["repository"]["projectsV2"]["nodes"]
                    if projects:
                        # Format projects for selection
                        project_list = []
                        for project in projects:
                            project_list.append((project["id"], project["title"], project["number"], project["url"]))
                        
                        log(f"Found {len(project_list)} projects linked to repository {owner}/{repo_name}")
                        return project_list
        except Exception as e:
            log(f"Error checking repository projects: {str(e)}", "WARNING")
    
    # If no projects found for the repository (or no repo specified), try user projects
    log(f"Looking for user projects for {owner}")
    user_query = """
    {
      user(login: "%s") {
        projectsV2(first: 20) {
          nodes {
            id
            title
            number
            url
          }
        }
      }
    }
    """ % owner
    
    # Make the API request
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={"query": user_query}
        )
        
        if response.status_code != 200:
            log(f"Failed to fetch user projects: {response.text}", "WARNING")
            # Try organization projects instead
            org_query = """
            {
              organization(login: "%s") {
                projectsV2(first: 20) {
                  nodes {
                    id
                    title
                    number
                    url
                  }
                }
              }
            }
            """ % owner
            
            response = requests.post(
                "https://api.github.com/graphql",
                headers=headers,
                json={"query": org_query}
            )
            
            if response.status_code != 200:
                log(f"Failed to fetch organization projects: {response.text}", "ERROR")
                return []
                
            data = response.json()
            
            if "errors" in data:
                log(f"GraphQL errors: {data['errors']}", "ERROR")
                return []
                
            projects = data["data"]["organization"]["projectsV2"]["nodes"]
        else:
            data = response.json()
            
            if "errors" in data:
                log(f"GraphQL errors: {data['errors']}", "ERROR")
                return []
                
            projects = data["data"]["user"]["projectsV2"]["nodes"]
        
        # Format projects for selection
        project_list = []
        for project in projects:
            project_list.append((project["id"], project["title"], project["number"], project["url"]))
            
        log(f"Found {len(project_list)} projects for {owner}")
        return project_list
        
    except Exception as e:
        log(f"Error detecting projects: {str(e)}", "ERROR")
        return []

def get_project_fields(github_token: str, project_id: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Get project field information including custom fields using GitHub's GraphQL API
    
    Returns:
        Tuple containing:
        - dict mapping field names to their details
        - list of all workstream options
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
            if not item["content"] or "number" not in item["content"]:
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

def apply_view_filters(github_token: str, project_id: str, view_id: str, view_number: int, view_name: str) -> bool:
    """
    Apply filters to a GitHub Project view to hide archived and not planned issues
    
    Args:
        github_token: GitHub token with repo and project access
        project_id: ID of the GitHub Project
        view_id: ID of the view to apply filters to
        view_number: Number of the view
        view_name: Name of the view (for logging)
        
    Returns:
        True if filters were applied successfully, False otherwise
    """
    log(f"Applying filters to view: {view_name} (Number: {view_number})")
    
    # GitHub GraphQL mutation to update view filters
    mutation = """
    mutation($projectId: ID!, $viewNumber: Int!, $filter: String!) {
      updateProjectV2View(
        input: {
          projectId: $projectId,
          number: $viewNumber,
          filter: $filter
        }
      ) {
        clientMutationId
      }
    }
    """
    
    # Define filter to hide issues with labels "Archive" or "Not Planned"
    # Note: Filters in GitHub Projects use a specific syntax similar to search
    filter_string = """
    -label:"Archive" -label:"Not Planned"
    """
    
    # Make the API request
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={
                "query": mutation, 
                "variables": {
                    "projectId": project_id,
                    "viewNumber": view_number,
                    "filter": filter_string.strip()
                }
            }
        )
        
        if response.status_code != 200:
            log(f"Failed to apply filters to view: {response.text}", "ERROR")
            return False
            
        data = response.json()
        
        if "errors" in data:
            log(f"GraphQL errors applying filters: {data['errors']}", "ERROR")
            return False
        
        log(f"Successfully applied filters to view: {view_name}", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"Error applying filters to view: {str(e)}", "ERROR")
        return False
    
def get_project_views(github_token: str, project_id: str) -> List[Dict[str, Any]]:
    """
    Get all views (lists/boards/etc) for a GitHub Project using the GraphQL API
    
    Returns a list of view objects with id, title, number, and layout info
    """
    log(f"Fetching views for project ID: {project_id}")
    
    # GraphQL query to get project views
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          views(first: 20) {
            nodes {
              id
              name
              number
              layout
              filter
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
        log(f"Failed to fetch project views: {response.text}", "ERROR")
        return []
        
    data = response.json()
    
    if "errors" in data:
        log(f"GraphQL errors: {data['errors']}", "ERROR")
        return []
    
    # Extract view information
    views = data["data"]["node"]["views"]["nodes"]
    
    # Format layout types for better display
    for view in views:
        layout_type = view.get("layout", "")
        if layout_type.startswith("PROJECT_V2_VIEW_LAYOUT_"):
            view["layout_type"] = layout_type.replace("PROJECT_V2_VIEW_LAYOUT_", "").replace("_", " ").title()
        else:
            view["layout_type"] = layout_type
    
    log(f"Found {len(views)} views in project")
    return views

def select_project_views(views: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Present views to the user and allow them to select which ones to apply filters to
    
    Returns a list of selected view objects with id, name, number, and layout info
    """
    if not views:
        log("No views found in the project", "WARNING")
        return []
    
    log("\n=== Available Project Views ===", "INFO")
    for i, view in enumerate(views, 1):
        layout_type = view.get("layout_type", "Unknown")
        log(f"{i}. {view['name']} ({layout_type})", "INFO")
    
    log("\nSelect views to apply filters to (comma-separated numbers, or 'all' for all views):", "PROMPT")
    selection = input("> ").strip().lower()
    
    selected_views = []
    
    if selection == "all":
        selected_views = views
        log(f"Selected all {len(views)} views", "SUCCESS")
    else:
        try:
            # Parse the selection
            indices = [int(idx.strip()) for idx in selection.split(",") if idx.strip()]
            
            # Validate indices
            valid_indices = [idx for idx in indices if 1 <= idx <= len(views)]
            
            if not valid_indices:
                log("No valid selections. Using all views by default.", "WARNING")
                selected_views = views
            else:
                # Get the selected views
                selected_views = [views[idx - 1] for idx in valid_indices]
                selected_names = [view["name"] for view in selected_views]
                log(f"Selected views: {', '.join(selected_names)}", "SUCCESS")
        except ValueError:
            log("Invalid selection format. Using all views by default.", "WARNING")
            selected_views = views
    
    return selected_views

def get_project_issues_by_views(github_token: str, project_id: str, config: Dict[str, Any], 
                               view_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Get all issues from specific views in a GitHub Project
    
    Args:
        github_token: GitHub token with repo and project access
        project_id: ID of the GitHub Project
        config: Pruner configuration dictionary
        view_ids: List of view IDs to get issues from
        
    Returns:
        List of issue objects with metadata
    """
    log(f"Fetching issues from {len(view_ids)} selected views")
    
    # Get project fields info
    fields, workstream_options = get_project_fields(github_token, project_id)
    
    # Extract field IDs needed for processing
    workstream_field_id = config.get("custom_fields", {}).get("workstream_field_id", "Workstream")
    status_field_id = config.get("custom_fields", {}).get("status_field_id", "Status")
    
    # Get all project views to map IDs to numbers
    all_views = get_project_views(github_token, project_id)
    view_id_to_number = {}
    view_id_to_name = {}
    
    for view in all_views:
        if "id" in view:
            # Create mapping from ID to view number and name
            view_id_to_number[view["id"]] = view.get("number")
            view_id_to_name[view["id"]] = view.get("name", "Unknown View")
    
    # Store all issues with issue number as key to prevent duplicates
    all_issues = []
    
    for view_id in view_ids:
        # Get the view name and number for this view ID
        view_name = view_id_to_name.get(view_id, "Selected View")
        view_number = view_id_to_number.get(view_id)
        
        if not view_number:
            log(f"Could not find view number for view ID: {view_id}", "ERROR")
            continue
            
        log(f"Fetching issues from view: {view_name}")
        
        # GraphQL query for items in a specific view
        # We need to query by view number, not ID
        query = """
        query($projectId: ID!, $viewNumber: Int!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              view(number: $viewNumber) {
                name
              }
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
        
        # Process each view with pagination
        has_next_page = True
        cursor = None
        view_issues = []
        
        while has_next_page:
            # Make the API request
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.post(
                "https://api.github.com/graphql",
                headers=headers,
                json={"query": query, "variables": {
                    "projectId": project_id, 
                    "viewNumber": view_number,
                    "cursor": cursor
                }}
            )
            
            if response.status_code != 200:
                log(f"Failed to fetch view items: {response.text}", "ERROR")
                break
                
            data = response.json()
            
            if "errors" in data:
                log(f"GraphQL errors: {data['errors']}", "ERROR")
                break
            
            # Check if we got valid data
            if "data" not in data or "node" not in data["data"]:
                log(f"Invalid response format for view {view_name}", "ERROR")
                break
                
            # Get items in this page
            items_data = data["data"]["node"]["items"]
            
            # Process items
            page_count = 0
            for item in items_data["nodes"]:
                # Skip non-issue items
                if not item["content"] or "number" not in item["content"]:
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
                    "repository": f"{issue['repository']['owner']['login']}/{issue['repository']['name']}",
                    "view_name": view_name  # Add the view name for reference
                }
                
                view_issues.append(issue_obj)
                page_count += 1
            
            # Update counters and check for next page
            has_next_page = items_data["pageInfo"]["hasNextPage"]
            cursor = items_data["pageInfo"]["endCursor"] if has_next_page else None
        
        log(f"Found {len(view_issues)} issues in view: {view_name}")
        all_issues.extend(view_issues)
    
    # Remove duplicates (same issue might appear in multiple views)
    unique_issues = {}
    for issue in all_issues:
        key = f"{issue['repository']}#{issue['number']}"
        if key not in unique_issues:
            unique_issues[key] = issue
    
    issues = list(unique_issues.values())
    log(f"Total unique issues across selected views: {len(issues)}")
    return issues

def run_pruner(config: Dict[str, Any], github_token: str, target_repository: str) -> Dict[str, Any]:
    """Run the pruner with the provided configuration"""
    
    # Initialize result
    result = {
        "success": False,
        "not_planned_count": 0,
        "archived_count": 0,
        "total_processed": 0,
        "error": None,
        "views_processed": []
    }
    
    try:
        # Validate required configuration
        required_keys = ["project_id", "done_age_days", "done_overflow_limit"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")
        
        # Extract repository parts
        repo_parts = target_repository.split("/")
        if len(repo_parts) != 2:
            raise ValueError(f"Invalid repository format: {target_repository}. Expected 'owner/repo'")
            
        repo_owner, repo_name = repo_parts
        
        # Check if specific views are selected
        selected_views = config.get("selected_views", [])
        if selected_views:
            view_names = [view.get("name", "Unknown") for view in selected_views]
            log(f"Applying filters to {len(selected_views)} selected views: {', '.join(view_names)}", "INFO")
            
            # Track which views we've processed
            result["views_processed"] = view_names
            
            # Get view IDs
            view_ids = [view.get("id") for view in selected_views if "id" in view]
            
            # Get issues from project, filtered by views
            issues = get_project_issues_by_views(github_token, config["project_id"], config, view_ids)
        else:
            log("No specific views selected, applying filters to all issues", "INFO")
            # Get all issues from project
            issues = get_project_issues(github_token, config["project_id"], config)
        
        result["total_processed"] = len(issues)
        
        # Filter issues to the target repository if specified
        if target_repository:
            issues = [issue for issue in issues if issue["repository"] == target_repository]
            log(f"Filtered to {len(issues)} issues from repository {target_repository}")
        
        # Process not planned issues
        not_planned_issues = [
            issue for issue in issues
            if issue["closed"] and issue["closed_reason"] == "not_planned"
        ]
        
        result["not_planned_count"] = len(not_planned_issues)
        log(f"Found {len(not_planned_issues)} issues to label as 'Not Planned'")
        
        # Apply labels if not in dry run mode
        actions = []  # For audit log
        
        if not config.get("dry_run", False):
            for issue in not_planned_issues:
                # Apply label
                success = apply_label(github_token, repo_owner, repo_name, issue["number"], "Not Planned")
                
                if success:
                    # Record action for audit log
                    actions.append({
                        "issue": issue["number"],
                        "repository": issue["repository"],
                        "action": "Applied label 'Not Planned'",
                        "reason": "Issue was closed as not planned",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        # Find issues that have been in Done status for too long
        done_status_value = config.get("custom_fields", {}).get("done_status_value", "Done")
        threshold_date = datetime.now(timezone.utc) - timedelta(days=config["done_age_days"])
        
        old_done_issues = []
        for issue in issues:
            if issue["status"] == done_status_value:
                # Parse the updated_at date with timezone awareness
                updated_at = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
                
                # Now both dates have timezone info and can be compared safely
                if updated_at < threshold_date:
                    old_done_issues.append(issue)
        
        log(f"Found {len(old_done_issues)} issues to archive (Done for {config['done_age_days']}+ days)")
        
        # Apply labels if not in dry run mode
        if not config.get("dry_run", False):
            for issue in old_done_issues:
                # Apply label
                success = apply_label(github_token, repo_owner, repo_name, issue["number"], "Archive")
                
                if success:
                    # Record action for audit log
                    actions.append({
                        "issue": issue["number"],
                        "repository": issue["repository"],
                        "action": "Applied label 'Archive'",
                        "reason": f"Issue was in Done status for over {config['done_age_days']} days",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        # Find overflow issues in Done status per workstream
        workstream_counts = {}
        workstream_issues = {}
        
        # Get all issues in Done status by workstream
        for issue in issues:
            if issue["status"] == done_status_value:
                workstream = issue["workstream"]
                
                if workstream not in workstream_counts:
                    workstream_counts[workstream] = 0
                    workstream_issues[workstream] = []
                
                workstream_counts[workstream] += 1
                workstream_issues[workstream].append(issue)
        
        # Sort issues by updated_at date (oldest first)
        for workstream in workstream_issues:
            workstream_issues[workstream].sort(key=lambda x: datetime.fromisoformat(x["updated_at"].replace("Z", "+00:00")))
        
        # Find overflow issues
        overflow_limit = config["done_overflow_limit"]
        overflow_issues = []
        
        for workstream, count in workstream_counts.items():
            if count > overflow_limit:
                # Get the oldest issues beyond the limit
                overflow = workstream_issues[workstream][:(count - overflow_limit)]
                overflow_issues.extend(overflow)
        
        log(f"Found {len(overflow_issues)} overflow issues in Done status to archive")
        
        # Apply labels if not in dry run mode
        if not config.get("dry_run", False):
            for issue in overflow_issues:
                # Apply label
                success = apply_label(github_token, repo_owner, repo_name, issue["number"], "Archive")
                
                if success:
                    # Record action for audit log
                    actions.append({
                        "issue": issue["number"],
                        "repository": issue["repository"],
                        "action": "Applied label 'Archive'",
                        "reason": f"Overflow: More than {overflow_limit} issues in Done status for workstream '{issue['workstream']}'",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        # Update the result
        result["archived_count"] = len(old_done_issues) + len(overflow_issues)
        
        # Update audit log if not in dry run mode and there are actions
        if not config.get("dry_run", False) and actions:
            wiki_page_name = config.get("wiki_page_name", ".github/PRUNER_LOG.md")
            update_audit_log(github_token, repo_owner, repo_name, wiki_page_name, actions)
        
        result["success"] = True
        return result
    except Exception as e:
        import traceback
        log(f"Error in run_pruner: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        result["error"] = str(e)
        return result

def setup_pruner():
    """
    Interactive setup process for pruner
    Updates config.yaml in the parent directory
    """
    log("Starting pruner setup...")
    
    # Load existing configuration
    config_data = load_config_files()
    github_token = config_data.get("github_token") or get_github_token()
    
    if not github_token:
        log("GitHub token not found. Please provide a personal access token:", "PROMPT")
        github_token = input("> ").strip()
        
        # Save token to secrets.yaml in parent directory
        _, secrets_path = find_parent_config_files()
        if secrets_path:
            # Create secrets.yaml if it doesn't exist
            with open(secrets_path, 'w') as f:
                yaml.dump({"github_token": github_token}, f, default_flow_style=False)
            log(f"GitHub token saved to {secrets_path}", "SUCCESS")
    
    # Get target repository
    target_repository = config_data.get("repository")
    if not target_repository:
        log("Repository not specified in configuration. Please provide owner and name:", "PROMPT")
        repo_owner = input("Owner (username or organization): ").strip()
        repo_name = input("Repository name: ").strip()
        target_repository = f"{repo_owner}/{repo_name}"
    
    # Extract owner and name from repository
    repo_parts = target_repository.split("/")
    if len(repo_parts) != 2:
        log(f"Invalid repository format: {target_repository}. Expected 'owner/repo'", "ERROR")
        sys.exit(1)
        
    repo_owner, repo_name = repo_parts
    
    # Detect GitHub Projects associated with the repository
    projects = detect_github_projects(github_token, repo_owner, repo_name)
    
    if not projects:
        log(f"No projects found for repository {repo_owner}/{repo_name}", "ERROR")
        log("Please create a GitHub Project first and associate it with your repository, then run this script again.", "ERROR")
        sys.exit(1)
    
    # Handle project selection
    if len(projects) == 1:
        # If there's only one project, select it automatically
        selected_project = projects[0]
        project_id, title, number, url = selected_project
        log(f"Found one project associated with this repository: {title} (#{number})", "SUCCESS")
        log(f"Automatically selected project: {title} (ID: {project_id})", "SUCCESS")
    else:
        # Show available projects
        log(f"Found {len(projects)} GitHub Projects:", "SUCCESS")
        for i, (project_id, title, number, url) in enumerate(projects, 1):
            log(f"{i}. {title} (#{number}) - {url}")
        
        # Let user select a project
        selection = 0
        while selection < 1 or selection > len(projects):
            try:
                log("Select a project by entering its number:", "PROMPT")
                selection = int(input("> ").strip())
            except ValueError:
                selection = 0
        
        selected_project = projects[selection - 1]
        project_id, title, number, url = selected_project
        log(f"Selected project: {title} (ID: {project_id})", "SUCCESS")
    
    # Get project views and let user select which ones to apply filters to
    log("\nFetching project views to determine which ones should have Pruner filters applied...")
    views = get_project_views(github_token, project_id)
    
    selected_views = []
    if views:
        selected_views = select_project_views(views)
        
        # Format selected views for config
        selected_views_config = [
            {
                "id": view["id"],
                "name": view["name"],
                "number": view.get("number"),  # Store the view number
                "layout": view.get("layout_type", "Unknown")
            }
            for view in selected_views
        ]
    else:
        log("No project views found.", "WARNING")
    
    # Ask about dry run
    log("Would you like to run in dry run mode? (no labels will be applied) [Y/n]", "PROMPT")
    dry_run = input("> ").strip().lower() != "n"
    
    # Create pruner configuration
    pruner_config = {
        "project_id": project_id,
        "repository": target_repository,
        "done_age_days": 14,  # Default
        "done_overflow_limit": 3,  # Default
        "wiki_page_name": ".github/PRUNER_LOG.md",  # Default
        "dry_run": dry_run,
        "selected_views": selected_views_config,
        "custom_fields": {
            "workstream_field_id": "Workstream",
            "status_field_id": "Status",
            "done_status_value": "Done"
        }
    }
    
    # Update config.yaml in parent directory
    config_path, _ = find_parent_config_files()
    if config_path:
        # Load existing config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Update pruner section
        config["pruner"] = pruner_config
        
        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        log(f"Updated pruner configuration in {config_path}", "SUCCESS")
    
    return github_token, pruner_config, target_repository

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automatically manage GitHub Project boards by labeling issues")
    parser.add_argument("--dry-run", action="store_true", help="Run without applying labels")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logging information")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup")
    parser.add_argument("--repository", help="Override target repository (format: owner/repo)")
    args = parser.parse_args()
    
    # Display header
    print(f"\n{Colors.HEADER}===== Pruner - GitHub Project Manager ====={Colors.ENDC}")
    log("Starting pruner process...")
    
    try:
        # Load configuration from parent directory
        config_data = load_config_files()
        github_token = config_data.get("github_token") or get_github_token()
        pruner_config = config_data.get("pruner_config", {})
        target_repository = args.repository or config_data.get("repository")
        
        # Check if setup is requested or needed
        if args.setup or not pruner_config or not github_token:
            github_token, pruner_config, target_repository = setup_pruner()
        
        # Override dry run if specified on command line
        if args.dry_run:
            pruner_config["dry_run"] = True
            log("Dry run mode enabled via command line", "WARNING")
        
        # Enable verbose logging if specified
        if args.verbose:
            pruner_config["verbose"] = True
            log("Verbose logging enabled", "INFO")
        
        # Validate target repository
        if not target_repository:
            log("Target repository not specified. Please use --repository or set in config.yaml.", "ERROR")
            sys.exit(1)
        
        # Log the configuration
        log(f"Project ID: {pruner_config['project_id']}")
        log(f"Target repository: {target_repository}")
        log(f"Done age threshold: {pruner_config.get('done_age_days', 14)} days")
        log(f"Done overflow limit: {pruner_config.get('done_overflow_limit', 3)} issues")
        log(f"Workstream field: {pruner_config.get('custom_fields', {}).get('workstream_field_id', 'Workstream')}")
        log(f"Dry run mode: {pruner_config.get('dry_run', False)}")
        
        # Run the pruner
        log(f"Running pruner for project ID: {pruner_config['project_id']} on repository {target_repository}")
        result = run_pruner(pruner_config, github_token, target_repository)
        
        # Display results
        if result["success"]:
            log("Pruner completed successfully!", "SUCCESS")
            log(f"Labeled {result['not_planned_count']} issues as \"Not Planned\"", "INFO")
            log(f"Labeled {result['archived_count']} issues as \"Archive\"", "INFO")
            log(f"Total issues processed: {result['total_processed']}", "INFO")
            
            # Report on views
            if "views_processed" in result and result["views_processed"]:
                log(f"Applied to views: {', '.join(result['views_processed'])}", "SUCCESS")
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