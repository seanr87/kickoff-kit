"""
creator.py - Creation module for GitHub Issues and Project fields

This module handles the creation of GitHub Issues and Project fields,
as well as their association with the GitHub Project.
"""

import requests
import json
import sys
import re
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

def log(message):
    """Simple logging function"""
    print(f"[creator] {message}")

def safe_get(d, key):
    """Safely get a value from a dictionary regardless of case"""
    for k in d.keys():
        if k.lower() == key.lower():
            return d[k]
    return ""

def create_custom_field(project_id, field_name, option_value, token):
    """
    Create a custom field with an initial option value
    Returns the created field data if successful, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    mutation = {
        "query": """
        mutation($input: CreateProjectV2FieldInput!) {
          createProjectV2Field(input: $input) {
            projectV2Field {
              ... on ProjectV2SingleSelectField {
                id
                name
                dataType
                options {
                  id
                  name
                }
              }
            }
          }
        }
        """,
        "variables": {
            "input": {
                "projectId": project_id,
                "name": field_name,
                "dataType": "SINGLE_SELECT",
                "singleSelectOptions": [{
                    "name": option_value,
                    "color": "GRAY",
                    "description": ""
                }]
            }
        }
    }
    
    log(f"Creating field '{field_name}' with initial option '{option_value}'...")
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error creating field '{field_name}': {response_json['errors']}")
            return None
        
        created = response_json["data"]["createProjectV2Field"]["projectV2Field"]
        log(f"Successfully created field '{field_name}' with initial option '{option_value}'")
        
        return created
    
    except Exception as e:
        log(f"Error creating field: {str(e)}")
        return None

def create_issue(repo_owner, repo_name, title, body, assignees, labels, token):
    """
    Create a GitHub Issue
    Returns the created issue data if successful, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    payload = {
        "title": title,
        "body": body or "",
        "assignees": assignees or [],
        "labels": labels or []
    }
    
    log(f"Creating issue: {title}")
    
    try:
        response = requests.post(
            f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 201:
            log(f"Error creating issue: {response.text}")
            return None
        
        issue_data = response.json()
        log(f"Successfully created issue #{issue_data['number']}: {title}")
        
        return issue_data
    
    except Exception as e:
        log(f"Error creating issue: {str(e)}")
        return None

def add_issue_to_project(issue_node_id, project_id, token):
    """
    Add an issue to a GitHub Project
    Returns the project item ID if successful, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    mutation = {
        "query": """
        mutation($input: AddProjectV2ItemByIdInput!) {
          addProjectV2ItemById(input: $input) {
            item {
              id
            }
          }
        }
        """,
        "variables": {
            "input": {
                "projectId": project_id,
                "contentId": issue_node_id
            }
        }
    }
    
    log(f"Adding issue to project...")
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error adding issue to project: {response_json['errors']}")
            return None
        
        item_id = response_json["data"]["addProjectV2ItemById"]["item"]["id"]
        log(f"Successfully added issue to project")
        
        return item_id
    
    except Exception as e:
        log(f"Error adding issue to project: {str(e)}")
        return None

def update_field_value(project_id, item_id, field_id, option_id, token):
    """
    Update a field value for an item in a project
    Returns True if successful, False otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    mutation = {
        "query": """
        mutation($input: UpdateProjectV2ItemFieldValueInput!) {
          updateProjectV2ItemFieldValue(input: $input) {
            projectV2Item {
              id
            }
          }
        }
        """,
        "variables": {
            "input": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "value": {
                    "singleSelectOptionId": option_id
                }
            }
        }
    }
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error updating field value: {response_json['errors']}")
            return False
        
        return True
    
    except Exception as e:
        log(f"Error updating field value: {str(e)}")
        return False

