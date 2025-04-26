const { Octokit } = require('@octokit/rest');
const dotenv = require('dotenv');

// Load environment variables from .env file
dotenv.config();

/**
 * Test script to verify workstream field detection in GitHub Projects
 */
async function testWorkstreamDetection() {
  // Get GitHub token from environment variable
  const githubToken = process.env.GITHUB_TOKEN;
  if (!githubToken) {
    console.error('GITHUB_TOKEN environment variable must be set');
    process.exit(1);
  }

  // Get project ID from command line or environment variable
  const projectId = process.env.PROJECT_ID || process.argv[2];
  if (!projectId) {
    console.error('PROJECT_ID must be provided as an environment variable or command line argument');
    process.exit(1);
  }

  // Initialize GitHub client
  const octokit = new Octokit({
    auth: githubToken
  });

  console.log(`Testing workstream detection for project ID: ${projectId}`);

  try {
    // Query project fields
    const query = `
      query($projectId: ID!) {
        node(id: $projectId) {
          ... on ProjectV2 {
            id
            title
            url
            fields(first: 20) {
              nodes {
                ... on ProjectV2Field {
                  id
                  name
                  dataType
                }
                ... on ProjectV2IterationField {
                  id
                  name
                  dataType
                }
                ... on ProjectV2SingleSelectField {
                  id
                  name
                  dataType
                  options {
                    id
                    name
                    color
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

    console.log(`Project: ${response.node.title}`);
    console.log(`URL: ${response.node.url}`);
    console.log('\nFields:');

    // Display all fields
    for (const field of response.node.fields.nodes) {
      console.log(`- ${field.name} (${field.dataType || 'unknown type'})`);
      
      // If it's a single select field, show options
      if (field.options) {
        console.log('  Options:');
        for (const option of field.options) {
          console.log(`  - ${option.name} (${option.color})`);
        }
      }
    }

    // Look for workstream field
    const workstreamField = response.node.fields.nodes.find(
      field => field.name.toLowerCase().includes('workstream')
    );

    if (workstreamField) {
      console.log('\nFound Workstream field:');
      console.log(`Name: ${workstreamField.name}`);
      console.log(`ID: ${workstreamField.id}`);
      console.log(`Type: ${workstreamField.dataType || 'unknown'}`);
      
      if (workstreamField.options) {
        console.log('Available Workstream options:');
        for (const option of workstreamField.options) {
          console.log(`- ${option.name}`);
        }
        
        console.log('\nTo use in .pruner.config.yml:');
        console.log(`
custom_fields:
  workstream_field_id: "${workstreamField.name}"
  status_field_id: "Status"  # Adjust based on your project
  dynamic_workstream_options: true
  done_status_value: "Done"  # Adjust based on your project
`);
      } else {
        console.log('No options found for the Workstream field');
      }
    } else {
      console.log('\nNo field with "workstream" in the name was found.');
      console.log('Available fields:');
      response.node.fields.nodes.forEach(field => {
        console.log(`- ${field.name}`);
      });
    }

  } catch (error) {
    console.error('Error:', error.message);
    if (error.request) {
      console.error('Request URL:', error.request.url);
    }
    console.error('Stack trace:', error.stack);
  }
}

// Run the test
testWorkstreamDetection();