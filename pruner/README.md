# Pruner - GitHub Project Manager

Automatically manage GitHub Project boards by labeling — not deleting — old, irrelevant, or non-actionable Issues to keep boards clean and focused.

## Key Features

- **No Issues are ever deleted**
- **Automatic labeling** of old or irrelevant Issues
- **Keeps Project boards clean** without manual intervention
- **Maintains audit logs** of all actions
- **Fully configurable** thresholds and rules
- **Workstream-aware** for better organization

## How It Works

Pruner automatically:

1. **Scans your GitHub Project** for all Issues and their metadata
2. **Applies labels** based on configurable rules:
   - `Not Planned`: Closed Issues with reason "not planned"
   - `Archive`: Issues in `Done` status for 2+ weeks (configurable)
   - `Archive`: Overflow Issues when more than 3 (configurable) are in `Done` per workstream
3. **Updates audit logs** on a Wiki page
4. **Preserves all data** while keeping active boards focused

## Using Pruner with Kickoff-Kit

When using Pruner as part of the kickoff-kit toolbox, all configuration is centralized in the parent repository's `config.yaml` and `secrets.yaml` files.

### Configuration Structure

The pruner tool expects the following file structure:

```
YourRepository/
├── config.yaml      <-- Contains pruner configuration
├── secrets.yaml     <-- Contains GitHub token
├── kickoff-kit/
│   ├── pruner/
│   │   ├── pruner.py   <-- Pruner script
│   │   └── ...
│   └── ...
└── ...
```

### Setup Instructions

1. **Clone kickoff-kit to your repository**:
   ```
   cd YourRepository
   git clone https://github.com/seanr87/kickoff-kit.git
   ```

2. **Set up your secrets.yaml file** in the root of your repository:
   ```yaml
   # secrets.yaml
   github_token: "your_github_personal_access_token"
   ```

3. **Add pruner configuration** to your config.yaml file:
   ```yaml
   # config.yaml
   pruner:
     project_id: "PVT_xxx"              # Your project ID
     repository: "owner/YourRepository"  # Target repository
     done_age_days: 14
     done_overflow_limit: 3
     wiki_page_name: Pruner - Project Board Manager

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
          pip install pyyaml requests
          
      - name: Run Pruner
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python kickoff-kit/pruner/pruner.py
```

## Troubleshooting

### Repository Detection Issues
If pruner is operating on the wrong repository, make sure your `config.yaml` has the correct repository specified:
```yaml
pruner:
  repository: "owner/YourRepository"  # This should be your target repository
```

You can also override the repository at runtime:
```
python kickoff-kit/pruner/pruner.py --repository owner/YourRepository
```

### Wiki Page Creation Errors
If you see errors about creating Wiki pages, you may need to:
1. Create the `.github` directory in your repository first
2. Or change the wiki_page_name in your config to a different location:
```yaml
pruner:
  wiki_page_name: "PRUNER_LOG.md"  # No directory prefix
```

### GitHub Token Permissions
Ensure your GitHub token has the following permissions:
- `repo` (Full control of private repositories)
- `project` (Full control of organization projects) ".github/PRUNER_LOG.md"
     dry_run: true                       # Set to false to apply labels
     custom_fields:
       workstream_field_id: "Workstream"
       status_field_id: "Status"
       done_status_value: "Done"
   ```

4. **Run the pruner setup** to configure or update your settings:
   ```
   cd YourRepository
   python kickoff-kit/pruner/pruner.py --setup
   ```

### Running Pruner

After setting up, you can run pruner at any time:

```
cd YourRepository
python kickoff-kit/pruner/pruner.py
```

#### Command Line Options

```
python kickoff-kit/pruner/pruner.py [options]

Options:
  --setup          Run interactive setup process
  --dry-run        Run without applying labels
  --verbose        Show detailed logging information
  --repository     Override target repository (format: owner/repo)
```

### Setting Up GitHub Actions

You can automate pruner with GitHub Actions. Create a file at `.github/workflows/pruner.yml`:

```yaml
name: