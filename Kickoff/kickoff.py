# Kickoff/kickoff.py

import argparse
from create_repo import create_repo, load_config as load_repo_config
from create_project import main as create_project_main
from import_issues import main as import_issues_main

def main():
    parser = argparse.ArgumentParser(description="Kickoff Kit: Setup GitHub repo, project, and issues.")
    parser.add_argument("--repo", action="store_true", help="Create the GitHub repository")
    parser.add_argument("--project", action="store_true", help="Create the GitHub project + milestone + release + fields")
    parser.add_argument("--issues", action="store_true", help="Import issues from CSV into the project")
    args = parser.parse_args()

    if not any([args.repo, args.project, args.issues]):
        print("ℹ️ No flags passed. Running all steps.")
        args.repo = args.project = args.issues = True

    if args.repo:
        print("\n🚀 Step 1: Creating repository...")
        cfg = load_repo_config()
        create_repo(
            repo_name=cfg.get("repo_name"),
            description=cfg.get("description", ""),
            private=cfg.get("private", False),
            auto_clone=cfg.get("auto_clone", False)
        )

    if args.project:
        print("\n📦 Step 2: Creating project, milestone, release, fields...")
        create_project_main()

    if args.issues:
        print("\n🐛 Step 3: Importing issues...")
        import_issues_main()

    print("\n✅ Kickoff complete.")

if __name__ == "__main__":
    main()
