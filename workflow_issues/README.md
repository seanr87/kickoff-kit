# GitHub Issues Creator

An interactive tool for bulk creating GitHub Issues from CSV files with proper Project field assignment.

## Features

- Analyze CSV files and GitHub Projects to identify fields and options
- Interactive prompts for creating missing fields and options
- Create a sample issue for verification before bulk creation
- Automatically populate custom fields in GitHub Projects
- Proper handling of standard fields (title, body, assignees, labels, milestone)
- Support for custom fields with dynamic option creation

## Project Structure

```
.
├── issues.py              # Main orchestrator script
├── issues/                # Supporting modules
│   ├── __init__.py        # Package initialization
│   ├── analyzer.py        # CSV and Project analysis
│   ├── creator.py         # Issue and field creation
│   └── validator.py       # Input validation
└── secrets.yaml           # Configuration file (not included)
```

## Requirements

- Python 3.6+
- GitHub Personal Access Token with appropriate permissions:
  - `repo` - Full control of private repositories
  - `project` - Full control of organization projects
  - `admin:org` - Full control of orgs and teams (if using organization projects)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/github-issues-creator.git
   cd github-issues-creator
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install requests pyyaml
   ```

3. Create a `secrets.yaml` file with your GitHub token:
   ```yaml
   github_token: ghp_your_token_here
   ```

## CSV Format

Your CSV file should include at minimum a `title` column. Additional supported columns:

- `body` - Issue description
- `assignees` - Comma-separated list of GitHub usernames
- `labels` - Comma-separated list of label names
- `milestone` - Milestone name
- `status` - Status value for the Project board

Any other columns will be treated as custom fields for the GitHub Project.

Example CSV:
```csv
title,body,status,workstream,milestone
Fix login bug,Users can't login on mobile devices,To Do,Backend,May 2025
Update docs,Documentation needs to be updated,In Progress,Documentation,May 2025
```

## Usage

Run the script with required parameters:

```bash
python issues.py --config-dir ./config --csv ./issues.csv --repo-url https://github.com/owner/repo --project-url https://github.com/orgs/owner/projects/1
```

The script will:
1. Analyze the CSV and GitHub Project structure
2. Provide interactive prompts for field creation/modification
3. Create a sample issue for verification
4. Ask for confirmation before bulk creation
5. Create all issues with proper field values

## Command Line Arguments

- `--config-dir`: Directory containing the secrets.yaml file
- `--csv`: Path to the CSV file with issue data
- `--repo-url`: GitHub repository URL (format: https://github.com/owner/repo)
- `--project-url`: GitHub project URL (format: https://github.com/orgs/owner/projects/number)

## License

MIT