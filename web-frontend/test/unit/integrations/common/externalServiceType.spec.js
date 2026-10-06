import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'

// Read rather than imported: the i18n loader turns an imported locale file
// into a loader function, and the test app only has the core messages.
const en = JSON.parse(
  readFileSync(
    resolve(__dirname, '../../../../modules/integrations/locales/en.json'),
    'utf8'
  )
)

describe('external service types', () => {
  let testApp
  let registry

  beforeAll(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('are registered with their integration type and form fields', () => {
    const gmail = registry.get('service', 'gmail_send_email')
    expect(gmail.integrationType.getType()).toBe('google')
    expect(gmail.isWorkflowAction).toBe(true)
    expect(gmail.formFields.map((field) => field.name)).toEqual([
      'to_emails',
      'cc_emails',
      'bcc_emails',
      'subject',
      'body',
    ])
    expect(gmail.group.id).toBe('integration-google')

    const teams = registry.get('service', 'microsoft_teams_send_message')
    expect(teams.integrationType.getType()).toBe('microsoft')

    const jira = registry.get('service', 'jira_list_issues')
    expect(jira.integrationType.getType()).toBe('jira')
    expect(jira.formFields.find((f) => f.name === 'max_results').type).toBe(
      'integer'
    )
  })

  test('report the missing integration and required fields', () => {
    const create = registry.get('service', 'jira_create_issue')
    expect(create.getErrorMessage({ service: undefined })).toBeNull()
    expect(create.getErrorMessage({ service: { integration_id: null } })).toBe(
      'externalServiceForm.missingIntegration'
    )
    expect(en.externalServiceForm.missingIntegration).toContain('{integration}')
    expect(
      create.getErrorMessage({
        service: { integration_id: 1, project_key: { formula: "'PROJ'" } },
      })
    ).toBe('externalServiceForm.missingField')
    expect(en.externalServiceForm.issueSummary).toBe('Summary')
    expect(
      create.getErrorMessage({
        service: {
          integration_id: 1,
          project_key: { formula: "'PROJ'" },
          summary: { formula: "'Bug'" },
        },
      })
    ).toBeNull()
  })

  test('integration summaries follow the connection state', () => {
    const google = registry.get('integration', 'google')
    expect(google.getSummary({ has_refresh_token: false })).toBe(
      'googleIntegrationType.notConnected'
    )
    expect(
      google.getSummary({
        has_refresh_token: true,
        account_email: 'me@example.com',
      })
    ).toBe('googleIntegrationType.connectedAs')
    expect(en.googleIntegrationType.connectedAs).toContain('{account}')
    const jira = registry.get('integration', 'jira')
    expect(jira.getSummary({ url: '', has_api_token: false })).toBe(
      'jiraIntegrationType.notConfigured'
    )
    expect(
      jira.getSummary({ url: 'https://x.atlassian.net', has_api_token: true })
    ).toBe('https://x.atlassian.net')
  })
})
