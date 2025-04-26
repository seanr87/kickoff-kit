const { Octokit } = require('@octokit/rest');
const { createAppAuth } = require('@octokit/auth-app');
const yaml = require('js-yaml');
const core = require('@actions/core');
const github = require('@actions/github');

/**
 * Pruner - GitHub Project Board Manager
 * 
 * This script automatically manages GitHub Project boards by labeling
 * old, irrelevant, or non-actionable Issues to keep boards clean.
 */
async function run() {
  try {
    // Get inputs
    const githubToken = core.getInput('github-token', { required: true });
    const configBase64 = core.getInput('config-base64', { required: true });
    
    // Parse configuration
    const config = JSON.parse(Buffer.from(configBase64, 'base64').toString());
    console.log('Configuration loaded:', JSON.stringify(config, null, 2));
    
    // Initialize GitHub client
    const octokit = new Octokit({
      auth: githubToken
    });
    
    const context = github.context;
    const repo = context.repo;
    
    // 1. Scan GitHub Project
    console.log(`Scanning project ID: ${config.project_id}`);
    
    // Get project data (Note: Using GraphQL API as REST API doesn't fully support Projects)
    const projectData = await getProjectData(octokit, config.project_id);
    
    // Extract all issues from the project
    const issues = await getProjectIssues(octokit, projectData, repo);
    console.log(`Found ${issues.length} issues in the project`);
    
    // Track actions for audit logging
    const actions = [];
    
    // 2. Apply Labels
    if (!config.dry_run) {
      // Apply "Not Planned" labels
      const notPlannedIssues = issues.filter(issue => 
        issue.closed && issue.closedReason === 'not_planned');
      
      console.log(`Found ${notPlannedIssues.length} issues to label as 'Not Planned'`);
      
      for (const issue of notPlannedIssues) {
        await applyLabel(octokit, repo, issue.number, 'Not Planned');
        actions.push({
          issue: issue.number,
          action: 'Applied label: Not Planned',
          reason: 'Closed with reason "not planned"',
          timestamp: new Date().toISOString()
        });
      }
      
      // Apply "Archive" labels based on "Done" status for 2+ weeks
      const twoWeeksAgo = new Date();
      twoWeeksAgo.setDate(twoWeeksAgo.getDate() - config.done_age_days);
      
      const oldDoneIssues = issues.filter(issue => 
        issue.status === 'Done' && 
        new Date(issue.updatedAt) < twoWeeksAgo);
      
      console.log(`Found ${oldDoneIssues.length} issues to archive (Done for ${config.done_age_days}+ days)`);
      
      for (const issue of oldDoneIssues) {
        await applyLabel(octokit, repo, issue.number, 'Archive');
        actions.push({
          issue: issue.number,
          action: 'Applied label: Archive',
          reason: `In 'Done' status for more than ${config.done_age_days} days`,
          timestamp: new Date().toISOString()
        });
      }
      
      // Apply "Archive" labels for overflow in "Done" per workstream
      const workstreams = {};
      
      // Group issues by workstream
      for (const issue of issues) {
        if (issue.status === 'Done') {
          // Use labels as workstreams, could be customized based on your workflow
          for (const label of issue.labels || []) {
            if (!workstreams[label]) {
              workstreams[label] = [];
            }
            workstreams[label].push({
              number: issue.number,
              updatedAt: issue.updatedAt
            });
          }
        }
      }
      
      // Process each workstream for overflow
      for (const [workstream, workstreamIssues] of Object.entries(workstreams)) {
        if (workstreamIssues.length > config.done_overflow_limit) {
          // Sort by updated date (oldest first)
          workstreamIssues.sort((a, b) => 
            new Date(a.updatedAt) - new Date(b.updatedAt));
          
          // Archive the oldest issues beyond the limit
          const toArchive = workstreamIssues.slice(0, 
            workstreamIssues.length - config.done_overflow_limit);
          
          console.log(`Found ${toArchive.length} overflow issues to archive in workstream: ${workstream}`);
          
          for (const issue of toArchive) {
            await applyLabel(octokit, repo, issue.number, 'Archive');
            actions.push({
              issue: issue.number,
              action: 'Applied label: Archive',
              reason: `Overflow in 'Done' status for workstream '${workstream}'`,
              timestamp: new Date().toISOString()
            });
          }
        }
      }
    } else {
      console.log('Dry run mode - no labels will be applied');
      // Calculate what would be labeled in dry run mode
      // ... (similar logic as above but just logging)
    }
    
    // 3. Update Project Board Filters
    if (!config.dry_run) {
      await updateProjectFilters(octokit, config.project_id);
    }
    
    // 4. Update Audit Log
    if (actions.length > 0) {
      await updateAuditLog(octokit, repo, config.wiki_page_name, actions);
    }
    
    console.log('Pruner completed successfully');
  } catch (error) {
    core.setFailed(`Action failed: ${error.message}`);
    console.error(error);
  }
}

