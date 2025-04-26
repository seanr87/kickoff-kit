# GitHub Projects V2 Field Option Handling

import csv
import subprocess
import json
import sys
from pathlib import Path

def log(message):
    print(f"[issues.py] {message}")

def analyze_csv_for_options(csv_path):
    """
    Analyze a CSV file to find all unique values for each column
    Returns a dictionary with column names as keys and sets of unique values as values
    """
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Get all column headers
            headers = reader.fieldnames
            
            # Initialize dictionary to store unique values for each column
            unique_values = {header: set() for header in headers}
            
            # Process each row
            for row in reader:
                for header in headers:
                    if row[header] and row[header].strip():
                        unique_values[header].add(row[header].strip())
        
        return unique_values
    except Exception as e:
        log(f"❌ Error analyzing CSV: {str(e)}")
        return {}

def get_project_fields(project_url, github_token):
    """
    Get all fields for a GitHub Project V2 using GitHub CLI
    Returns a dictionary with field names as keys and field data as values
    """
    try:
        # Extract project number from URL
        project_parts = project_url.split('/')
        org = project_parts[-3]
        project_number = int(project_parts[-1])
        
        # Construct GraphQL query
        query = f"""
        query {{
          organization(login: "{org}") {{
            projectV2(number: {project_number}) {{
              id
              fields(first: 100) {{
                nodes {{
                  ... on ProjectV2FieldCommon {{
                    id
                    name
                    dataType
                  }}
                  ... on ProjectV2SingleSelectField {{
                    id
                    name
                    options {{
                      id
                      name
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        # Run query using GitHub CLI
        result = subprocess.run(
            ["gh", "api", "graphql", "-H", f"Authorization: Bearer {github_token}", "-f", f"query={query}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            log(f"❌ Error fetching project fields: {result.stderr}")
            return None
        
        # Parse results
        data = json.loads(result.stdout)
        project_id = data["data"]["organization"]["projectV2"]["id"]
        fields = data["data"]["organization"]["projectV2"]["fields"]["nodes"]
        
        # Convert to dictionary for easier lookup
        field_dict = {}
        for field in fields:
            field_dict[field["name"].lower()] = field
        
        return project_id, field_dict
    
    except Exception as e:
        log(f"❌ Error getting project fields: {str(e)}")
        return None, {}

def generate_option_instructions(csv_path, project_url, github_token):
    """
    Analyze CSV and project to provide instructions for manually creating missing options
    """
    log("Analyzing CSV for required field options...")
    unique_values = analyze_csv_for_options(csv_path)
    
    log(f"Found {len(unique_values)} columns in the CSV")
    for column, values in unique_values.items():
        log(f"  - {column}: {len(values)} unique values")
    
    log("Fetching project fields from GitHub...")
    project_id, project_fields = get_project_fields(project_url, github_token)
    
    if not project_id:
        log("❌ Failed to get project ID. Aborting.")
        return
    
    log(f"✅ Found project with ID: {project_id}")
    log(f"✅ Found {len(project_fields)} fields in the project")
    
    # Standard fields that don't need option creation
    standard_fields = {"title", "body", "assignees", "labels", "milestone"}
    
    # Identify which fields need options created
    required_options = {}
    
    for column, values in unique_values.items():
        column_lower = column.lower()
        
        # Skip standard fields
        if column_lower in standard_fields:
            continue
        
        # Check if field exists in project
        if column_lower in project_fields:
            field = project_fields[column_lower]
            
            # For single select fields, check if all options exist
            if "options" in field:
                existing_options = {opt["name"] for opt in field["options"]}
                missing_options = values - existing_options
                
                if missing_options:
                    required_options[column] = {
                        "field_id": field["id"],
                        "missing_options": list(missing_options)
                    }
        else:
            # Field doesn't exist - all options would need to be created after field creation
            required_options[column] = {
                "field_id": None,
                "missing_options": list(values)
            }
    
    # Generate instructions
    if required_options:
        log("\n===== MANUAL OPTION CREATION REQUIRED =====")
        log("The following fields need options to be created manually in the GitHub UI:")
        
        for field_name, data in required_options.items():
            log(f"\nField: {field_name}")
            if not data["field_id"]:
                log("  This field needs to be created first")
            
            log("  Missing options:")
            for option in data["missing_options"]:
                log(f"    - {option}")
        
        log("\nPlease create these options in the GitHub UI before running the import script.")
        log("Follow these steps:")
        log("1. Go to your project: " + project_url)
        log("2. Click on '+ Add field' or edit existing fields")
        log("3. For each field listed above, add the missing options")
        log("4. Once all options are created, run the import script again")
        
        # Write options to a file for reference
        output_file = Path("missing_field_options.json")
        with open(output_file, "w") as f:
            json.dump(required_options, f, indent=2)
        
        log(f"\nA detailed list has been saved to {output_file}")
        
        return False
    else:
        log("✅ All required field options already exist in the project")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze GitHub Projects V2 field options")
    parser.add_argument("--csv", required=True, help="Path to CSV file with issue data")
    parser.add_argument("--project-url", required=True, help="GitHub project URL")
    parser.add_argument("--github-token", required=True, help="GitHub token")
    
    args = parser.parse_args()
    
    if not generate_option_instructions(args.csv, args.project_url, args.github_token):
        sys.exit(1)