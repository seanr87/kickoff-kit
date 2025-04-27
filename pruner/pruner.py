#!/usr/bin/env python3
"""
pruner.py - Archives GitHub issues based on configurable criteria

This script tags GitHub issues with 'archive' label if they:
1. Have had 'Done' status for 2 weeks
2. Are 'Closed as not planned'

Configuration is loaded from kickoff-kit/config.yaml
"""

import os
import sys
import yaml
import datetime
import argparse
import logging
from github import Github
from dateutil.parser import parse
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pruner')

def load_config():
    """Load configuration from config.yaml file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        with open(config_path, 'r') as config_file:
            return yaml.safe_load(config_file)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        sys.exit(1)

def get_github_client(config):
    """Initialize GitHub client with token from config"""
    try:
        token = config.get('github', {}).get('token')
        if not token:
            logger.error("GitHub token not found in config")
            sys.exit(1)
        return Github(token)
    except Exception as e:
        logger.error(f"Failed to initialize GitHub client: {str(e)}")
        sys.exit(1)

def get_target_repo(github_client, config):
    """Get target repository object"""
    try:
        repo_url = config.get('github', {}).get('target_repo')
        if not repo_url:
            logger.error("Target repository URL not found in config")
            sys.exit(1)
            
        # Extract owner and repo name from URL
        # Handle different URL formats:
        # https://github.com/owner/repo
        # git@github.com:owner/repo.git
        if repo_url.startswith('https://'):
            parts = repo_url.rstrip('/').split('/')
            owner, repo_name = parts[-2], parts[-1]
        else:
            # Assuming SSH format
            parts = repo_url.split(':')[1].split('/')
            owner = parts[0]
            repo_name = parts[1].replace('.git', '')
            
        return github_client.get_repo(f"{owner}/{repo_name}")
    except Exception as e:
        logger.error(f"Failed to get repository: {str(e)}")
        sys.exit(1)

def is_done_for_two_weeks(issue, config):
    """Check if issue has been in 'Done' status for at least 2 weeks"""
    try:
        # Find the event where the issue was marked as 'Done'
        for event in issue.get_timeline():
            # Project card moved to Done column
            if (event.event == 'moved_columns_in_project' and 
                event.project_card and 
                event.project_card.column_name == 'Done'):
                # Calculate time difference
                moved_time = event.created_at
                current_time = datetime.now(moved_time.tzinfo)
                time_difference = current_time - moved_time
                return time_difference.days >= 14
                
        # If we didn't find a 'moved_columns_in_project' event to 'Done',
        # check if there's a 'done' label that has been applied more than 2 weeks ago
        done_label = config.get('github', {}).get('done_label', 'status: done')
        for label in issue.labels:
            if label.name.lower() == done_label.lower():
                # Try to find when this label was added
                for event in issue.get_timeline():
                    if event.event == 'labeled' and event.label.name.lower() == done_label.lower():
                        labeled_time = event.created_at
                        current_time = datetime.now(labeled_time.tzinfo)
                        time_difference = current_time - labeled_time
                        return time_difference.days >= 14
                        
        return False
    except Exception as e:
        logger.warning(f"Error checking 'Done' status for issue #{issue.number}: {str(e)}")
        return False

def is_closed_not_planned(issue, config):
    """Check if issue is closed as not planned"""
    try:
        # Check specifically for the "Closed as not planned" state
        for event in issue.get_timeline():
            # Look for state_change events specifically with "not planned" closed reason
            if event.event == 'closed' and hasattr(event, 'state_reason') and event.state_reason == 'not_planned':
                return True
                
        # Alternative check: Look for a specific label
        not_planned_label = config.get('github', {}).get('not_planned_label', 'Closed as not planned')
        
        for label in issue.labels:
            if label.name.lower() == not_planned_label.lower():
                return True
                
        # Also check for the closed state and closing comment that might indicate "not planned"
        if issue.state == 'closed':
            for event in issue.get_timeline():
                if (event.event == 'closed' or event.event == 'state_change') and hasattr(event, 'actor'):
                    # Check if there's a comment associated with the closure that mentions "not planned"
                    for comment_event in issue.get_timeline():
                        if (hasattr(comment_event, 'event') and comment_event.event == 'commented' and 
                            hasattr(comment_event, 'actor') and 
                            comment_event.actor.login == event.actor.login and
                            hasattr(comment_event, 'created_at') and 
                            abs((comment_event.created_at - event.created_at).total_seconds()) < 60 and
                            hasattr(comment_event, 'body') and 
                            'not planned' in comment_event.body.lower()):
                            return True
                
        return False
    except Exception as e:
        logger.warning(f"Error checking 'Not Planned' status for issue #{issue.number}: {str(e)}")
        return False

def should_archive_issue(issue, config):
    """Determine if an issue should be archived based on criteria"""
    # Skip issues that already have the archive label
    archive_label = config.get('github', {}).get('archive_label', 'archive')
    for label in issue.labels:
        if label.name.lower() == archive_label.lower():
            return False
            
    # Check archive criteria
    return (is_done_for_two_weeks(issue, config) or 
            is_closed_not_planned(issue, config))

def archive_issues(repo, config):
    """Add archive label to issues that meet archiving criteria"""
    try:
        # Get archive label name from config
        archive_label = config.get('github', {}).get('archive_label', 'archive')
        
        # Check if archive label exists, create if it doesn't
        try:
            label = repo.get_label(archive_label)
        except:
            # Create the label with a pale gray color
            repo.create_label(name=archive_label, color="e6e6e6", description="Archived issue")
            label = repo.get_label(archive_label)
            
        # Get issues to process based on config
        issues_to_check = config.get('github', {}).get('max_issues_to_check', 100)
        dry_run = config.get('github', {}).get('dry_run', False)
        
        # Count statistics
        total_checked = 0
        total_archived = 0
        
        # Get open and closed issues, sorted by updated
        for issue in repo.get_issues(state='all', sort='updated', direction='desc'):
            if total_checked >= issues_to_check:
                break
                
            total_checked += 1
            
            # Check if issue should be archived
            if should_archive_issue(issue, config):
                total_archived += 1
                
                if dry_run:
                    logger.info(f"Would archive issue #{issue.number}: {issue.title}")
                else:
                    logger.info(f"Archiving issue #{issue.number}: {issue.title}")
                    issue.add_to_labels(label)
                    
        logger.info(f"Checked {total_checked} issues, archived {total_archived} issues")
        return total_archived
        
    except Exception as e:
        logger.error(f"Error archiving issues: {str(e)}")
        return 0

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Archive GitHub issues based on criteria')
    parser.add_argument('--dry-run', action='store_true', help='Do not actually archive issues, just print what would be done')
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config()
        
        # Override dry_run from command line if specified
        if args.dry_run:
            if 'github' not in config:
                config['github'] = {}
            config['github']['dry_run'] = True
            
        # Initialize GitHub client
        github_client = get_github_client(config)
        
        # Get target repository
        repo = get_target_repo(github_client, config)
        
        # Archive issues
        archived_count = archive_issues(repo, config)
        
        # Success message
        if config.get('github', {}).get('dry_run', False):
            logger.info(f"Dry run completed. Would have archived {archived_count} issues.")
        else:
            logger.info(f"Successfully archived {archived_count} issues.")
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()