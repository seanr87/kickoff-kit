# Pruner

Pruner is a tool for automatically tagging GitHub issues as 'archive' based on specific criteria.

## Overview

The `pruner.py` script helps manage your GitHub repository by automatically adding an 'archive' label to issues that meet either of these conditions:

1. Have had 'Done' status for 2 weeks or more
2. Are closed as 'not planned'

This helps maintain a clean project board by identifying issues that can be archived.

## Installation

Pruner is included as part of the kickoff-kit. No additional installation is required after cloning the kickoff-kit repository.

## Requirements

- Python 3.6+
- PyGithub library
- PyYAML library
- python-dateutil library

To install required dependencies:

```bash
pip install PyGithub PyYAML python-dateutil
```

## Configuration

Pruner is configured through the main `kickoff-kit/config.yaml` file. The following options are available under the `github` section:

```yaml
github:
  # Required: Your GitHub personal access token with repo scope
  token: "your-github-token"
  
  # Required: URL of the target repository
  target_repo: "https://github.com/owner/repo"
  
  # Optional: Label name that indicates an issue is done
  # Default: "status: done"
  done_label: "status: done" 
  
  # Optional: Label name that indicates an issue is closed as not planned
  # Default: "closed: not planned"
  not_planned_label: "closed: not planned"
  
  # Optional: Name of the archive label to apply
  # Default: "archive"
  archive_label: "archive"
  
  # Optional: Maximum number of most recently updated issues to check
  # Default: 100
  max_issues_to_check: 100
  
  # Optional: If true, don't actually apply labels, just log what would happen
  # Default: false
  dry_run: false
```

## Usage

Run pruner from the `kickoff-kit/pruner` directory:

```bash
cd kickoff-kit/pruner
python pruner.py
```

### Command Line Options

- `--dry-run`: Perform a dry run without actually applying labels. Useful for testing.

Example:
```bash
python pruner.py --dry-run
```

## How It Works

1. The script loads configuration from `config.yaml`
2. It connects to GitHub using your personal access token
3. It retrieves issues from your repository, sorted by most recently updated
4. For each issue, it checks:
   - If the issue has been in 'Done' status for 2+ weeks
   - If the issue is closed and has the 'not planned' label
5. If either condition is met and the issue doesn't already have the archive label:
   - It adds the configured archive label to the issue
   - It logs the action taken

The script identifies 'Done' status by:
- Looking for issues moved to a 'Done' column in a project board, or
- Looking for issues with the configured 'done' label

## Logging

Pruner logs its actions to the console with timestamps. The logs include:
- Configuration loading
- Issues being archived
- Errors encountered
- Summary of actions taken

## Examples

### Standard Run

```bash
python pruner.py
```

Output:
```
2025-04-27 10:00:00 - pruner - INFO - Archiving issue #42: Fix login button
2025-04-27 10:00:01 - pruner - INFO - Archiving issue #37: Update documentation
2025-04-27 10:00:02 - pruner - INFO - Checked 100 issues, archived 2 issues
2025-04-27 10:00:02 - pruner - INFO - Successfully archived 2 issues.
```

### Dry Run

```bash
python pruner.py --dry-run
```

Output:
```
2025-04-27 10:05:00 - pruner - INFO - Would archive issue #42: Fix login button
2025-04-27 10:05:01 - pruner - INFO - Would archive issue #37: Update documentation
2025-04-27 10:05:02 - pruner - INFO - Checked 100 issues, archived 2 issues
2025-04-27 10:05:02 - pruner - INFO - Dry run completed. Would have archived 2 issues.
```

## Troubleshooting

- **Authentication Errors**: Ensure your GitHub token is valid and has the 'repo' scope
- **Permission Errors**: Verify you have write access to the target repository
- **Label Not Found**: The script will automatically create the archive label if it doesn't exist
- **Missing Dependencies**: Ensure all required Python packages are installed
- **SSL Errors**: Check your network connection and proxy settings