def assign_milestone(repo_owner, repo_name, issue_number, milestone_title, token):
    """
    Assign a milestone to an issue
    Returns True if successful, False otherwise
    """
    if not milestone_title:
        return True
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    # Get milestones
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/milestones",
            headers=headers
        )
        
        if response.status_code != 200:
            log(f"Error getting milestones: {response.text}")
            return False
        
        milestones = response.json()
        milestone_number = None
        
        for milestone in milestones:
            if milestone["title"] == milestone_title:
                milestone_number = milestone["number"]
                break
        
        if not milestone_number:
            # Create milestone
            response = requests.post(
                f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/milestones",
                headers=headers,
                json={"title": milestone_title}
            )
            
            if response.status_code != 201:
                log(f"Error creating milestone: {response.text}")
                return False
            
            milestone_number = response.json()["number"]
        
        # Assign milestone to issue
        response = requests.patch(
            f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues/{issue_number}",
            headers=headers,
            json={"milestone": milestone_number}
        )
        
        if response.status_code != 200:
            log(f"Error assigning milestone: {response.text}")
            return False
        
        log(f"Successfully assigned milestone '{milestone_title}' to issue #{issue_number}")
        return True
    
    except Exception as e:
        log(f"Error with milestone: {str(e)}")
        return False

def process_issue_fields(item_id, issue_data, project_id, project_fields, token):
    """
    Process and update all fields for an issue
    Returns True if successful, False otherwise
    """
    success = True
    
    for field_name, field_value in issue_data.items():
        field_name_lower = field_name.lower()
        
        # Skip standard fields and empty values
        if field_name_lower in ["title", "body", "assignees", "labels", "milestone"] or not field_value:
            continue
        
        # Handle status field separately
        if field_name_lower == "status":
            status_field = next((f for f in project_fields.values() if f["name"].lower() == "status"), None)
            if status_field and field_value:
                option = next((opt for opt in status_field.get("options", []) if opt["name"] == field_value), None)
                if option:
                    if not update_field_value(project_id, item_id, status_field["id"], option["id"], token):
                        log(f"Failed to update Status field to '{field_value}'")
                        success = False
                    else:
                        log(f"Updated Status field to '{field_value}'")
            continue
        
        # Handle custom fields
        field = next((f for f in project_fields.values() if f["name"].lower() == field_name_lower), None)
        if field and "options" in field:
            option = next((opt for opt in field["options"] if opt["name"] == field_value), None)

def find_option_id(field, value, token, project_id, log_messages=True):
    """
    Find or create an option for a field
    Returns the option ID if successful, None otherwise
    """
    # Check if the option already exists
    for option in field.get("options", []):
        if option["name"] == value:
            return option["id"]
    
    # Option doesn't exist, create it
    if log_messages:
        log(f"Option '{value}' not found for field '{field['name']}', creating it...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    mutation = {
        "query": """
        mutation($input: UpdateProjectV2Input!) {
          updateProjectV2(input: $input) {
            projectV2 {
              id
            }
          }
        }
        """,
        "variables": {
            "input": {
                "projectId": project_id,
                "singleSelectField": {
                    "id": field["id"],
                    "optionId": None,
                    "newOptionName": value,
                    "color": "GRAY",
                    "description": ""
                }
            }
        }
    }
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        response_json = response.json()
        
        if "errors" in response_json:
            if log_messages:
                log(f"Error creating option '{value}': {response_json['errors']}")
            return None
        
        # Now get the updated field with new option
        updated_field = get_updated_field(token, project_id, field["id"])
        if updated_field and "options" in updated_field:
            for option in updated_field["options"]:
                if option["name"] == value:
                    if log_messages:
                        log(f"Successfully created option '{value}' for field '{field['name']}'")
                    return option["id"]
        
        return None
    
    except Exception as e:
        if log_messages:
            log(f"Error creating option: {str(e)}")
        return None

