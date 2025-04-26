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

## 🚀 Usage

```bash
python pruner.py --config-dir <path_to_config_dir> --pruner-config <path_to_pruner_config> [--dry-run] [--verbose]
```

### Arguments:

- `--config-dir`: Directory containing secrets.yaml file with GitHub token
- `--pruner-config`: Path to pruner configuration file
- `--dry-run`: Run without applying any labels (optional)
- `--verbose`: Show detailed logging information (optional)

### Example:

```bash
python pruner.py --config-dir config --pruner-config .pruner.config --dry-run
```

## ⚙️ Configuration

Pruner uses two configuration files:

1. **secrets.yaml** - Contains GitHub authentication:
   ```yaml
   github_token: "your_github_personal_access_token"
   ```

2. **.pruner.config** - Contains Pruner settings:
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

## 📝 Audit Logs

Pruner maintains detailed logs of all actions in a Wiki page (default: "Pruner Audit Log"). This logs:

- Which Issues were labeled
- What labels were applied
- When the action was taken
- Why the action was taken

## 📄 Requirements

- Python 3.7+
- Packages: pyyaml, requests
- GitHub Personal Access Token with repo permissions

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📚 Documentation

For detailed setup instructions, see [SETUP.md](SETUP.md).

---

Part of the kickoff-kit repository for GitHub project management tools.