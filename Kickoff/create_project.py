# create_project.py

import requests
import yaml
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_API_URL = "https://api.github.com"

def load_yaml(filename, config_dir):
    with open(Path(config_dir) / filename, "r") as f:
        return yaml.safe_load(f)

def save_yaml(filename, data, config_dir):
    with open(Path(config_dir) / filename, "w") as f:
        yaml.dump(data, f)

def get_user_id(headers):
    query = { "query": "query { viewer { id } }" }
    res = requests.post(GRAPHQL_URL, headers=headers, json=query)
    return res.json()["data"]["viewer"]["id"]

def create_project(owner_id, title, headers):
    query = {
        "query": """
        mutation($input: CreateProjectV2Input!) {
          createProjectV2(input: $input) {
            projectV2 {
              id
            }
          }
        }
        """,
        "variables": {
            "input": {
                "ownerId": owner_id,
                "title": title
            }
        }
    }
    res = requests.post(GRAPHQL_URL, headers=headers, json=query)
    print(res.status_code, res.text)
    return res.json()["data"]["createProjectV2"]["projectV2"]["id"]

def create_field(project_id, name, ftype, headers, options=None):
    payload = {
        "query": """
        mutation($input: CreateProjectV2FieldInput!) {
          createProjectV2Field(input: $input) {
            projectV2Field {
              ... on ProjectV2FieldCommon {
                id
                name
              }
              ... on ProjectV2SingleSelectField {
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
                "name": name,
                "dataType": ftype
            }
        }
    }

    if ftype == "SINGLE_SELECT":
        payload["variables"]["input"]["singleSelectOptions"] = [
            {"name": opt, "description": "", "color": "GRAY"} for opt in options
        ]

    res = requests.post(GRAPHQL_URL, headers=headers, json=payload)
    print(res.status_code, res.text)
    data = res.json()["data"]["createProjectV2Field"]["projectV2Field"]
    print(f"✅ Added field: {name} ({ftype})")
    return data

def get_field_option_ids(project_id, headers):
    query = {
        "query": """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 100) {
                nodes {
                  __typename
                  ... on ProjectV2SingleSelectField {
                    id
                    name
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
        "variables": {"projectId": project_id}
    }
    response = requests.post(GRAPHQL_URL, headers=headers, json=query)
    nodes = response.json()["data"]["node"]["fields"]["nodes"]

    return {
        field["name"]: {
            "field_id": field["id"],
            "options": {opt["name"]: opt["id"] for opt in field["options"]}
        }
        for field in nodes if field["__typename"] == "ProjectV2SingleSelectField"
    }

def create_or_get_milestone(repo, headers):
    title = "Prototype"
    res = requests.post(f"{GITHUB_API_URL}/repos/{repo}/milestones", headers=headers, json={"title": title})
    if res.status_code == 201:
        print(f"✅ Milestone created: {title}")
        return res.json()["number"]
    elif res.status_code == 422:
        # Already exists—fetch it
        r = requests.get(f"{GITHUB_API_URL}/repos/{repo}/milestones", headers=headers)
        for m in r.json():
            if m["title"] == title:
                print(f"ℹ️ Using existing milestone: {title}")
                return m["number"]
    print("❌ Could not resolve milestone")
    return None

def main(config_dir):
    config = load_yaml("config.yaml", config_dir)
    cfg = config.get("create_project", {})
    secrets = load_yaml("secrets.yaml", config_dir)
    headers = {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }

    owner_id = get_user_id(headers)
    project_id = create_project(owner_id, cfg["project_title"], headers)

    field_ids = {}
    select_options = {}

    for field in cfg.get("custom_fields", []):
        name = field["name"]
        ftype = field["type"].upper()
        options = field.get("options", [])

        field_data = create_field(project_id, name, ftype, headers, options)
        field_ids[name] = field_data["id"]

        if ftype == "SINGLE_SELECT":
            select_options[name] = {opt["name"]: opt["id"] for opt in field_data["options"]}

    all_fields = get_field_option_ids(project_id, headers)
    status_info = all_fields.get("Status", {})

    repo = cfg["repo"]
    milestone_number = create_or_get_milestone(repo, headers)

    ids_data = {
        "project_id": project_id,
        "custom_fields": field_ids,
        "select_options": {
            **select_options,
            "status": status_info.get("options", {})
        },
        "status_field_id": status_info.get("field_id"),
        "milestone_number": milestone_number
    }

    save_yaml("ids.yaml", ids_data, config_dir)
    print("✅ Project setup complete. IDs saved to ids.yaml")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    main(args.config_dir)
