# scripts/create_project/create_project.py

import requests
import yaml
from pathlib import Path

GITHUB_API_URL = "https://api.github.com/graphql"
GITHUB_REST_URL = "https://api.github.com"

def load_config():
    root = Path(__file__).resolve().parents[1]
    with open(root / "config.yaml", "r") as f:
        return yaml.safe_load(f)["create_project"]

def load_token():
    root = Path(__file__).resolve().parents[1]
    with open(root / "secrets.yaml", "r") as f:
        secrets = yaml.safe_load(f)
    return {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }

def save_ids(data):
    root = Path(__file__).resolve().parents[1]
    ids_file = root / "ids.yaml"
    if ids_file.exists():
        with open(ids_file, "r") as f:
            current = yaml.safe_load(f)
    else:
        current = {}
    current.update(data)
    with open(ids_file, "w") as f:
        yaml.dump(current, f)

def get_user_or_org_id(login, headers):
    query = """
    query($login: String!) {
      user(login: $login) {
        id
      }
      organization(login: $login) {
        id
      }
    }
    """
    response = requests.post(GITHUB_API_URL, headers=headers, json={"query": query, "variables": {"login": login}})
    print("PROJECT CREATE RESPONSE:", response.status_code, response.text)
    print(response.status_code, response.text)
    data = response.json()["data"]
    return data["user"]["id"] if data["user"] else data["organization"]["id"]

def get_repo_node_id(repo, headers):
    url = f"{GITHUB_REST_URL}/repos/{repo}"
    response = requests.get(url, headers=headers)
    return response.json().get("node_id")

def link_project_to_repo(project_id, repo_node_id, headers):
    query = """
    mutation($input: LinkProjectV2ToRepositoryInput!) {
      linkProjectV2ToRepository(input: $input) {
        clientMutationId
      }
    }
    """
    variables = {
        "input": {
            "projectId": project_id,
            "repositoryId": repo_node_id
        }
    }
    response = requests.post(GITHUB_API_URL, headers=headers, json={"query": query, "variables": variables})
    print("PROJECT LINK RESPONSE:", response.status_code, response.text)
    return response.json()

def create_project(owner_id, title, description, headers):
    query = """
    mutation($input: CreateProjectV2Input!) {
      createProjectV2(input: $input) {
        projectV2 {
          id
        }
      }
    }
    """
    variables = {
        "input": {
            "ownerId": owner_id,
            "title": title,
        }
    }
    response = requests.post(GITHUB_API_URL, headers=headers, json={"query": query, "variables": variables})
    print("PROJECT CREATE RESPONSE:", response.status_code, response.text)
    return response.json()

def create_project_field(project_id, name, field_type, headers, options=None):
    mutation = """
    mutation($input: CreateProjectV2FieldInput!) {
        createProjectV2Field(input: $input) {
            projectV2Field {
                ... on ProjectV2FieldCommon {
                    id
                    name
                }
            }
        }
    }
    """

    input_data = {
        "projectId": project_id,
        "name": name,
        "dataType": field_type
    }
    if field_type == "SINGLE_SELECT" and options:
        input_data["singleSelectOptions"] = [
            {"name": opt, "description": "", "color": "GRAY"} for opt in options
        ]

    print("FIELD CREATE PAYLOAD:", input_data)
    response = requests.post(GITHUB_API_URL, headers=headers, json={"query": mutation, "variables": {"input": input_data}})
    print("FIELD CREATE RESPONSE:", response.status_code, response.text)
    return response.json()

def create_milestone(repo, title, headers):
    url = f"{GITHUB_REST_URL}/repos/{repo}/milestones"
    response = requests.post(url, headers=headers, json={"title": title})
    return response.json()

def create_release(repo, tag, name, body, milestone_number, headers):
    url = f"{GITHUB_REST_URL}/repos/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "target_commitish": "main"
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def main():
    cfg = load_config()
    headers = load_token()
    owner_login = cfg["repo"].split("/")[0]

    print("\n[1] Creating milestone...")
    milestone = create_milestone(cfg["repo"], cfg["milestone_title"], headers)
    print("Milestone created:", milestone.get("title"))

    print("\n[2] Creating release...")
    release = create_release(
        cfg["repo"],
        cfg["release_tag"],
        cfg["release_name"],
        cfg["release_description"],
        milestone.get("number"),
        headers
    )
    print("Release created:", release.get("tag_name"))

    print("\n[3] Getting owner ID...")
    owner_id = get_user_or_org_id(owner_login, headers)
    print("Owner ID:", owner_id)

    print("\n[4] Creating GitHub Project...")
    project = create_project(owner_id, cfg["project_title"], cfg["project_description"], headers)
    project_id = project["data"]["createProjectV2"]["projectV2"]["id"]
    print("Project created with ID:", project_id)

    print("\n[5] Linking project to repo...")
    repo_node_id = get_repo_node_id(cfg["repo"], headers)
    link_project_to_repo(project_id, repo_node_id, headers)

    field_ids = {}
    for field in cfg.get("custom_fields", []):
        name = field["name"]
        ftype = field["type"].upper()
        options = field.get("options")
        print(f"Adding field: {name} ({ftype})")
        result = create_project_field(project_id, name, ftype, headers, options)

        if "data" not in result:
            print("FIELD CREATE ERROR:", result)
            raise SystemExit("🛑 Failed to create field. See above.")

        field_id = result["data"]["createProjectV2Field"]["projectV2Field"]["id"]
        field_ids[name] = field_id

    save_ids({
        "milestone_id": milestone.get("id"),
        "release_id": release.get("id"),
        "project_id": project_id,
        "custom_fields": field_ids
    })
    print("\n✅ Project setup complete. IDs saved to ids.yaml")

if __name__ == "__main__":
    main()
