# kickoff.py (Updated to support --config-dir for external project folders)

import argparse
from pathlib import Path
from create_repo import create_repo
from create_project import main as create_project_main
from import_issues import main as import_issues_main


def main():
    parser = argparse.ArgumentParser(description="Kickoff Kit: Setup GitHub repo, project, and issues.")
    parser.add_argument("--repo", action="store_true", help="Create the GitHub repository")
    parser.add_argument("--project", action="store_true", help="Create the GitHub project + milestone + release + fields")
    parser.add_argument("--issues", action="store_true", help="Import issues from CSV into the project")
    parser.add_argument("--config-dir", type=str, required=True, help="Path to folder containing config.yaml, secrets.yaml, ids.yaml")
    args = parser.parse_args()

    config_dir = Path(args.config_dir).resolve()

    if not any([args.repo, args.project, args.issues]):
        print("No flags passed. Running all steps.")
        args.repo = args.project = args.issues = True

    if args.repo:
        print("Step 1: Creating repository...")
        from create_repo import load_config
        cfg = load_config(config_dir)
        create_repo(
            repo_name=cfg.get("repo_name"),
            description=cfg.get("description", ""),
            private=cfg.get("private", False),
            auto_clone=cfg.get("auto_clone", False),
            working_dir=config_dir
        )

    if args.project:
        print("Step 2: Creating project, milestone, release, fields...")
        create_project_main(config_dir)

    if args.issues:
        print("Step 3: Importing issues...")
        import_issues_main(config_dir)

    print("\n\u2705 Kickoff complete.")


if __name__ == "__main__":
    main()
