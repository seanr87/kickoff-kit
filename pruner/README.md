# Pruner - GitHub Project Manager

Automatically manage GitHub Project boards by labeling — not deleting — old, irrelevant, or non-actionable Issues to keep boards clean and focused.

## 🌟 Features

- **No Issues are ever deleted**
- **Automatic labeling** of old or irrelevant Issues
- **Keeps Project boards clean** without manual intervention
- **Maintains audit logs** of all actions
- **Fully configurable** thresholds and rules

## 📋 How It Works

Pruner automatically:

1. **Scans your GitHub Project** for all Issues and their metadata
2. **Applies labels** based on configurable rules:
   - `Not Planned`: Closed Issues with reason "not planned"
   - `Archive`: Issues in `Done` status for 2+ weeks (configurable)
   - `Archive`: Overflow Issues when more than 3 (configurable) are in `Done` per workstream
3. **Updates audit logs** on a Wiki page
4. **Preserves all data** while keeping active boards focused

## 🚀 Installation

### Option 1: Use from GitHub Marketplace

1. Go to [GitHub Marketplace](https://github.com/marketplace) and search for "Pruner"
2. Click "Install it for free"
3. Configure the repositories where you want to use Pruner

### Option 2: Add to Your Repository

Add this to your repository's `.github/workflows/pruner.yml`:

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

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          
      - name: Load configuration
        id: config
        run: |
          if [ -f .pruner-config.yml ]; then
            echo "::set-output name=config::$(cat .pruner-config.yml | base64 -w 0)"
          else
            echo "::set-output name=config::$(echo '{
              "project_id": ${{ github.event.repository.projects.0.id }},
              "done_age_days": 14,
              "done_overflow_limit": 3,
              "wiki_page_name": "Pruner Audit Log",
              "dry_run": ${{ github.event.inputs.dry-run || false }}
            }' | base64 -w 0)"
          fi

      - name: Run Pruner
        uses: your-org/pruner-action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          config-base64: ${{ steps.config.outputs.config }}
```

## ⚙️ Configuration

Create a `.pruner-config.yml` file in your repository root:

```yaml
# GitHub Project ID to monitor
project_id: 7  # Replace with your actual project ID

# Number of days an issue must be in 'Done' before archiving
done_age_days: 14

# Maximum number of issues in 'Done' per workstream before overflow archiving
done_overflow_limit: 3

# Wiki page name for audit logging
wiki_page_name: "Pruner Audit Log"

# Set to true to test without applying labels
dry_run: false

# Custom workstream identification
# By default, workstreams are identified by labels
workstream_mapping:
  "Frontend": ["Frontend", "UI", "UX"]
  "Backend": ["Backend", "API", "Database"]
```

### Finding Your Project ID

To find your GitHub Project ID:

1. Go to your project board
2. Look at the URL: `https://github.com/orgs/YOUR-ORG/projects/NUMBER` or `https://github.com/users/YOUR-USERNAME/projects/NUMBER`
3. The `NUMBER` at the end is your Project ID

## 🔄 Usage

Pruner runs automatically based on your schedule configuration (daily by default). You can also trigger it manually from the Actions tab in your repository.

### Manual Run

1. Go to your repository on GitHub
2. Click the "Actions" tab
3. Select "Pruner - Project Board Manager" from the workflow list
4. Click "Run workflow"
5. Select "Run workflow"

### Dry Run Mode

To test Pruner without applying any labels:

1. Follow the Manual Run steps above
2. Select "true" for the "Run without applying labels" option before running

## 📝 Audit Logs

Pruner maintains detailed logs of all actions in a Wiki page (default: "Pruner Audit Log"). This logs:

- Which Issues were labeled
- What labels were applied
- When the action was taken
- Why the action was taken

## 🛠️ Troubleshooting

### Common Issues

**Problem**: Labels aren't being applied
**Solution**: Check that your GitHub token has sufficient permissions and that the Project ID is correct

**Problem**: Wiki page isn't being updated
**Solution**: Ensure that Wiki is enabled for your repository and that your token has Wiki write access

### Getting Help

If you encounter any issues:

1. Check the Action run logs for error messages
2. Review the [GitHub Actions documentation](https://docs.github.com/en/actions)
3. Open an issue in this repository

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Made with ❤️ by [Your Organization]