/**
 * Get project data using GraphQL API
 */
async function getProjectData(octokit, projectId) {
  // Implementation using GitHub GraphQL API to get project details
  // This would get the project columns and other metadata
  
  // Example GraphQL query (simplified)
  const query = `
    query {
      node(id: "${projectId}") {
        ... on Project {
          id
          name
          columns(first: 10) {
            nodes {
              id
              name
            }
          }
        }
      }
    }
  `;
  
  const response = await octokit.graphql(query);
  return response.node;
}

/**
 * Get all issues from a project with their metadata
 */
async function getProjectIssues(octokit, projectData, repo) {
  // This would retrieve all issues in the project with their status and metadata
  // Implementation would use GitHub API to get issues and their project card status
  
  // Placeholder for actual implementation
  const issues = [];
  
  // For each column in the project
  for (const column of projectData.columns.nodes) {
    // Get cards in this column (would need pagination for large projects)
    const { data: cards } = await octokit.projects.listCards({
      column_id: column.id
    });
    
    for (const card of cards) {
      if (card.content_url && card.content_url.includes('/issues/')) {
        // Extract issue number from content_url
        const issueNumber = parseInt(card.content_url.split('/').pop());
        
        // Get issue details
        const { data: issue } = await octokit.issues.get({
          ...repo,
          issue_number: issueNumber
        });
        
        issues.push({
          number: issue.number,
          title: issue.title,
          status: column.name,  // Use column name as status
          closed: issue.state === 'closed',
          closedReason: issue.state_reason,
          updatedAt: issue.updated_at,
          labels: issue.labels.map(l => l.name)
        });
      }
    }
  }
  
  return issues;
}

/**
 * Apply a label to an issue
 */
async function applyLabel(octokit, repo, issueNumber, label) {
  console.log(`Applying label '${label}' to issue #${issueNumber}`);
  
  try {
    await octokit.issues.addLabels({
      ...repo,
      issue_number: issueNumber,
      labels: [label]
    });
  } catch (error) {
    // Check if it's because the label doesn't exist
    if (error.status === 404) {
      // Create the label first
      await octokit.issues.createLabel({
        ...repo,
        name: label,
        color: label === 'Archive' ? '808080' : 'ff0000'  // Gray for Archive, Red for Not Planned
      });
      
      // Try adding the label again
      await octokit.issues.addLabels({
        ...repo,
        issue_number: issueNumber,
        labels: [label]
      });
    } else {
      throw error;
    }
  }
}

/**
 * Update project filters to hide issues with certain labels
 */
async function updateProjectFilters(octokit, projectId) {
  // This would need to use GitHub API to update project view settings
  // Note: This might require custom API calls or GitHub CLI commands
  // as the API for project views is limited
  
  console.log('Project filters would be updated here');
  // Placeholder - in reality, this might need to be manual or use GitHub CLI
}

/**
 * Update the audit log wiki page
 */
async function updateAuditLog(octokit, repo, wikiPageName, actions) {
  console.log(`Updating audit log on wiki page: ${wikiPageName}`);
  
  try {
    // Try to get the existing wiki page content
    const { data: existingPage } = await octokit.repos.getPageContent({
      ...repo,
      path: `${wikiPageName}.md`
    });
    
    // Decode existing content
    const existingContent = Buffer.from(existingPage.content, 'base64').toString();
    
    // Append new actions
    let newContent = existingContent + '\n\n## Pruner Actions - ' + 
      new Date().toISOString().split('T')[0] + '\n\n';
    
    for (const action of actions) {
      newContent += `- Issue #${action.issue}: ${action.action} - ${action.reason} (${action.timestamp})\n`;
    }
    
    // Update the wiki page
    await octokit.repos.createOrUpdatePageContent({
      ...repo,
      path: `${wikiPageName}.md`,
      message: 'Update Pruner audit log',
      content: Buffer.from(newContent).toString('base64'),
      sha: existingPage.sha
    });
  } catch (error) {
    if (error.status === 404) {
      // Wiki page doesn't exist yet, create it
      const newContent = `# ${wikiPageName}\n\nThis page automatically tracks actions taken by the Pruner GitHub Action.\n\n` +
        `## Pruner Actions - ${new Date().toISOString().split('T')[0]}\n\n`;
      
      for (const action of actions) {
        newContent += `- Issue #${action.issue}: ${action.action} - ${action.reason} (${action.timestamp})\n`;
      }
      
      await octokit.repos.createOrUpdatePageContent({
        ...repo,
        path: `${wikiPageName}.md`,
        message: 'Create Pruner audit log',
        content: Buffer.from(newContent).toString('base64')
      });
    } else {
      throw error;
    }
  }
}

// Execute the action
run();