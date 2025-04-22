# import_issues.py (always assigns Prototype milestone, no release column)

import csv
import requests
import yaml
from pathlib import Path

GITHUB_API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

def load_yaml(filename, config_dir):
    with open(Path(config_dir) / filename, "r") as f:
        return yaml.safe_load(f)

def save_yaml(filename, data, config_dir):
    with open(Path(config_dir) / filename, "w") as f:
        yaml.dump(data, f)

def read_issues_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def create_issue(repo, issue, milestone_number, headers):
    url = f"{GITHUB_API_URL}/repos/{repo}/issues"
    raw_labels = [l.strip() for l in issue.get("labels", "").split(",") if l.strip()]
    excluded = {"priority", "status"}
    labels = [l for l in raw_labels if l.lower() not in excluded]

    data = {
        "title": issue["title"],
        "body": issue.get("body", ""),
        "assignees": [a.strip() for a in issue.get("assignees", "").split(",") if a.strip()],
        "milestone": milestone_number,
        "labels": labels,
    }
    data = {k: v for k, v in data.items() if v}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def get_select_option_id(field_name, option_name, select_options):
    return select_options.get(field_name, {}).get(option_name)

def add_issue_to_project(project_id, content_id, issue, field_ids, select_options, headers, status_field_id):
    add_mutation = {
        "query": """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {
            projectId: $projectId,
            contentId: $contentId
          }) {
            item { id }
          }
        }
        """,
        "variables": {
            "projectId": project_id,
            "contentId": content_id
        }
    }
    add_response = requests.post(GRAPHQL_URL, headers=headers, json=add_mutation)
    item_id = add_response.json().get("data", {}).get("addProjectV2ItemById", {}).get("item", {}).get("id")

    if not item_id:
        print(f"❌ Failed to add issue to project: {add_response.text}")
        return

    status_value = issue.get("status", "").strip()
    if status_value:
        mutation = {
            "query": """
            mutation($input: UpdateProjectV2ItemFieldValueInput!) {
              updateProjectV2ItemFieldValue(input: $input) {
                projectV2Item { id }
              }
            }
            """,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "itemId": item_id,
                    "fieldId": status_field_id,
                    "value": { "singleSelectOptionId": get_select_option_id("status", status_value, select_options) }
                }
            }
        }
        res = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        res_json = res.json()
        if "errors" in res_json:
            print(f"❌ Status update failed: {res_json['errors']}")
        else:
            print(f"✅ Status updated to '{status_value}'")

    for name in ["workstream", "mvp", "dependencies", "priority"]:
        if name not in issue:
            continue

        raw_value = issue.get(name)
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        if name == "priority":
            value = {
                "high": "High",
                "critical": "Critical",
                "low": "Low"
            }.get(value.lower(), value)

        if not value:
            continue

        field_type = "single_select" if name in ["workstream", "mvp", "priority"] else "text"
        field_id = field_ids.get(name)
        if not field_id:
            print(f"⚠️ Field ID missing for {name}")
            continue

        payload = {"fieldId": field_id}

        if field_type == "single_select":
            print(f"[DEBUG] Looking up '{value}' for field '{name}'")
            print(f"[DEBUG] Available: {select_options.get(name)}")
            option_id = get_select_option_id(name, value, select_options)
            if not option_id:
                print(f"❌ No select option ID found for '{name}' value '{value}'")
                continue
            payload["value"] = {"singleSelectOptionId": option_id}
        else:
            payload["value"] = {"text": value}

        mutation = {
            "query": """
            mutation($input: UpdateProjectV2ItemFieldValueInput!) {
              updateProjectV2ItemFieldValue(input: $input) {
                projectV2Item { id }
              }
            }
            """,
            "variables": {"input": {
                "projectId": project_id,
                "itemId": item_id,
                **payload
            }}
        }
        res = requests.post(GRAPHQL_URL, headers=headers, json=mutation)
        res_json = res.json()
        if "errors" in res_json:
            print(f"❌ Field update failed for {name}: {res_json['errors']}")
        else:
            print(f"✅ Field '{name}' updated to '{value}'")

    print("✅ Issue added to project and fields updated")

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
    status_field_id = ids.get("status_field_id")

    issues = read_issues_csv(Path(cfg["issue_csv_path"]))
    milestone_number = ids.get("milestone_number")
    default_milestone = ids.get("milestone_id")
    project_id = ids.get("project_id")
    field_ids = ids.get("custom_fields", {})
    select_options = ids.get("select_options", {})

    for issue in issues:
        print(f"Creating issue: {issue['title']}")
        issue_response = create_issue(project_cfg["repo"], issue, milestone_number, headers)

        if "id" not in issue_response:
            print("❌ Failed to create issue:", issue_response)
            continue

        content_id = issue_response["node_id"]
        add_issue_to_project(project_id, content_id, issue, field_ids, select_options, headers, status_field_id)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    main(args.config_dir)
