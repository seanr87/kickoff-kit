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
    
    // Set default custom field settings if not provided
    if (!config.custom_fields) {
      config.custom_fields = {
        workstream_field_id: "Workstream",
        status_field_id: "Status",
        dynamic_workstream_options: true,
        done_status_value: "Done"
      };
    }
    
    // Initialize GitHub client
    const octokit = new Octokit({
      auth: githubToken
    });
    
    const context = github.context;
    const repo = context.repo;
    
    // 1. Scan GitHub Project
    console.log(`Scanning project ID: ${config.project_id}`);
    
    // Get project data and issues with custom fields
    const { issues, workstreamOptions } = await getProjectIssues(octokit, null, config, repo);
    console.log(`Found ${issues.length} issues in the project`);
    console.log(`Workstream options: ${workstreamOptions.join(', ')}`);
    
    // Track actions for audit logging
    const actions = [];
    
    // 2. Apply Labels
    if (!config.dry_run) {
      // Apply "Not Planned" labels
      const notPlannedIssues = issues.filter(issue => 
        issue.closed && issue.closedReason === 'not_planned');
      
      console.log(`Found ${notPlannedIssues.length} issues to label as 'Not Planned'`);
      
      for (const issue of notPlannedIssues) {
        // Extract repository owner and name from issue
        const [owner, repoName] = issue.repository.split('/');
        await applyLabel(octokit, { owner, repo: repoName }, issue.number, 'Not Planned');
        
        actions.push({
          issue: issue.number,
          repository: issue.repository,
          action: 'Applied label: Not Planned',
          reason: 'Closed with reason "not planned"',
          timestamp: new Date().toISOString()
        });
      }
      
      // Apply "Archive" labels based on "Done" status for 2+ weeks
      const twoWeeksAgo = new Date();
      twoWeeksAgo.setDate(twoWeeksAgo.getDate() - config.done_age_days);
      
      // Use the configured done status value
      const doneStatusValue = config.custom_fields.done_status_value;
      
      const oldDoneIssues = issues.filter(issue => 
        issue.status === doneStatusValue && 
        new Date(issue.updatedAt) < twoWeeksAgo);
      
      console.log(`Found ${oldDoneIssues.length} issues to archive (Done for ${config.done_age_days}+ days)`);
      
      for (const issue of oldDoneIssues) {
        const [owner, repoName] = issue.repository.split('/');
        await applyLabel(octokit, { owner, repo: repoName }, issue.number, 'Archive');
        
        actions.push({
          issue: issue.number,
          repository: issue.repository,
          action: 'Applied label: Archive',
          reason: `In '${doneStatusValue}' status for more than ${config.done_age_days} days`,
          timestamp: new Date().toISOString()
        });
      }
      
      // Apply "Archive" labels for overflow in "Done" per workstream
      const workstreamGroups = {};
      
      // Group issues by workstream using the custom field value
      for (const issue of issues) {
        if (issue.status === doneStatusValue && issue.workstream) {
          if (!workstreamGroups[issue.workstream]) {
            workstreamGroups[issue.workstream] = [];
          }
          
          workstreamGroups[issue.workstream].push({
            number: issue.number,
            updatedAt: issue.updatedAt,
            repository: issue.repository
          });
        }
      }
      
      // Process each workstream for overflow
      for (const [workstream, workstreamIssues] of Object.entries(workstreamGroups)) {
        if (workstreamIssues.length > config.done_overflow_limit) {
          // Sort by updated date (oldest first)
          workstreamIssues.sort((a, b) => 
            new Date(a.updatedAt) - new Date(b.updatedAt));
          
          // Archive the oldest issues beyond the limit
          const toArchive = workstreamIssues.slice(0, 
            workstreamIssues.length - config.done_overflow_limit);
          
          console.log(`Found ${toArchive.length} overflow issues to archive in workstream: ${workstream}`);
          
          for (const issue of toArchive) {
            const [owner, repoName] = issue.repository.split('/');
            await applyLabel(octokit, { owner, repo: repoName }, issue.number, 'Archive');
            
            actions.push({
              issue: issue.number,
              repository: issue.repository,
              action: 'Applied label: Archive',
              reason: `Overflow in '${doneStatusValue}' status for workstream '${workstream}'`,
              timestamp: new Date().toISOString()
            });
          }
        }
      }
    } else {
      console.log('Dry run mode - no labels will be applied');
      
      // Count what would be labeled in dry run mode
      const notPlannedCount = issues.filter(issue => 
        issue.closed && issue.closedReason === 'not_planned').length;
      
      const twoWeeksAgo = new Date();
      twoWeeksAgo.setDate(twoWeeksAgo.getDate() - config.done_age_days);
      
      const doneStatusValue = config.custom_fields.done_status_value;
      
      const oldDoneCount = issues.filter(issue => 
        issue.status === doneStatusValue && 
        new Date(issue.updatedAt) < twoWeeksAgo).length;
      
      console.log(`DRY RUN: Would label ${notPlannedCount} issues as 'Not Planned'`);
      console.log(`DRY RUN: Would label ${oldDoneCount} issues as 'Archive' (Done for ${config.done_age_days}+ days)`);
      
      // Calculate overflow per workstream
      const workstreamGroups = {};
      let overflowCount = 0;
      
      for (const issue of issues) {
        if (issue.status === doneStatusValue && issue.workstream) {
          if (!workstreamGroups[issue.workstream]) {
            workstreamGroups[issue.workstream] = [];
          }
          
          workstreamGroups[issue.workstream].push({
            number: issue.number,
            updatedAt: issue.updatedAt
          });
        }
      }
      
      for (const [workstream, workstreamIssues] of Object.entries(workstreamGroups)) {
        if (workstreamIssues.length > config.done_overflow_limit) {
          const archiveCount = workstreamIssues.length - config.done_overflow_limit;
          overflowCount += archiveCount;
          console.log(`DRY RUN: Would label ${archiveCount} issues as 'Archive' in workstream '${workstream}' (overflow)`);
        }
      }
      
      console.log(`DRY RUN: Total issues that would be labeled: ${notPlannedCount + oldDoneCount + overflowCount}`);
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
 * Get project field information including custom fields
 */
async function getProjectFields(octokit, projectId) {
  // GitHub Projects v2 uses GraphQL API for custom fields
  const query = `
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          id
          title
          fields(first: 20) {
            nodes {
              ... on ProjectV2Field {
                id
                name
              }
              ... on ProjectV2IterationField {
                id
                name
                configuration {
                  iterations {
                    startDate
                    id
                  }
                }
              }
              ... on ProjectV2SingleSelectField {
                id
                name
                options {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
  `;
  
  const response = await octokit.graphql(query, {
    projectId: projectId
  });
  
  return response.node;
}

/**
 * Get all issues from a project with their metadata including custom fields
 */
async function getProjectIssues(octokit, projectData, config, repo) {
  // Get project fields including the workstream field
  const projectFields = await getProjectFields(octokit, config.project_id);
  
  // Find the workstream field
  const workstreamField = projectFields.fields.nodes.find(
    field => field.name === config.custom_fields.workstream_field_id
  );
  
  // Find the status field
  const statusField = projectFields.fields.nodes.find(
    field => field.name === config.custom_fields.status_field_id
  );
  
  if (!workstreamField) {
    console.warn(`Warning: Could not find workstream field "${config.custom_fields.workstream_field_id}"`);
  }
  
  if (!statusField) {
    console.warn(`Warning: Could not find status field "${config.custom_fields.status_field_id}"`);
  }
  
  // Get workstream options if dynamic is enabled
  let workstreamOptions = [];
  if (config.custom_fields.dynamic_workstream_options && workstreamField && workstreamField.options) {
    workstreamOptions = workstreamField.options.map(option => option.name);
    console.log('Detected workstream options:', workstreamOptions);
  } else if (!config.custom_fields.dynamic_workstream_options) {
    workstreamOptions = config.custom_fields.workstream_options;
    console.log('Using configured workstream options:', workstreamOptions);
  }
  
  // Get all issues in the project with their custom field values
  const query = `
    query($projectId: ID!, $first: Int!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: $first, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              content {
                ... on Issue {
                  id
                  number
                  title
                  state
                  stateReason
                  updatedAt
                  labels(first: 10) {
                    nodes {
                      name
                    }
                  }
                  repository {
                    name
                    owner {
                      login
                    }
                  }
                }
              }
              fieldValues(first: 20) {
                nodes {
                  ... on ProjectV2ItemFieldTextValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    text
                  }
                  ... on ProjectV2ItemFieldDateValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    date
                  }
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    field { ... on ProjectV2FieldCommon { name } }
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  `;
  
  // Process all pages of results
  const issues = [];
  let hasNextPage = true;
  let cursor = null;
  
  while (hasNextPage) {
    const response = await octokit.graphql(query, {
      projectId: config.project_id,
      first: 100,
      after: cursor
    });
    
    const items = response.node.items;
    
    // Process each item
    for (const item of items.nodes) {
      if (!item.content || item.content.__typename !== 'Issue') continue;
      
      const issue = item.content;
      
      // Extract custom field values
      const fieldValues = {};
      for (const fieldValue of item.fieldValues.nodes) {
        if (fieldValue.field) {
          fieldValues[fieldValue.field.name] = fieldValue.text || fieldValue.date || fieldValue.name;
        }
      }
      
      // Get workstream and status values
      const workstream = fieldValues[config.custom_fields.workstream_field_id] || 'Unknown';
      const status = fieldValues[config.custom_fields.status_field_id] || 'Unknown';
      
      issues.push({
        number: issue.number,
        title: issue.title,
        status: status,
        workstream: workstream,
        closed: issue.state === 'CLOSED',
        closedReason: issue.stateReason,
        updatedAt: issue.updatedAt,
        labels: issue.labels.nodes.map(l => l.name),
        repository: `${issue.repository.owner.login}/${issue.repository.name}`
      });
    }
    
    // Check if there are more pages
    hasNextPage = items.pageInfo.hasNextPage;
    cursor = items.pageInfo.endCursor;
  }
  
  return { issues, workstreamOptions };
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