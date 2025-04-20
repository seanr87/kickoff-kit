# scripts/import_issues/import_issues.py

import csv
import requests
import yaml
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"


def load_config():
    root = Path(__file__).resolve().parents[1]
    with open(root / "config.yaml", "r") as f:
        return yaml.safe_load(f)

def load_ids():
    root = Path(__file__).resolve().parents[1]
    with open(root / "ids.yaml", "r") as f:
        return yaml.safe_load(f)

def load_token():
    root = Path(__file__).resolve().parents[1]
    with open(root / "secrets.yaml", "r") as f:
        secrets = yaml.safe_load(f)
    return {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }

def read_issues_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def create_issue(repo, issue, milestone_id, headers):
    url = f"{GITHUB_API_URL}/repos/{repo}/issues"
    labels = [l.strip() for l in issue.get("labels", "").split(",") if l.strip()]
    priority = issue.get("priority", "").strip()
    if priority:
        labels.append(priority)

    data = {
        "title": issue["title"],
        "body": issue.get("body", ""),
        "assignees": [a.strip() for a in issue.get("assignees", "").split(",") if a.strip()],
        "milestone": milestone_id if issue.get("mvp", "No").lower() == "yes" else None,
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

def main():
    config = load_config()
    cfg = config.get("import_issues", {})
    project_cfg = config.get("create_project", {})
    headers = load_token()
    ids = load_ids()

    if not cfg or not project_cfg:
        raise SystemExit("🛑 Missing 'import_issues' or 'create_project' in config.yaml")

    if "issue_csv_path" not in cfg:
        raise SystemExit("🛑 'issue_csv_path' missing from import_issues config")

    issues = read_issues_csv(cfg["issue_csv_path"])
    milestone_id = ids.get("milestone_id")
    project_id = ids.get("project_id")
    field_ids = ids.get("custom_fields", {})

    for issue in issues:
        print(f"Creating issue: {issue['title']}")
        issue_response = create_issue(project_cfg["repo"], issue, milestone_id, headers)

        if "id" not in issue_response:
            print("❌ Failed to create issue:", issue_response)
            continue

        content_id = issue_response["node_id"]
        add_issue_to_project(project_id, content_id, field_ids, headers)

if __name__ == "__main__":
    main()
