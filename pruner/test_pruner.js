/**
 * Test script for Pruner
 * 
 * This script tests the Pruner functionality by simulating the GitHub action environment.
 * 
 * Usage:
 *   node test_pruner.js [--dry-run] [--project-id ID] [--repo OWNER/REPO]
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Mock @actions/core and @actions/github
global.core = {
  getInput: (name) => {
    if (name === 'github-token') return process.env.GITHUB_TOKEN;
    if (name === 'config-base64') return process.env.CONFIG_BASE64;
    return '';
  },
  setFailed: (message) => console.error(`ERROR: ${message}`),
  info: (message) => console.log(message),
  warning: (message) => console.warn(`WARNING: ${message}`)
};

global.github = {
  context: {
    repo: {
      owner: 'OWNER',
      repo: 'REPO'
    }
  }
};

// Parse command line arguments
const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const projectIdArg = args.find(arg => arg.startsWith('--project-id='));
const repoArg = args.find(arg => arg.startsWith('--repo='));

// Get project ID
let projectId = projectIdArg ? projectIdArg.split('=')[1] : null;
if (!projectId) {
  projectId = process.env.PROJECT_ID;
  if (!projectId) {
    console.error('Project ID is required. Provide it via --project-id=ID or PROJECT_ID environment variable');
    process.exit(1);
  }
}

// Get repo info
if (repoArg) {
  const [owner, repo] = repoArg.split('=')[1].split('/');
  github.context.repo.owner = owner;
  github.context.repo.repo = repo;
}

// Load and prepare configuration
let config;
try {
  // Try to load from .pruner.config file
  const configFile = fs.readFileSync('.pruner.config', 'utf8');
  config = yaml.load(configFile);
  
  // Override project ID if provided
  if (projectId) {
    config.project_id = projectId;
  }
  
  // Override dry-run if specified
  if (dryRun) {
    config.dry_run = true;
  }
  
  console.log('Loaded configuration:', config);
} catch (error) {
  console.error('Error loading configuration:', error.message);
  
  // Create a minimal configuration
  config = {
    project_id: projectId,
    done_age_days: 14,
    done_overflow_limit: 3,
    wiki_page_name: "Pruner Test Log",
    dry_run: dryRun || true,
    custom_fields: {
      workstream_field_id: "Workstream",
      status_field_id: "Status",
      dynamic_workstream_options: true,
      done_status_value: "Done"
    }
  };
  
  console.log('Using default configuration:', config);
}

// Check for GitHub token
if (!process.env.GITHUB_TOKEN) {
  console.error('GITHUB_TOKEN environment variable must be set');
  console.log('Create a .env file with content: GITHUB_TOKEN=your_github_token');
  process.exit(1);
}

// Encode configuration as base64
process.env.CONFIG_BASE64 = Buffer.from(JSON.stringify(config)).toString('base64');

console.log('==============================');
console.log('PRUNER TEST');
console.log('==============================');
console.log(`Project ID: ${config.project_id}`);
console.log(`Repository: ${github.context.repo.owner}/${github.context.repo.repo}`);
console.log(`Dry Run: ${config.dry_run ? 'Yes' : 'No'}`);
console.log('==============================');

// Import and run the Pruner script
try {
  // Check if we're in the root or in the pruner directory
  let scriptPath;
  if (fs.existsSync('./index.js')) {
    scriptPath = './index.js';
  } else if (fs.existsSync('./pruner/index.js')) {
    scriptPath = './pruner/index.js';
  } else {
    console.error('Could not find index.js in current or pruner/ directory');
    process.exit(1);
  }
  
  console.log(`Running Pruner script from ${scriptPath}...`);
  
  // Run the Pruner script
  require(scriptPath);
} catch (error) {
  console.error('Error executing Pruner:', error);
  process.exit(1);
}