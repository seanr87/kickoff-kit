# scripts/import_issues/import_issues.py

import csv
import requests
import yaml
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"

def load_yaml(filename, config_dir):
    with open(Path(config_dir) / filename, "r") as f:
        return yaml.safe_load(f)

def read_issues_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def create_issue(repo, issue, milestone_ids, default_milestone, headers):
    url = f"{GITHUB_API_URL}/repos/{repo}/issues"
    labels = [l.strip() for l in issue.get("labels", "").split(",") if l.strip()]
    priority = issue.get("priority", "").strip()
    if priority:
        labels.append(priority)

    status = issue.get("status", "").strip()
    if status:
        labels.append(status)

    milestone_name = issue.get("milestone", "").strip()
    milestone_id = milestone_ids.get(milestone_name, default_milestone)

    data = {
        "title": issue["title"],
        "body": issue.get("body", ""),
        "assignees": [a.strip() for a in issue.get("assignees", "").split(",") if a.strip()],
        "milestone": milestone_id,
        "labels": labels,
    }
    data = {k: v for k, v in data.items() if v}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def get_project_fields(headers, project_id):
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
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {"projectId": project_id}
    }
    response = requests.post("https://api.github.com/graphql", headers=headers, json=query)
    fields = response.json()["data"]["node"]["fields"]["nodes"]
    return {field["name"]: field["id"] for field in fields}

def add_issue_to_project(project_id, content_id, field_values, headers):
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
                "contentId": content_id
            }
        }
    }
    response = requests.post("https://api.github.com/graphql", headers=headers, json=mutation)
    print("✅ Issue added to project")

def main(config_dir):
    config = load_yaml("config.yaml", config_dir)
    cfg = config.get("import_issues", {})
    project_cfg = config.get("create_project", {})
    secrets = load_yaml("secrets.yaml", config_dir)
    headers = {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }
    ids = load_yaml("ids.yaml", config_dir)

    issues = read_issues_csv(Path(cfg["issue_csv_path"]))
    milestone_ids = ids.get("milestone_ids", {})
    default_milestone = ids.get("milestone_id")
    project_id = ids.get("project_id")
    field_ids = ids.get("custom_fields", {})

    for issue in issues:
        print(f"Creating issue: {issue['title']}")
        issue_response = create_issue(project_cfg["repo"], issue, milestone_ids, default_milestone, headers)

        if "id" not in issue_response:
            print("❌ Failed to create issue:", issue_response)
            continue

        content_id = issue_response["node_id"]
        add_issue_to_project(project_id, content_id, field_ids, headers)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    main(args.config_dir)
