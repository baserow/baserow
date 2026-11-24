import { TestApp } from '@baserow/test/helpers/testApp'
import { MicrosoftOutlookSendEmailServiceType } from '@baserow_enterprise/integrations/microsoftOutlook/serviceTypes'
import { MicrosoftOutlookSendEmailActionNodeType } from '@baserow_enterprise/automation/nodeTypes'

const formula = (value) => ({ formula: value, mode: 'simple' })

const service = (extra = {}) => ({
  integration_id: 7,
  to_emails: formula("'bob@example.com'"),
  cc_emails: formula(''),
  bcc_emails: formula(''),
  subject: formula("'Hello'"),
  body_type: 'plain',
  body: formula("'Hi Bob'"),
  ...extra,
})

describe('Microsoft Outlook types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const serviceType = () =>
    testApp._app.$registry.get('service', 'microsoft_outlook_send_email')

  test('is registered for the builder and automations', () => {
    const { $registry } = testApp._app
    expect(serviceType()).toBeInstanceOf(MicrosoftOutlookSendEmailServiceType)
    expect(
      $registry.get('workflowAction', 'microsoft_outlook_send_email')
        .serviceType
    ).toBe(serviceType())
    expect(
      $registry.get('node', 'microsoft_outlook_send_email')
    ).toBeInstanceOf(MicrosoftOutlookSendEmailActionNodeType)
    expect(serviceType().integrationType.getType()).toBe('microsoft')
    expect($registry.get('paidFeature', 'microsoft_outlook').getPlan()).toBe(
      'Advanced'
    )
  })

  test.each([
    [
      { integration_id: null },
      'serviceType.microsoftOutlookMissingIntegration',
    ],
    [
      { to_emails: formula(' ') },
      'serviceType.microsoftOutlookMissingRecipient',
    ],
  ])('reports what is missing: %o', (values, message) => {
    expect(serviceType().getErrorMessage({ service: service(values) })).toBe(
      message
    )
  })

  test('a complete action without subject, CC or BCC has no error', () => {
    expect(
      serviceType().getErrorMessage({
        service: service({ subject: formula('') }),
      })
    ).toBeNull()
  })

  test('a published action, which has only public fields, has no error', () => {
    expect(
      serviceType().getErrorMessage({
        service: {
          id: 1,
          type: 'microsoft_outlook_send_email',
          integration_id: 7,
          schema: null,
        },
      })
    ).toBeNull()
  })

  test('is deactivated without the license', () => {
    const hasFeature = vi.fn().mockReturnValue(false)
    const standalone = new MicrosoftOutlookSendEmailServiceType({
      app: {
        $i18n: testApp._app.$i18n,
        $registry: testApp._app.$registry,
        $hasFeature: hasFeature,
      },
    })
    const workspace = { id: 1 }

    expect(standalone.isDeactivatedReason({ workspace })).toBe(
      'enterprise.deactivated'
    )
    expect(standalone.getDeactivatedClickModal({ workspace })[1]).toEqual({
      'initial-selected-type': 'microsoft_outlook',
    })
    expect(hasFeature).toHaveBeenCalledWith('MICROSOFT_OUTLOOK', 1)

    hasFeature.mockReturnValue(true)
    expect(standalone.isDeactivatedReason({ workspace })).toBeNull()
    expect(standalone.getDeactivatedClickModal({ workspace })).toBeNull()
  })

  test('the node is named after a single fixed recipient', () => {
    const nodeType = testApp._app.$registry.get(
      'node',
      'microsoft_outlook_send_email'
    )
    const label = (toEmails) =>
      nodeType.getDefaultLabel({
        node: { service: { to_emails: formula(toEmails) } },
      })

    expect(label("'bob@example.com'")).toBe(
      'nodeType.microsoftOutlookSendEmailLabel'
    )
    expect(label("'bob@example.com, carol@example.com'")).toBe(
      'nodeType.microsoftOutlookSendEmailName'
    )
    expect(label("get('previous_node.1.email')")).toBe(
      'nodeType.microsoftOutlookSendEmailName'
    )
    expect(label('')).toBe('nodeType.microsoftOutlookSendEmailName')
  })
})
