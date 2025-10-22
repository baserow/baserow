#!/usr/bin/env node

/**
 * Local test script for the GitHub Project PR workflow
 *
 * Usage:
 *   node test-pr-workflow.js <pr_number> <action>
 *
 * Actions:
 *   - opened: Simulate PR opened
 *   - draft: Simulate converting to draft
 *   - ready: Simulate ready for review
 *   - approve: Simulate a review approval
 *   - changes: Simulate request changes review
 *
 * Example:
 *   node test-pr-workflow.js 4113 opened
 */

const { execSync } = require('child_process');

// Configuration
const OWNER = 'baserow';
const REPO = 'baserow';
const PROJECT_NUMBER = 3;

// Get arguments
const prNumber = parseInt(process.argv[2]);
const action = process.argv[3];

if (!prNumber || !action) {
  console.error('Usage: node test-pr-workflow.js <pr_number> <action>');
  console.error('Actions: opened, draft, ready, approve, changes');
  process.exit(1);
}

console.log(`Testing PR workflow: PR #${prNumber} - Action: ${action}\n`);

// Helper function to run GraphQL queries
function runGraphQL(query, variables = {}) {
  try {
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

async function main() {
  try {
    // Step 1: Get Project Info
    console.log('Step 1: Getting project info and fields...');
    const projectQuery = `
      query($owner: String!, $number: Int!) {
        organization(login: $owner) {
          projectV2(number: $number) {
            id
            title
            fields(first: 20) {
              nodes {
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

    const projectData = runGraphQL(projectQuery, { owner: OWNER, number: PROJECT_NUMBER });
    const project = projectData.data.organization.projectV2;

    const statusField = project.fields.nodes.find(f => f.name === 'Status');
    const reviewStatusField = project.fields.nodes.find(f => f.name === 'Review Status');

    console.log(`✓ Project: "${project.title}"`);
    console.log(`  Status Field ID: ${statusField.id}`);
    console.log(`  Review Status Field ID: ${reviewStatusField.id}\n`);

    // Step 2: Get PR Data
    console.log('Step 2: Getting PR data...');
    const prQuery = `
      query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $number) {
            id
            number
            title
            isDraft
            state
            closingIssuesReferences(first: 10) {
              nodes {
                id
                number
                title
              }
            }
          }
        }
      }
    `;

    const prData = runGraphQL(prQuery, { owner: OWNER, repo: REPO, number: prNumber });
    const pr = prData.data.repository.pullRequest;

    console.log(`✓ PR #${pr.number}: "${pr.title}"`);
    console.log(`  State: ${pr.state}, Draft: ${pr.isDraft}`);
    console.log(`  Linked Issues: ${pr.closingIssuesReferences.nodes.length}`);
    pr.closingIssuesReferences.nodes.forEach(issue => {
      console.log(`    - #${issue.number}: ${issue.title}`);
    });
    console.log();

    // Step 3: Simulate the action
    console.log(`Step 3: Simulating action "${action}"...\n`);

    const statusOptions = {};
    statusField.options.forEach(opt => {
      statusOptions[opt.name] = opt.id;
    });

    const reviewStatusOptions = {};
    reviewStatusField.options.forEach(opt => {
      reviewStatusOptions[opt.name] = opt.id;
    });

    // Get PR project item
    function getProjectItem(contentId) {
      const query = `
        query($contentId: ID!) {
          node(id: $contentId) {
            ... on PullRequest {
              projectItems(first: 10) {
                nodes {
                  id
                  project { id }
                }
              }
            }
          }
        }
      `;

      const result = runGraphQL(query, { contentId });
      const item = result.data.node.projectItems.nodes.find(
        i => i.project.id === project.id
      );
      return item ? item.id : null;
    }

    function updateFieldValue(itemId, fieldId, optionId) {
      const mutation = `
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { singleSelectOptionId: $optionId }
          }) {
            projectV2Item { id }
          }
        }
      `;

      runGraphQL(mutation, {
        projectId: project.id,
        itemId: itemId,
        fieldId: fieldId,
        optionId: optionId
      });
    }

    const prItemId = getProjectItem(pr.id);
    if (!prItemId) {
      console.error('❌ PR is not in the project. Please add it first.');
      process.exit(1);
    }

    console.log(`✓ PR project item ID: ${prItemId}\n`);

    // Execute the action
    switch (action) {
      case 'opened':
      case 'draft':
        console.log('Setting PR status to: In Progress');
        updateFieldValue(prItemId, statusField.id, statusOptions['In Progress']);
        console.log('✅ Done!');
        break;

      case 'ready':
        console.log('Setting PR status to: In Review');
        updateFieldValue(prItemId, statusField.id, statusOptions['In Review']);
        console.log('Setting Review Status to: Waiting');
        updateFieldValue(prItemId, reviewStatusField.id, reviewStatusOptions['Waiting']);
        console.log('✅ Done!');
        break;

      case 'approve':
        console.log('Setting PR status to: In Testing');
        updateFieldValue(prItemId, statusField.id, statusOptions['In Testing']);
        console.log('✅ Done! (Note: Full approval logic requires checking all reviews)');
        break;

      case 'changes':
        console.log('Setting Review Status to: Feedback');
        updateFieldValue(prItemId, reviewStatusField.id, reviewStatusOptions['Feedback']);
        console.log('✅ Done!');
        break;

      default:
        console.error(`❌ Unknown action: ${action}`);
        process.exit(1);
    }

  } catch (error) {
    console.error('\n❌ Workflow failed:', error.message);
    process.exit(1);
  }
}

main();
