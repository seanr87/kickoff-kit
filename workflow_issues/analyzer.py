"""
analyzer.py - Analysis module for CSV and GitHub Project structure

This module handles the analysis of CSV files and GitHub Projects,
identifying fields and options that need to be created or modified.
"""

import csv
import requests
import json
import sys
from pathlib import Path

# Standard fields that need special handling
STANDARD_FIELDS = {
    "title": "title",
    "body": "body", 
    "assignees": "assignees",
    "labels": "labels",
    "milestone": "milestone",
    "status": "status"
}

DATE_FIELDS = {
    "end date": "DATE",
    "due date": "DATE",
    "start date": "DATE",
    "deadline": "DATE"
}


GITHUB_API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

def log(message):
    """Simple logging function"""
    print(f"[analyzer] {message}")

def check_project_access(token, owner, repo, project_number):
    """
    Check if the provided token has access to the specified GitHub project
    Returns the project ID if access is granted, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    # Query for the project ID
    query = {
        "query": """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              id
            }
          }
        }
        """,
        "variables": {
            "owner": owner,
            "number": project_number
        }
    }
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=query)
        response_json = response.json()
        
        if "errors" in response_json:
            # Try alternative query for user projects instead of organization
            alt_query = {
                "query": """
                query($number: Int!) {
                  viewer {
                    projectV2(number: $number) {
                      id
                    }
                  }
                }
                """,
                "variables": {
                    "number": project_number
                }
            }
            
            response = requests.post(GRAPHQL_URL, headers=headers, json=alt_query)
            response_json = response.json()
            
            if "errors" in response_json:
                log(f"Error accessing project: {response_json['errors']}")
                return None
            
            return response_json.get("data", {}).get("viewer", {}).get("projectV2", {}).get("id")
        
        return response_json.get("data", {}).get("organization", {}).get("projectV2", {}).get("id")
    
    except Exception as e:
        log(f"Error checking project access: {str(e)}")
        return None

def read_csv_file(csv_path):
    """
    Read a CSV file and extract headers and rows
    Returns a tuple of (headers, rows)
    """
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
            
        if not headers or not rows:
            log("CSV file is empty or has no headers")
            return None, None
            
        return headers, rows
    except Exception as e:
        log(f"Error reading CSV file: {str(e)}")
        return None, None

def get_project_fields(token, project_id):
    """
    Get all fields for a GitHub Project V2
    Returns a dictionary mapping field names to field data
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    query = {
        "query": """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 100) {
                nodes {
                  ... on ProjectV2FieldCommon {
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
                    }
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {
            "projectId": project_id
        }
    }
    
    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=query)
        response_json = response.json()
        
        if "errors" in response_json:
            log(f"Error fetching project fields: {response_json['errors']}")
            return {}
        
        fields = response_json.get("data", {}).get("node", {}).get("fields", {}).get("nodes", [])
        field_dict = {}
        
        for field in fields:
            field_dict[field["name"].lower()] = field
        
        return field_dict
    
    except Exception as e:
        log(f"Error getting project fields: {str(e)}")
        return {}

def analyze_csv_and_project(csv_path, token, owner, repo, project_number, project_id, project_url):
    """
    Analyze a CSV file and GitHub Project to identify fields and options
    Returns a dictionary with analysis results
    """
    # Read CSV file
    headers, rows = read_csv_file(csv_path)
    if not headers or not rows:
        return {
            "success": False,
            "error": "Failed to read CSV file"
        }
    
    # Store rows in csv_rows variable (this was missing)
    csv_rows = rows
    
    # Get project fields
    project_fields = get_project_fields(token, project_id)
    if not project_fields:
        return {
            "success": False,
            "error": "Failed to get project fields"
        }
    
    # Standard vs custom fields
    standard_fields = []
    custom_fields = {}
    
    # Identify custom fields and gather unique values
    for header in headers:
        header_lower = header.lower()
        
        if header_lower in STANDARD_FIELDS:
            standard_fields.append(header)
        else:
            custom_fields[header] = set()
            
            # Collect unique values for this field from the CSV
            for row in csv_rows:  # Use csv_rows here
                value = row.get(header, "").strip()
                if value:
                    custom_fields[header].add(value)
    
    # Check which custom fields already exist
    existing_custom_fields = []
    missing_fields = {}
    
    for field, values in custom_fields.items():
        field_lower = field.lower()
        
        if field_lower in project_fields:
            existing_custom_fields.append(field)
        else:
            missing_fields[field] = list(values)
    
    # Check for missing options in existing fields
    missing_options = {}
    
    for field in existing_custom_fields:
        field_lower = field.lower()
        project_field = project_fields.get(field_lower, {})
        
        # Skip if not a single select field
        if project_field.get("dataType") != "SINGLE_SELECT" or "options" not in project_field:
            continue
        
        # Get existing options
        existing_options = {opt["name"] for opt in project_field.get("options", [])}
        
        # Find missing options
        field_values = custom_fields.get(field, set())
        missing = [val for val in field_values if val not in existing_options]
        
        if missing:
            missing_options[field] = missing
            
    # Check for date fields
    date_fields = []
    for header in headers:
        header_lower = header.lower()
        if header_lower in DATE_FIELDS:
            # Check if field exists
            if header_lower in project_fields:
                date_fields.append(header)
            else:
                # Add to missing fields
                missing_fields[header] = ["DATE FIELD"]
                
    # Return the analysis results
    return {
        "success": True,
        "standard_fields": standard_fields,
        "existing_custom_fields": existing_custom_fields,
        "missing_fields": missing_fields,
        "missing_options": missing_options,
        "project_fields": project_fields,
        "csv_headers": headers,
        "csv_rows": csv_rows,  # This is now properly defined
        "project_id": project_id,
        "project_url": project_url,
        "date_fields": date_fields
    }
