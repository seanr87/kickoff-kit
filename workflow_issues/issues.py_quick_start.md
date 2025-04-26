# 🚀 Quick Start

1. Prepare a CSV with at least a `title` column.
2. Ensure your GitHub Project has all needed custom fields and options already created.
3. Create a `secrets.yaml` with your `github_token`.
4. Run the script:

    ```bash
    python issues.py --config-dir <path> --csv <path> --repo-url <repo-url> --project-url <project-url> --confirm-live
    ```

5. Script will create Issues, assign them to the Project, and populate all fields.
6. Any missing fields or options will cause a fatal error with a clear message.

---
