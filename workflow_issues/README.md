# GitHub Issues CSV Importer

A streamlined tool for creating GitHub Issues from CSV data and synchronizing custom fields with GitHub Projects.

## Overview

This tool automates the process of creating GitHub Issues from structured CSV data while preserving all field relationships by mapping them to GitHub Projects fields. It handles standard issue fields, custom fields, and field options with minimal user intervention.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/seanr87/kickoff-kit
   cd kickoff-kit
   ```

2. Create a configuration directory with a `secrets.yaml` file:
   ```yaml
   # secrets.yaml
   github_token: your_github_personal_access_token
   ```

   > **Note**: Your GitHub token needs permissions for repository and project access.

## CSV Format

Your CSV file must include a `title` column and can contain the following:

### Standard Fields
- `title` (required): The issue title
- `body`: The issue description 
- `assignees`: Comma-separated usernames
- `labels`: Comma-separated label names
- `milestone`: Milestone name
- `status`: Project status (Todo, In Progress, Done, etc.)

### Custom Fields
Any additional columns will be treated as custom fields and synchronized with your GitHub Project.

### Date Fields
The following fields are automatically handled as date fields:
- `end date`
- `due date`
- `start date`
- `deadline`

## Usage

Run the tool with the following command:

```
python issues.py --config-dir ./config --csv ./issues.csv --repo-url https://github.com/owner/repo --project-url https://github.com/orgs/owner/projects/1
```

### Parameters

- `--config-dir`: Directory containing the secrets.yaml file
- `--csv`: Path to your CSV file with issue data
- `--repo-url`: GitHub repository URL where issues will be created
- `--project-url`: GitHub project URL where issues will be added

## Workflow

1. **Validation**: The tool validates your CSV file format and GitHub URLs
2. **Analysis**: The tool analyzes your CSV fields and the GitHub Project structure
3. **Field Creation**: You'll be prompted to confirm creation of any missing fields
4. **Sample Issue**: A sample issue is created for verification
5. **Confirmation**: You confirm whether to proceed with creating all issues
6. **Bulk Creation**: All remaining issues are created and added to the project

## Troubleshooting

- Ensure your GitHub token has sufficient permissions
- Verify that your CSV file contains a "title" column
- For custom fields with many options, consider adding them manually in the GitHub UI
- Check that your repository and project URLs are correctly formatted

## Limitations

- Maximum of 50 options per custom field (GitHub limitation)
- Field and option names must be 50 characters or less
- The tool cannot modify existing fields, only add new ones

## License

[MIT License](LICENSE)
