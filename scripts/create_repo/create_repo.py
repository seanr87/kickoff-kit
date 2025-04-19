# scripts/create_repo/create_repo.py

"""
Create a GitHub repository using the GitHub CLI.
Reads config from the root-level config.yaml file.
"""

import subprocess
import yaml
from pathlib import Path

def load_config():
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("create_repo", {})

def create_repo(repo_name, description="", private=False, auto_clone=False):
    visibility = "--private" if private else "--public"
    command = [
        "gh", "repo", "create", repo_name,
        visibility,
        "--description", description
    ]
    if auto_clone:
        command.append("--clone")

    print(f"Creating repository: {repo_name}")
    subprocess.run(command, check=True)

if __name__ == "__main__":
    cfg = load_config()
    create_repo(
        repo_name=cfg.get("repo_name"),
        description=cfg.get("description", ""),
        private=cfg.get("private", False),
        auto_clone=cfg.get("auto_clone", False)
    )
