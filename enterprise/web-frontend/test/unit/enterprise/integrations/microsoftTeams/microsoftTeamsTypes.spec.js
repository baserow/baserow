import { TestApp } from '@baserow/test/helpers/testApp'
import { MicrosoftTeamsWriteMessageServiceType } from '@baserow_enterprise/integrations/microsoftTeams/serviceTypes'
import { MicrosoftTeamsWriteMessageActionNodeType } from '@baserow_enterprise/automation/nodeTypes'
import {
  formulaForLiteral,
  literalFromFormula,
} from '@baserow_enterprise/integrations/microsoftTeams/utils'

const formula = (value) => ({ formula: value, mode: 'simple' })

const service = (extra = {}) => ({
  integration_id: 7,
  destination_type: 'channel',
  team_id: formula("'t1'"),
  channel_id: formula("'c1'"),
  chat_id: formula(''),
  message: formula("'Hello'"),
  ...extra,
})

describe('Microsoft Teams types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const serviceType = () =>
    testApp._app.$registry.get('service', 'microsoft_teams_write_message')

  test('is registered for the builder and automations', () => {
    const { $registry } = testApp._app
    expect(serviceType()).toBeInstanceOf(MicrosoftTeamsWriteMessageServiceType)
    expect(
      $registry.get('workflowAction', 'microsoft_teams_write_message')
        .serviceType
    ).toBe(serviceType())
    expect(
      $registry.get('node', 'microsoft_teams_write_message')
    ).toBeInstanceOf(MicrosoftTeamsWriteMessageActionNodeType)
    expect(serviceType().integrationType.getType()).toBe('microsoft')
  })

  test.each([
    [{ integration_id: null }, 'serviceType.microsoftTeamsMissingIntegration'],
    [{ team_id: formula('') }, 'serviceType.microsoftTeamsMissingTeam'],
    [{ channel_id: formula(' ') }, 'serviceType.microsoftTeamsMissingChannel'],
    [{ destination_type: 'chat' }, 'serviceType.microsoftTeamsMissingChat'],
    [{ message: formula('') }, 'serviceType.microsoftTeamsMissingMessage'],
  ])('reports what is missing: %o', (values, message) => {
    expect(serviceType().getErrorMessage({ service: service(values) })).toBe(
      message
    )
  })

  test('a published action, which has only public fields, has no error', () => {
    expect(
      serviceType().getErrorMessage({
        service: {
          id: 1,
          type: 'microsoft_teams_write_message',
          integration_id: 7,
          schema: null,
        },
      })
    ).toBeNull()
  })

  test('a complete chat action has no error', () => {
    expect(
      serviceType().getErrorMessage({
        service: service({
          destination_type: 'chat',
          team_id: formula(''),
          channel_id: formula(''),
          chat_id: formula("'19:abc@thread.v2'"),
        }),
      })
    ).toBeNull()
  })

  test('is deactivated without the license', () => {
    const hasFeature = vi.fn().mockReturnValue(false)
    const standalone = new MicrosoftTeamsWriteMessageServiceType({
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
      'initial-selected-type': 'microsoft_teams',
    })
    expect(hasFeature).toHaveBeenCalledWith('MICROSOFT_TEAMS', 1)

    hasFeature.mockReturnValue(true)
    expect(standalone.isDeactivatedReason({ workspace })).toBeNull()
    expect(standalone.getDeactivatedClickModal({ workspace })).toBeNull()
  })

  test('the node is named after the picked destination', () => {
    const nodeType = testApp._app.$registry.get(
      'node',
      'microsoft_teams_write_message'
    )

    expect(
      nodeType.getDefaultLabel({
        node: { service: { destination_label: 'General · Marketing' } },
      })
    ).toBe('nodeType.microsoftTeamsWriteMessageLabel')
    expect(
      nodeType.getDefaultLabel({ node: { service: { destination_label: '' } } })
    ).toBe('nodeType.microsoftTeamsWriteMessageName')
  })

  test('picked ids are string literals', () => {
    const id = "19:it's@thread.v2"
    expect(literalFromFormula(formulaForLiteral(id))).toBe(id)
    expect(literalFromFormula(formula("concat('a', 'b')"))).toBeNull()
    expect(literalFromFormula(formula(''))).toBeNull()
    expect(literalFromFormula({ formula: "'a'", mode: 'advanced' })).toBeNull()
  })
})
