import requests
import yaml
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"

def load_yaml(filename, config_dir):
    with open(Path(config_dir) / filename, "r") as f:
        return yaml.safe_load(f)

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


def create_view(project_id, name, layout, group_by_field_id, headers):
    variables = {
        "input": {
            "projectId": project_id,
            "name": name,
            "layout": layout
        }
    }

    if layout == "BOARD" and group_by_field_id:
        variables["input"]["groupByFieldId"] = group_by_field_id

    payload = {
        "query": """
        mutation($input: CreateProjectV2ViewInput!) {
          createProjectV2View(input: $input) {
            projectV2View {
              id
              name
            }
          }
        }
        """,
        "variables": variables
    }

    response = requests.post(GRAPHQL_URL, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"✅ Created view: {name}")
    else:
        print(f"❌ Failed to create view: {name}")
        print(response.text)

def main(config_dir):
    config = load_yaml("config.yaml", config_dir)
    secrets = load_yaml("secrets.yaml", config_dir)
    ids = load_yaml("ids.yaml", config_dir)

    headers = {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }

    project_id = ids.get("project_id")
    all_fields = get_field_option_ids(project_id, headers)

    workstream_id = all_fields.get("workstream", {}).get("field_id")
    priority_id = all_fields.get("priority", {}).get("field_id")

    create_view(project_id, "Roadmap", "LIST", None, headers)
    create_view(project_id, "Kanban", "BOARD", workstream_id, headers)
    create_view(project_id, "Backlog", "BOARD", priority_id, headers)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    main(args.config_dir)