def get_updated_field(token, project_id, field_id):
    """
    Get updated field data with all options
    Returns the field data if successful, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    query = {
        "query": """
        query($projectId: ID!, $fieldId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              field(id: $fieldId) {
                ... on ProjectV2SingleSelectField {
                  id
                  name
                  dataType
                  options {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {
            "projectId": project_id,
            "fieldId": field_id
        }
    }
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=query)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error fetching updated field: {response_json['errors']}")
            return None
        
        return response_json.get("data", {}).get("node", {}).get("field", {})
    
    except Exception as e:
        log(f"Error getting updated field: {str(e)}")
        return None

def create_sample_issue(csv_path, token, repo_owner, repo_name, project_id, fields_to_create, analysis_results):
    """
    Create a sample issue to validate the workflow
    Returns a dictionary with the result
    """
    # Get the first row from the CSV
    csv_rows = analysis_results.get("csv_rows", [])
    if not csv_rows:
        return {
            "success": False,
            "error": "No data rows found in CSV"
        }
    
    first_row = csv_rows[0]
    
    # Extract standard fields
    title = safe_get(first_row, "title")
    body = safe_get(first_row, "body")
    
    # Handle assignees (comma-separated)
    assignees_str = safe_get(first_row, "assignees")
    assignees = [a.strip() for a in assignees_str.split(",")] if assignees_str else []
    
    # Handle labels (comma-separated)
    labels_str = safe_get(first_row, "labels")
    labels = [l.strip() for l in labels_str.split(",")] if labels_str else []
    
    # Create the issue
    issue_data = create_issue(repo_owner, repo_name, title, body, assignees, labels, token)
    if not issue_data:
        return {
            "success": False,
            "error": "Failed to create sample issue"
        }
    
    # Add to project
    item_id = add_issue_to_project(issue_data["node_id"], project_id, token)
    if not item_id:
        return {
            "success": False,
            "error": "Failed to add issue to project"
        }
    
    # Set milestone if present
    milestone = safe_get(first_row, "milestone")
    if milestone and not assign_milestone(repo_owner, repo_name, issue_data["number"], milestone, token):
        log(f"Warning: Failed to assign milestone '{milestone}' to sample issue")
    
    # Create custom fields if needed
    project_fields = analysis_results.get("project_fields", {})
    
    for field_name, field_value in first_row.items():
        field_name_lower = field_name.lower()
        
        # Skip standard fields, empty values, and newly created fields
        if (field_name_lower in ["title", "body", "assignees", "labels", "milestone"] 
            or not field_value 
            or field_name in fields_to_create):
            continue
        
        # Handle Status field
        if field_name_lower == "status":
            status_field = next((f for f in project_fields.values() if f["name"].lower() == "status"), None)
            if status_field:
                # Find or create the option
                option_id = find_option_id(status_field, field_value, token, project_id)
                if option_id:
                    update_field_value(project_id, item_id, status_field["id"], option_id, token)
            continue
        
        # Handle date fields (End Date)
        if field_name_lower == "end date":
            handle_date_field(field_name, field_value, project_id, item_id, project_fields, token)
            continue
        
        # Handle other fields
        field = next((f for f in project_fields.values() if f["name"].lower() == field_name_lower), None)
        if field and field.get("dataType") == "SINGLE_SELECT":
            # Find or create the option
            option_id = find_option_id(field, field_value, token, project_id)
            if option_id:
                update_field_value(project_id, item_id, field["id"], option_id, token)

    
    # Update existing field values
    for field_name, field_value in first_row.items():
        field_name_lower = field_name.lower()
        
        # Skip standard fields, empty values, and newly created fields
        if (field_name_lower in ["title", "body", "assignees", "labels", "milestone"] 
            or not field_value 
            or field_name in fields_to_create):
            continue
        
        # Handle Status field
        if field_name_lower == "status":
            status_field = next((f for f in project_fields.values() if f["name"].lower() == "status"), None)
            if status_field:
                # Find or create the option
                option_id = find_option_id(status_field, field_value, token, project_id)
                if option_id:
                    update_field_value(project_id, item_id, status_field["id"], option_id, token)
            continue
        
        # Handle other fields
        field = next((f for f in project_fields.values() if f["name"].lower() == field_name_lower), None)
        if field and field.get("dataType") == "SINGLE_SELECT":
            # Find or create the option
            option_id = find_option_id(field, field_value, token, project_id)
            if option_id:
                update_field_value(project_id, item_id, field["id"], option_id, token)
    
    # Return success
    return {
        "success": True,
        "issue_number": issue_data["number"],
        "issue_url": issue_data["html_url"]
    }

def create_issues(csv_path, token, repo_owner, repo_name, project_id, fields_to_create, analysis_results, sample_issue_number=None):
    """
    Create issues from a CSV file
    Returns a dictionary with the result
    """
    created_count = 0
    skipped_count = 0
    
    csv_rows = analysis_results.get("csv_rows", [])
    project_fields = analysis_results.get("project_fields", {})
    
    # Skip the first row if it was used for the sample
    start_index = 1 if sample_issue_number else 0
    
    # Process each row
    for i, row in enumerate(csv_rows[start_index:], start=start_index):
        title = safe_get(row, "title")
        if not title:
            log(f"Skipping row {i+1}: Missing title")
            skipped_count += 1
            continue
        
        # Extract standard fields
        body = safe_get(row, "body")
        
        # Handle assignees (comma-separated)
        assignees_str = safe_get(row, "assignees")
        assignees = [a.strip() for a in assignees_str.split(",")] if assignees_str else []
        
        # Handle labels (comma-separated)
        labels_str = safe_get(row, "labels")
        labels = [l.strip() for l in labels_str.split(",")] if labels_str else []
        
        # Create the issue
        issue_data = create_issue(repo_owner, repo_name, title, body, assignees, labels, token)
        if not issue_data:
            log(f"Error creating issue from row {i+1}")
            skipped_count += 1
            continue
        
        # Add to project
        item_id = add_issue_to_project(issue_data["node_id"], project_id, token)
        if not item_id:
            log(f"Error adding issue #{issue_data['number']} to project")
            skipped_count += 1
            continue
        
        # Set milestone if present
        milestone = safe_get(row, "milestone")
        if milestone and not assign_milestone(repo_owner, repo_name, issue_data["number"], milestone, token):
            log(f"Warning: Failed to assign milestone '{milestone}' to issue #{issue_data['number']}")
        
        # Update field values (both custom and standard)
        for field_name, field_value in row.items():
            field_name_lower = field_name.lower()
            
            # Skip standard fields and empty values
            if field_name_lower in ["title", "body", "assignees", "labels", "milestone"] or not field_value:
                continue
            
            # Handle Status field
            if field_name_lower == "status":
                status_field = next((f for f in project_fields.values() if f["name"].lower() == "status"), None)
                if status_field:
                    # Find or create the option (quiet mode)
                    option_id = find_option_id(status_field, field_value, token, project_id, log_messages=False)
                    if option_id:
                        update_field_value(project_id, item_id, status_field["id"], option_id, token)
                continue
            
            # Handle date fields (End Date)
            if field_name_lower == "end date":
                handle_date_field(field_name, field_value, project_id, item_id, project_fields, token)
                continue
            
            # Handle other fields
            field = next((f for f in project_fields.values() if f["name"].lower() == field_name_lower), None)
            if field and field.get("dataType") == "SINGLE_SELECT":
                # Find or create the option (quiet mode)
                option_id = find_option_id(field, field_value, token, project_id, log_messages=False)
                if option_id:
                    update_field_value(project_id, item_id, field["id"], option_id, token)

    
    return {
        "success": True,
        "created": created_count,
        "skipped": skipped_count
    }   

def handle_date_field(field_name, field_value, project_id, item_id, project_fields, token):
    """
    Handle updating date fields specifically
    Returns True if successful, False otherwise
    """
    field_name_lower = field_name.lower()
    
    # Find the field in project fields
    field = next((f for f in project_fields.values() if f["name"].lower() == field_name_lower), None)
    if not field:
        log(f"Field '{field_name}' not found in project")
        return False
        
    # Check if it's a date field
    if field.get("dataType") != "DATE":
        log(f"Field '{field_name}' is not a date field")
        return False
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    # Format the date properly - GitHub accepts ISO format
    try:
        # Try to parse the date - handle common formats
        from datetime import datetime
        import re
        
        # Check if it's already ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$', field_value):
            date_value = field_value
        else:
            # Try common formats
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    date_obj = datetime.strptime(field_value, fmt)
                    date_value = date_obj.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            else:
                log(f"Could not parse date: {field_value}")
                return False
        
        mutation = {
            "query": """
            mutation($input: UpdateProjectV2ItemFieldValueInput!) {
              updateProjectV2ItemFieldValue(input: $input) {
                projectV2Item {
                  id
                }
              }
            }
            """,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "itemId": item_id,
                    "fieldId": field["id"],
                    "value": {
                        "date": date_value
                    }
                }
            }
        }
        
        response = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error updating date field: {response_json['errors']}")
            return False
        
        log(f"Successfully updated date field '{field_name}' to '{date_value}'")
        return True
        
    except Exception as e:
        log(f"Error handling date field: {str(e)}")
        return False         