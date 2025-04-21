import requests
import yaml
from pathlib import Path

GITHUB_API_URL = "https://api.github.com/graphql"
GITHUB_REST_URL = "https://api.github.com"

def load_config(config_dir):
    with open(Path(config_dir) / "config.yaml", "r") as f:
        return yaml.safe_load(f)["create_project"]

def load_token(config_dir):
    with open(Path(config_dir) / "secrets.yaml", "r") as f:
        secrets = yaml.safe_load(f)
    return {
        "Authorization": f"Bearer {secrets['github_token']}",
        "Accept": "application/vnd.github+json"
    }

def save_ids(data, config_dir):
    path = Path(config_dir) / "ids.yaml"
    if path.exists():
        with open(path, "r") as f:
            current = yaml.safe_load(f)
    else:
        current = {}
    current.update(data)
    with open(path, "w") as f:
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

# create_project.py (Updated for multi-milestone)

# [keep all existing imports/functions as-is except for main() below]

def main(config_dir):
    cfg = load_config(config_dir)
    headers = load_token(config_dir)
    owner_login = cfg["repo"].split("/")[0]

    # 1. Create all milestones
    print("\n[1] Creating milestones...")
    milestone_ids = {}
    default_milestone = None
    for m in cfg.get("milestones", []):
        milestone = create_milestone(cfg["repo"], m["name"], headers)
        print("Milestone created:", milestone.get("title"))
        milestone_ids[m["name"]] = milestone.get("number")
        if m.get("default", False):
            default_milestone = milestone.get("number")

    # 2. Create release (linked to default milestone)
    print("\n[2] Creating release...")
    release = create_release(
        cfg["repo"],
        cfg["release_tag"],
        cfg["release_name"],
        cfg["release_description"],
        default_milestone,
        headers
    )
    print("Release created:", release.get("tag_name"))

    # 3. Create project and fields
    print("\n[3] Getting owner ID...")
    owner_id = get_user_or_org_id(owner_login, headers)

    print("\n[4] Creating GitHub Project...")
    project = create_project(owner_id, cfg["project_title"], cfg["project_description"], headers)
    project_id = project["data"]["createProjectV2"]["projectV2"]["id"]
    print("Project created with ID:", project_id)

    print("\n[5] Linking project to repo...")
    repo_node_id = get_repo_node_id(cfg["repo"], headers)
    link_project_to_repo(project_id, repo_node_id, headers)

    # Create fields
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
        field_ids[name] = result["data"]["createProjectV2Field"]["projectV2Field"]["id"]

    # Save all identifiers
    save_ids({
        "milestone_id": default_milestone,
        "milestone_ids": milestone_ids,
        "release_id": release.get("id"),
        "project_id": project_id,
        "custom_fields": field_ids
    }, config_dir)
    print("\n✅ Project setup complete. IDs saved to ids.yaml")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    args = parser.parse_args()
    main(args.config_dir)
