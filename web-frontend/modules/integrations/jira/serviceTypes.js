import {
  ExternalServiceType,
  formulaField,
  integerField,
} from '@baserow/modules/integrations/common/externalServiceType'
import { JiraIntegrationType } from '@baserow/modules/integrations/jira/integrationTypes'

class JiraServiceType extends ExternalServiceType {
  static get integrationTypeClass() {
    return JiraIntegrationType
  }
}

const issueFields = (required) => [
  formulaField('summary', 'issueSummary', { required }),
  formulaField('description', 'issueDescription', {
    help: 'issueDescriptionHelp',
  }),
  formulaField('issue_type', 'issueType', {
    placeholder: 'issueTypePlaceholder',
    help: 'issueTypeHelp',
  }),
  formulaField('priority', 'issuePriority', {
    placeholder: 'issuePriorityPlaceholder',
  }),
  formulaField('labels', 'issueLabels', { help: 'issueLabelsHelp' }),
  formulaField('assignee', 'issueAssignee', { help: 'issueAssigneeHelp' }),
]

export class JiraListIssuesServiceType extends JiraServiceType {
  static getType() {
    return 'jira_list_issues'
  }

  static get i18nKey() {
    return 'jiraListIssues'
  }

  get icon() {
    return 'iconoir-task-list'
  }

  get formFields() {
    return [
      formulaField('jql', 'jql', {
        placeholder: 'jqlPlaceholder',
        help: 'jqlHelp',
      }),
      integerField('max_results', 'maxResults', { max: 100 }),
    ]
  }

  getOrder() {
    return 50
  }
}

export class JiraCreateIssueServiceType extends JiraServiceType {
  static getType() {
    return 'jira_create_issue'
  }

  static get i18nKey() {
    return 'jiraCreateIssue'
  }

  get icon() {
    return 'iconoir-plus'
  }

  get formFields() {
    return [
      formulaField('project_key', 'projectKey', {
        required: true,
        placeholder: 'projectKeyPlaceholder',
        help: 'projectKeyHelp',
      }),
      ...issueFields(true),
    ]
  }

  getOrder() {
    return 51
  }
}

export class JiraUpdateIssueServiceType extends JiraServiceType {
  static getType() {
    return 'jira_update_issue'
  }

  static get i18nKey() {
    return 'jiraUpdateIssue'
  }

  get icon() {
    return 'iconoir-edit-pencil'
  }

  get formFields() {
    return [
      formulaField('issue_key', 'issueKey', {
        required: true,
        placeholder: 'issueKeyPlaceholder',
      }),
      ...issueFields(false),
    ]
  }

  getOrder() {
    return 52
  }
}

export class JiraDeleteIssueServiceType extends JiraServiceType {
  static getType() {
    return 'jira_delete_issue'
  }

  static get i18nKey() {
    return 'jiraDeleteIssue'
  }

  get icon() {
    return 'iconoir-bin'
  }

  get formFields() {
    return [
      formulaField('issue_key', 'issueKey', {
        required: true,
        placeholder: 'issueKeyPlaceholder',
      }),
    ]
  }

  getOrder() {
    return 53
  }
}
