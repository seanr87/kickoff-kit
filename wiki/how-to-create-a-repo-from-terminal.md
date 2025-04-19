# How to Create a GitHub Repository from the Terminal

This guide walks you through creating a new GitHub repository using the GitHub CLI (`gh`).

## Step 1: Authenticate
If you haven't used `gh` before:

```bash
gh auth login
```

Follow the prompts to log in with GitHub.com and use HTTPS.

## Step 2: Create the Repository
To create a public repo and clone it immediately:

```bash
gh repo create my-repo-name --public --description "Short description of your project" --clone
```

Replace my-repo-name with whatever you want to call your repository.

## Step 3: Verify It Worked
After it's created, your terminal should automatically place you inside the cloned folder. Run:

```bash
ls
```

You should see README.md, .git/, and other project files if they were initialized.

## Notes
- Use --private if you don’t want the repo to be public
- Use --source=. --push to create a repo from existing files
- You can check your login status anytime with:
```bash
gh auth status
```
