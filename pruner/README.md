# Pruner - GitHub Project Manager

Automatically manage GitHub Project boards by labeling — not deleting — old, irrelevant, or non-actionable Issues to keep boards clean and focused.

## 🌟 Features

- **No Issues are ever deleted**
- **Automatic labeling** of old or irrelevant Issues
- **Keeps Project boards clean** without manual intervention
- **Maintains audit logs** of all actions
- **Fully configurable** thresholds and rules
- **Workstream-aware** for better organization

## 📋 How It Works

Pruner automatically:

1. **Scans your GitHub Project** for all Issues and their metadata
2. **Applies labels** based on configurable rules:
   - `Not Planned`: Closed Issues with reason "not planned"
   - `Archive`: Issues in `Done` status for 2+ weeks (configurable)
   - `Archive`: Overflow Issues when more than 3 (configurable) are in `Done` per workstream
3. **Updates audit logs** on a Wiki page
4. **Preserves all data** while keeping active boards focused

## 🚀 Quick Start

1. **Clone this repository into your project**

   ```bash
   git clone https://github.com/username/pruner.git
   cd pruner
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Setup**

   ```bash
   python pruner.py --setup
   ```

   This will:
   - Prompt for your GitHub token (if not already set)
   - Detect your repository automatically
   - Find available GitHub Projects
   - Let you select which project to manage
   - Create a configuration file

4. **Run in Dry Run Mode First**

   ```bash
   python pruner.py --dry-run
   ```

   This will show what actions would be taken without actually applying any labels.

5. **Run for Real**

   ```bash
   python pruner.py
   ```

## ⚙️ Configuration

Pruner automatically creates a `.pruner.config` file with default settings. You can edit this file to customize the behavior:

```yaml
# GitHub Project ID to monitor (automatically detected)
project_id: "PVT_xxx"

# Number of days an issue must be in 'Done' before archiving
done_age_days: 14

# Maximum number of issues in 'Done' per workstream before overflow archiving
done_overflow_limit: 3

# Wiki page name for audit logging
wiki_page_name: "Pruner Audit Log"

# Set to true to test without applying labels
dry_run: true

# Repository information
repository: "owner/repo"

# Custom field configurations
custom_fields:
  # The ID or name of the custom "Workstream" field in your GitHub Project
  workstream_field_id: "Workstream"
  
  # Status field to identify "Done" items
  status_field_id: "Status"
  done_status_value: "Done"
```

## 🔄 Automation Options

### GitHub Actions

You can set up a GitHub Action to run Pruner on a schedule:

1. Create a file `.github/workflows/pruner.yml`:

```yaml
name: Pruner - Project Board Manager

on:
  schedule:
    # Run daily at midnight
    - cron: '0 0 * * *'
  workflow_dispatch:
    # Allow manual triggering
    inputs:
      dry-run:
        description: 'Run without applying labels (true/false)'
        required: false
        default: 'false'

jobs:
  prune-issues:
    runs-on: ubuntu-latest
    name: Prune GitHub Project Issues
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          
      - name: Run Pruner
        env:
          GITHUB_TOKEN: ${{ secrets.PRUNER_TOKEN }}
        run: |
          python pruner.py
```

2. Generate a Personal Access Token with `repo` and `project` permissions
3. Add it as a secret named `PRUNER_TOKEN` in your repository

## 📝 Audit Logs

Pruner maintains detailed logs of all actions in a Wiki page (default: "Pruner Audit Log"). This logs:

- Which Issues were labeled
- What labels were applied
- When the action was taken
- Why the action was taken

## 📄 Requirements

- Python 3.7+
- Packages: pyyaml, requests
- GitHub Personal Access Token with repo and project permissions

## 🔍 Command Line Options

```
python pruner.py [options]

Options:
  --setup        Run interactive setup process
  --dry-run      Run without applying labels
  --verbose      Show detailed logging information
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.