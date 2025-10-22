#!/usr/bin/env node

/**
 * Local test script for the GitHub Project workflow
 *
 * Usage:
 *   node test-workflow.js <issue_number>
 *
 * Example:
 *   node test-workflow.js 4105
 *
 * Requirements:
 *   - gh CLI must be authenticated with project scopes
 *   - GITHUB_TOKEN environment variable (optional, will use gh auth token if not set)
 */

const { execSync } = require('child_process');

// Configuration
const OWNER = 'baserow';
const REPO = 'baserow';
const PROJECT_NUMBER = 3;

// Get issue number from command line
const issueNumber = parseInt(process.argv[2]);
if (!issueNumber) {
  console.error('Usage: node test-workflow.js <issue_number>');
  process.exit(1);
}

console.log(`Testing workflow for issue #${issueNumber}...\n`);

// Helper function to run GraphQL queries
function runGraphQL(query, variables = {}) {
  try {
    // Build the GraphQL query with variables inline
    let varArgs = '';
    for (const [key, value] of Object.entries(variables)) {
      if (typeof value === 'string') {
        varArgs += ` -f ${key}="${value}"`;
      } else {
        varArgs += ` -F ${key}=${value}`;
      }
    }

    const result = execSync(
      `gh api graphql -f query='${query}'${varArgs}`,
      { encoding: 'utf-8' }
    );
    return JSON.parse(result);
  } catch (error) {
    console.error('GraphQL Error:', error.message);
    throw error;
  }
}

// Step 1: Get Project Data
console.log('Step 1: Getting project data...');
const projectQuery = `
  query($owner: String!, $number: Int!) {
    organization(login: $owner) {
      projectV2(number: $number) {
        id
        title
        number
      }
    }
  }
`;

try {
  const projectData = runGraphQL(projectQuery, { owner: OWNER, number: PROJECT_NUMBER });
  const project = projectData.data.organization.projectV2;

  if (!project) {
    console.error(`❌ Project ${PROJECT_NUMBER} not found`);
    process.exit(1);
  }

  console.log(`✓ Found project: "${project.title}" (${project.id})\n`);

  // Step 2: Get Issue Data
  console.log('Step 2: Getting issue data...');
  const issueQuery = `
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $number) {
          id
          number
          title
          labels(first: 10) {
            nodes {
              name
            }
          }
        }
      }
    }
  `;

  const issueData = runGraphQL(issueQuery, {
    owner: OWNER,
    repo: REPO,
    number: issueNumber
  });
  const issue = issueData.data.repository.issue;

  if (!issue) {
    console.error(`❌ Issue #${issueNumber} not found`);
    process.exit(1);
  }

  console.log(`✓ Found issue: "${issue.title}"`);
  console.log(`  Labels: ${issue.labels.nodes.map(l => l.name).join(', ')}`);

  // Step 3: Check if issue has required labels
  console.log('\nStep 3: Checking labels...');
  const hasRequiredLabel = issue.labels.nodes.some(label =>
    label.name.startsWith('domain::database') || label.name.startsWith('domain::core')
  );

  if (!hasRequiredLabel) {
    console.log('⚠️  Issue does not have required labels (domain::database or domain::core)');
    console.log('   Workflow would exit here without adding to project');
    process.exit(0);
  }

  console.log('✓ Issue has required labels\n');

  // Step 4: Check if issue is already in project
  console.log('Step 4: Checking if issue is already in project...');
  const checkQuery = `
    query($issueId: ID!) {
      node(id: $issueId) {
        ... on Issue {
          projectItems(first: 10) {
            nodes {
              id
              project {
                id
                title
              }
            }
          }
        }
      }
    }
  `;

  const checkData = runGraphQL(checkQuery, { issueId: issue.id });
  const existingItem = checkData.data.node.projectItems.nodes.find(
    item => item.project.id === project.id
  );

  if (existingItem) {
    console.log(`⚠️  Issue is already in project "${project.title}"`);
    console.log('   Workflow would exit here without adding duplicate');
    process.exit(0);
  }

  console.log('✓ Issue is not in project yet\n');

  // Step 5: Add issue to project
  console.log('Step 5: Adding issue to project...');
  const addMutation = `
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {
        projectId: $projectId
        contentId: $contentId
      }) {
        item {
          id
        }
      }
    }
  `;

  const addData = runGraphQL(addMutation, {
    projectId: project.id,
    contentId: issue.id
  });

  if (addData.data.addProjectV2ItemById.item) {
    console.log(`✅ Successfully added issue #${issueNumber} to project "${project.title}"`);
  } else {
    console.error('❌ Failed to add issue to project');
    process.exit(1);
  }

} catch (error) {
  console.error('\n❌ Workflow failed:', error.message);
  process.exit(1);
}
