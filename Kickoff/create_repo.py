# create_repo.py (Refactored for external config directory)

import subprocess
import yaml
from pathlib import Path

def load_config(config_dir):
    config_path = Path(config_dir) / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("create_repo", {})

def create_repo(repo_name, description="", private=False, auto_clone=False, working_dir=Path.cwd()):
    visibility = "--private" if private else "--public"
    command = [
        "gh", "repo", "create", repo_name,
        visibility,
        "--description", description
    ]
    if auto_clone:
        command.append("--clone")

    print(f"Creating repository: {repo_name}")
    subprocess.run(command, check=True, cwd=working_dir)
    # Auto-create .gitignore in the working directory
    gitignore_path = Path(working_dir) / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            "secrets.yaml\n.env\n*.csv\n__pycache__/\n*.pyc\n"
        )
        print("✅ .gitignore created.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True, help="Path to config directory")
    args = parser.parse_args()

    cfg = load_config(args.config_dir)
    create_repo(
        repo_name=cfg.get("repo_name"),
        description=cfg.get("description", ""),
        private=cfg.get("private", False),
        auto_clone=cfg.get("auto_clone", False),
        working_dir=Path(args.config_dir)
    )