# Pruner Setup and Testing Guide

This guide will walk you through setting up and testing the Pruner tool, which is part of the kickoff-kit repository.

## Prerequisites

- Python 3.7 or higher
- pip package manager
- A GitHub account with a Personal Access Token (PAT) with repo permissions
- A GitHub Project to test with

## Setup Instructions

### 1. Install Dependencies

From the root directory, install the required dependencies:

```bash
pip install -r requirements.txt
```

If you don't have a requirements.txt file, you can install the dependencies directly:

```bash
pip install pyyaml requests
```

### 2. Create Configuration Files

#### Create Secrets File

Create a `secrets.yaml` file in your configuration directory:

```bash
mkdir -p config
touch config/secrets.yaml
```

Edit `config/secrets.yaml` to include your GitHub token:

```yaml
# GitHub authentication
github_token: "your_github_personal_access_token"  # Replace with your actual token
```

#### Create Pruner Configuration

Create a `.pruner.config` file:

```bash
touch .pruner.config
```

Edit `.pruner.config` with your project settings:

```yaml
# GitHub Project ID to monitor
project_id: "PVT_xxx"  # Replace with your actual project ID

# Number of days an issue must be in 'Done' before archiving
done_age_days: 14

# Maximum number of issues in 'Done' per workstream before overflow archiving
done_overflow_limit: 3

# Wiki page name for audit logging
wiki_page_name: "Pruner Audit Log"

# Set to true to test without applying labels
dry_run: true

# Custom field configurations
custom_fields:
  # The ID or name of the custom "Workstream" field in your GitHub Project
  workstream_field_id: "Workstream"
  
  # Status field to identify "Done" items
  status_field_id: "Status"
  done_status_value: "Done"
```

## Finding Your Project Information

### Identifying Your Project ID

1. Go to your GitHub Project
2. Look at the URL:
   - For organization projects: `https://github.com/orgs/YOUR-ORG/projects/NUMBER`
   - For user projects: `https://github.com/users/YOUR-USERNAME/projects/NUMBER`
3. In the browser's developer tools console, you can run:
   ```javascript
   document.querySelector('meta[name="octolytics-dimension-project_id"]').content
   ```
   This will return the project ID in the format `PVT_xxx`

### Finding Custom Field Names

To find the exact names of custom fields in your project, you can run Pruner with the `--verbose` flag:

```bash
python pruner.py --config-dir config --pruner-config .pruner.config --verbose --dry-run
```

This will display all field names found in your project, which you can then use to update your configuration.

## Testing Pruner

### 1. Run in Dry Run Mode

Always start with a dry run to see what actions would be taken without actually modifying any issues:

```bash
python pruner.py --config-dir config --pruner-config .pruner.config --dry-run
```

This will:
- Load your configuration
- Connect to your GitHub Project 
- Scan all issues
- Identify issues that would be labeled
- Print a report of actions that would be taken

### 2. Run with Real Labels

Once you've verified that the dry run works correctly, you can run with real labeling by:

1. Updating your `.pruner.config` file to set `dry_run: false`, or
2. Running without the `--dry-run` flag:

```bash
python pruner.py --config-dir config --pruner-config .pruner.config
```

**CAUTION**: This will actually apply labels to your issues. Make sure you're using a test project or are prepared for the changes.

## Troubleshooting

### Common Issues and Solutions

#### Authentication Errors

If you see errors like "Bad credentials" or "Resource not accessible":

1. Check that your GitHub token has the necessary permissions
2. Verify that your token is correctly set in the `secrets.yaml` file
3. Try generating a new token if needed

#### Project Not Found

If you see "Project not found" or similar errors:

1. Double-check your Project ID
2. Ensure you have access to the project
3. Verify your token has access to the repository and project

#### Custom Field Errors

If you see errors related to custom fields:

1. Run with the `--verbose` flag to see the exact field names in your project
2. Update your `.pruner.config` with the correct field names

## Integration with Automation

To run Pruner automatically on a schedule:

### GitHub Actions

Create a workflow file `.github/workflows/pruner.yml`:

```yaml
name: Pruner - Project Board Manager

on:
  schedule:
    - cron: '0 0 * * *'  # Run daily at midnight
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Run without applying labels'
        required: false
        type: boolean
        default: false

jobs:
  prune-issues:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pyyaml requests

      - name: Create config directory
        run: mkdir -p config

      - name: Create secrets file
        run: |
          echo "github_token: ${{ secrets.GITHUB_TOKEN }}" > config/secrets.yaml

      - name: Run Pruner
        run: |
          python pruner.py --config-dir config --pruner-config .pruner.config ${{ inputs.dry_run && '--dry-run' || '' }}
```

## Next Steps

After successfully setting up and testing Pruner, consider:

1. Fine-tuning the configuration based on your team's needs
2. Creating custom views in your GitHub Project that exclude Archive/Not Planned issues
3. Setting up scheduled runs to keep your boards clean automatically