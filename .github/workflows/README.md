# GitHub Workflows

## Database Team PR Automation

**File:** `database-projects-pr-workflow.yml`

This workflow automatically updates the Database Team's GitHub Project board based on PR events.

### How it works

The workflow triggers on PR events (opened, review requested, review submitted, merged, etc.) and automatically:

1. **Checks domain labels** - Only processes PRs with labels starting with `domain::database` or `domain::core`
2. **Adds PR to project** - Ensures the PR is added to the Database Team project board
3. **Updates Status field** - Sets the PR status based on its state:
   - `In Progress` - PR is a draft
   - `In Review` - PR is ready for review
   - `Done` - PR has been merged
4. **Updates Review Status field** - Sets the review status based on review state:
   - `Awaiting` - Set when:
     - PR switches from draft to ready for review
     - There are pending review requests
     - A reviewer who requested changes has been re-requested for review
     - No reviewers have been requested yet and no approvals exist
   - `Feedback` - Changes have been requested by a reviewer
   - `Merge` - No pending review requests and at least one approval exists
5. **Updates linked issues** - Also updates the Status field (not Review Status) of any issues linked to the PR. This assumes a 1:1 relation between PRs and issues.

### State transitions

```
Draft PR opened/converted to draft
  → Status: In Progress
  → Review Status: (cleared)

PR ready for review / review requested
  → Status: In Review
  → Review Status: Awaiting

Changes requested
  → Status: In Review
  → Review Status: Feedback

Changes requested reviewer re-requested for review
  → Status: In Review
  → Review Status: Awaiting

PR approved
  → Status: In Review
  → Review Status: Merge

PR merged
  → Status: Done
  → Review Status: (cleared)
```

### Configuration

The workflow uses these environment variables (defined at the top of the file):

| Variable | Description |
|----------|-------------|
| `PROJECT_NUMBER` | The GitHub Project number (currently `3`) |
| `DOMAIN_LABELS` | Labels that trigger the workflow (`domain::database`, `domain::core`) |
| `STATUS_FIELD_NAME` | Name of the Status field in the project |
| `REVIEW_STATUS_FIELD_NAME` | Name of the Review Status field in the project |

### Requirements

- A GitHub token with project write permissions stored as `DATABASE_PROJECT_WORKFLOW_TOKEN` secret
- The project must have `Status` and `Review Status` single-select fields with the expected options

### Manual trigger

You can manually trigger the workflow for a specific PR using the "Run workflow" button in the Actions tab, providing the PR number.

---

## Database Team Issue Automation

**File:** `database-projects-issues-workflow.yml`

This workflow automatically adds new issues to the Database Team's GitHub Project board.

### How it works

The workflow triggers when an issue is opened or labeled, and:

1. **Checks domain labels** - Only processes issues with labels starting with `domain::database` or `domain::core`
2. **Checks if already in project** - Skips if the issue is already on the project board
3. **Adds issue to project** - Adds the issue to the Database Team project board
4. **Sets Status to Todo** - Sets the initial status to `Todo`

### Configuration

| Variable | Description |
|----------|-------------|
| `PROJECT_NUMBER` | The GitHub Project number (currently `3`) |
| `DOMAIN_LABELS` | Labels that trigger the workflow (`domain::database`, `domain::core`) |
| `STATUS_FIELD_NAME` | Name of the Status field in the project |
| `STATUS_TODO` | The initial status value for new issues (`Todo`) |

### Requirements

- A GitHub token with project write permissions stored as `DATABASE_PROJECT_WORKFLOW_TOKEN` secret
- The project must have a `Status` single-select field with a `Todo` option

### Manual trigger

You can manually trigger the workflow for a specific issue using the "Run workflow" button in the Actions tab, providing the issue number.
