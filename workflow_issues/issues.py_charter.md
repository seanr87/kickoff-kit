# issues.py Charter

## Purpose
Provide an interactive tool to automate GitHub issue creation and project field population based on a simple CSV file, with appropriate user feedback and confirmation steps throughout the process.

## CSV provides content and configuration
The CSV file is not just providing Issue content, but also providing configuration. Our script needs to assess the CSV headers and values. Some must be recognized as requiring their own unique metadata import strategy (e.g., milestone). Others will be assumed to be custom fields: we must ensure that custom fields exist (create them if not) and that the options for said custom fields (as declared in the CSV) also exist (create them if not).

## Project Structure
- **issues.py**: Main orchestrator script that manages the workflow and user interaction
- **issues/**: Directory containing supporting modules:
  - **analyzer.py**: Analyzes CSV and GitHub Project structure
  - **creator.py**: Handles creation of issues and fields
  - **validator.py**: Validates configurations and settings

## Interactive Workflow
1. User runs the main script:
   ```bash
   python issues.py --config-dir <path> --csv <path> --repo-url <repo-url> --project-url <project-url>
   ```

2. The script performs analysis and provides interactive prompts:
   - Acknowledges CSV column headers that can be populated without creation
   - For fields that need to be created, asks user for confirmation before creating
   - When a field exists but an option doesn't, prompts user to add the option manually and confirm completion

3. The script creates one sample issue and asks for user confirmation before proceeding with the full import

4. Upon confirmation, the script proceeds with creating all issues and populating fields

## Requirements
- **CSV File:** must include at minimum a `title` column.
- **Standard Columns Supported:** `title`, `body`, `assignees`, `labels`, `milestone`, `status`.
- **Custom Field Support:**
  - Custom fields (e.g., `Workstream`) will be created after user confirmation if they don't exist
  - Custom field options must be created manually when prompted by the script
- **Field/Option Creation:**
  - Missing fields → Prompt user for creation or manual addition
  - Missing options → Prompt user to add manually and confirm when done
- **Status Handling:**
  - Status is treated as a special built-in Project V2 field
  - Status field ID is dynamically detected and updated separately
- **Secrets File:**
  - `secrets.yaml` must exist and contain `github_token`
- **Error Handling:**
  - Clear error messages with helpful prompts for resolution
  - Graceful termination with appropriate feedback if issues are encountered

## User Experience
The script prioritizes user feedback and interaction:
- Clear indications of what's being analyzed and created
- Explicit prompts for user confirmation at critical steps
- Opportunity to confirm sample issue before bulk creation
- Graceful handling of interruptions or errors

## Expected Outcome
A more robust and user-friendly process for bulk issue creation that:
- Minimizes manual setup through automation where possible
- Provides clear guidance when manual intervention is needed
- Ensures correct field creation and linking to Project V2
- Gives users confidence and control throughout the process