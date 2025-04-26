# issues.py (live safeguard enabled)

import csv
import requests
import yaml
from pathlib import Path
import sys
import re

GITHUB_API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

# -----------------------
# Utility Functions
# -----------------------

def safe_get(d, key):
    for k in d.keys():
        if k.lower() == key.lower():
            return d[k]
    return ""

def load_yaml(filename, config_dir):
    with open(Path(config_dir) / filename, "r") as f:
        return yaml.safe_load(f)

def save_yaml(filename, data, config_dir):
    with open(Path(config_dir) / filename, "w") as f:
        yaml.dump(data, f)

def read_issues_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def log(message):
    print(f"[issues.py] {message}")

def parse_repo_from_url(repo_url):
    log(f"Parsing repo URL: {repo_url}")
    if "github.com/" not in repo_url.lower():
        log("Invalid repo URL format!")
        return None
    parts = repo_url.split("github.com/")[-1].split("/")
    if len(parts) >= 2:
        repo = f"{parts[0]}/{parts[1]}"
        log(f"Parsed repo: {repo}")
        return repo
    else:
        log("Failed to parse repo URL!")
        return None

def parse_project_number_from_url(project_url):
    log(f"Parsing project URL: {project_url}")
    match = re.search(r"/projects/(\d+)", project_url)
    if match:
        log(f"Parsed project number: {match.group(1)}")
        return int(match.group(1))
    else:
        log("Failed to parse project number!")
        return None

# -----------------------
# GitHub API Functions
# -----------------------

def get_project_id(project_number, headers):
    query = {
        "query": """
        query($number: Int!) {
          viewer {
            projectV2(number: $number) {
              id
            }
          }
        }
        """,
        "variables": {"number": project_number}
    }
    res = requests.post(GRAPHQL_URL, headers=headers, json=query)
    if "errors" in res.json():
        log(f"GraphQL error: {res.json()['errors']}")
        sys.exit(1)
    return res.json()["data"]["viewer"]["projectV2"]["id"]

def get_project_fields(project_id, headers):
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
                    options { id name }
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {"projectId": project_id}
    }
    res = requests.post(GRAPHQL_URL, headers=headers, json=query)
    res_json = res.json()
    if "errors" in res_json:
        log(f"GraphQL error during field fetch: {res_json['errors']}")
        sys.exit(1)
    fields = res_json["data"]["node"]["fields"]["nodes"]
    return {field["name"]: field for field in fields}

def create_custom_field(project_id, name, headers):
    payload = {
        "query": """
        mutation($input: CreateProjectV2FieldInput!) {
          createProjectV2Field(input: $input) {
            projectV2Field { id name }
          }
        }
        """,
        "variables": {
            "input": {
                "projectId": project_id,
                "name": name,
                "dataType": "TEXT"
            }
        }
    }
    res = requests.post(GRAPHQL_URL, headers=headers, json=payload)
    if res.status_code == 200:
        log(f"✅ Created custom field: {name}")
    else:
        log(f"❌ Failed to create field '{name}': {res.text}")
        sys.exit(1)

def create_issue(repo, title, body, assignees, headers, dry_run=False):
    if dry_run:
        log(f"[Dry Run] Would create issue: {title}")
        return "DUMMY_NODE_ID"
    payload = {"title": title, "body": body, "assignees": assignees}
    url = f"{GITHUB_API_URL}/repos/{repo}/issues"
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 201:
        log(f"✅ Created issue: {title}")
        return res.json()["node_id"]
    else:
        log(f"❌ Failed to create issue: {res.text}")
        sys.exit(1)

def create_milestone(repo, title, headers, dry_run=False):
    if dry_run:
        log(f"[Dry Run] Would create milestone: {title}")
        return "DUMMY_MILESTONE_ID"
    url = f"{GITHUB_API_URL}/repos/{repo}/milestones"
    res = requests.post(url, headers=headers, json={"title": title})
    if res.status_code == 201:
        milestone_number = res.json()["number"]
        log(f"✅ Created milestone: {title}")
        return milestone_number
    else:
        log(f"❌ Failed to create milestone '{title}': {res.text}")
        sys.exit(1)

# -----------------------
# CSV Field Validation
# -----------------------

def validate_csv_headers(headers, existing_fields, project_id, headers_api, dry_run):
    whitelist = {"title", "body", "assignees", "milestone", "status"}
    required = {"title", "status"}
    missing = required - set(h.lower() for h in headers)
    if missing:
        log(f"CSV missing required fields: {missing}")
        sys.exit(1)

    unknown = [h for h in headers if h.lower() not in whitelist and h not in existing_fields]
    if unknown:
        print("\nThe following CSV columns are not whitelisted or found as custom fields in the project:")
        for col in unknown:
            print(f"  - {col}")
        confirm = input("\nWould you like to create these as new custom fields on the project? [y/N]: ").lower()
        if confirm != "y":
            print("Exiting without modifying project.")
            sys.exit(1)
        else:
            for field in unknown:
                if dry_run:
                    log(f"[Dry Run] Would create custom field: {field}")
                else:
                    create_custom_field(project_id, field, headers_api)

# -----------------------
# Main Workflow
# -----------------------

def main(config_dir, csv_path, repo_url, project_url, dry_run=False):
    config_dir = Path(config_dir)
    secrets = load_yaml("secrets.yaml", config_dir)
    headers_api = {"Authorization": f"Bearer {secrets['github_token']}", "Accept": "application/vnd.github+json"}

    repo = parse_repo_from_url(repo_url)
    project_number = parse_project_number_from_url(project_url)
    project_id = get_project_id(project_number, headers_api)

    existing_fields = get_project_fields(project_id, headers_api)
    issues = read_issues_csv(csv_path)
    headers_in_csv = issues[0].keys()

    validate_csv_headers(headers_in_csv, existing_fields, project_id, headers_api, dry_run)

    milestone_cache = {}

    for issue in issues:
        title = safe_get(issue, "title").strip()
        body = safe_get(issue, "body").strip()
        assignees = [a.strip() for a in safe_get(issue, "assignees").split(",") if a.strip()]

        if not title:
            log("❌ Cannot create issue without a title. Skipping.")
            continue

        node_id = create_issue(repo, title, body, assignees, headers_api, dry_run)

        milestone_title = safe_get(issue, "milestone").strip()
        if milestone_title:
            if milestone_title not in milestone_cache:
                milestone_id = create_milestone(repo, milestone_title, headers_api, dry_run)
                milestone_cache[milestone_title] = milestone_id
            else:
                milestone_id = milestone_cache[milestone_title]
            log(f"[Dry Run] Would assign milestone '{milestone_title}'")

        for field_name, value in issue.items():
            if field_name.lower() == "status" and value:
                log(f"[Dry Run] Would set Status to '{value.strip()}'")
            elif field_name in existing_fields and value:
                field_id = existing_fields[field_name]["id"]
                log(f"[Dry Run] Would update field {field_id} to '{value.strip()}'")

    log("✅ Full Issue creation and field update simulation complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create GitHub Issues and add to Project")
    parser.add_argument("--config-dir", required=True, help="Path to config directory containing secrets.yaml")
    parser.add_argument("--csv", required=True, help="Path to the CSV containing Issues to import")
    parser.add_argument("--repo-url", required=True, help="URL of the GitHub Repository")
    parser.add_argument("--project-url", required=True, help="URL of the GitHub Project")
    parser.add_argument("--confirm-live", action="store_true", help="CONFIRM you want to create live issues (otherwise dry-run)")
    args = parser.parse_args()
    dry_run = not args.confirm_live
    main(args.config_dir, args.csv, args.repo_url, args.project_url, dry_run)
