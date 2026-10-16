import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import Presentation from '@baserow/modules/core/components/Presentation'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import { IntegrationsBuilderSettingsType } from '@baserow/modules/builder/builderSettingTypes'
import { integrationSubtitle } from '@baserow/modules/core/utils/integration'

const LOCAL_BASEROW_OK = {
  id: 1,
  name: 'Local Baserow',
  type: 'local_baserow',
  authorized_user: { first_name: 'Ada', username: 'ada@example.com' },
}
const LOCAL_BASEROW_NO_USER = {
  id: 2,
  name: 'Local Baserow',
  type: 'local_baserow',
  authorized_user: null,
}

describe('Integration error trail', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const registry = () => testApp.store.$registry

  test('integration types report what is misconfigured', () => {
    const localBaserow = registry().get('integration', 'local_baserow')
    expect(localBaserow.isInError(LOCAL_BASEROW_OK)).toBe(false)
    expect(localBaserow.isInError(LOCAL_BASEROW_NO_USER)).toBe(true)
    expect(localBaserow.getErrorMessage(LOCAL_BASEROW_NO_USER)).toBe(
      'localBaserowIntegrationType.errorNoUser'
    )

    const slack = registry().get('integration', 'slack_bot')
    expect(slack.isInError({ has_token: true })).toBe(false)
    expect(slack.isInError({ has_token: false })).toBe(true)

    const smtp = registry().get('integration', 'smtp')
    expect(smtp.isInError({ host: 'smtp.example.com', port: 587 })).toBe(false)
    expect(smtp.isInError({ host: '', port: 587 })).toBe(true)

    // Inheriting the workspace AI settings is a valid configuration.
    const ai = registry().get('integration', 'ai')
    expect(ai.isInError({ ai_settings: {} })).toBe(false)
  })

  test.each(['builder', 'automation'])(
    'a %s is in error when one of its integrations is',
    (type) => {
      const applicationType = registry().get('application', type)
      expect(
        applicationType.isInError({ integrations: [LOCAL_BASEROW_OK] })
      ).toBe(false)
      expect(
        applicationType.isInError({
          integrations: [LOCAL_BASEROW_OK, LOCAL_BASEROW_NO_USER],
        })
      ).toBe(true)
      // The message comes from the integration that is in error.
      expect(
        applicationType.getErrorMessage({
          integrations: [LOCAL_BASEROW_OK, LOCAL_BASEROW_NO_USER],
        })
      ).toBe('localBaserowIntegrationType.errorNoUser')
      expect(
        applicationType.getErrorMessage({ integrations: [LOCAL_BASEROW_OK] })
      ).toBe(null)
    }
  )

  test('nothing is flagged without the application_in_error feature flag', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const app = {
      $registry: registry(),
      $featureFlagIsEnabled: featureFlagIsEnabled,
    }
    const application = { integrations: [LOCAL_BASEROW_NO_USER] }

    expect(new BuilderApplicationType({ app }).isInError(application)).toBe(
      false
    )
    expect(
      new IntegrationsBuilderSettingsType({ app }).isInError(application)
    ).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('application_in_error')
    // The integration itself still knows it's misconfigured.
    expect(
      registry()
        .get('integration', 'local_baserow')
        .isInError(LOCAL_BASEROW_NO_USER)
    ).toBe(true)

    featureFlagIsEnabled.mockReturnValue(true)
    expect(new BuilderApplicationType({ app }).isInError(application)).toBe(
      true
    )
  })

  test('the subtitle explains why an integration is in error', () => {
    const app = {
      $registry: registry(),
      $featureFlagIsEnabled: vi.fn().mockReturnValue(true),
    }
    expect(integrationSubtitle(app, LOCAL_BASEROW_NO_USER)).toBe(
      'localBaserowIntegrationType.errorNoUser'
    )
    expect(integrationSubtitle(app, LOCAL_BASEROW_OK)).toBe(
      'localBaserowIntegrationType.localBaserowSummary'
    )

    // Without the feature flag, the summary is kept.
    app.$featureFlagIsEnabled.mockReturnValue(false)
    expect(integrationSubtitle(app, LOCAL_BASEROW_NO_USER)).toBe(
      'localBaserowIntegrationType.localBaserowNoUser'
    )
  })

  test('applications without integrations are never in error', () => {
    expect(registry().get('application', 'database').isInError({})).toBe(false)
  })

  test.each([
    ['builderSettings', 'builder'],
    ['automationSettings', 'automation'],
  ])(
    'only the integrations %s tab is flagged',
    (registryName, applicationType) => {
      const application = { integrations: [LOCAL_BASEROW_NO_USER] }
      const inError = registry()
        .getOrderedList(registryName)
        .filter((setting) => setting.isInError(application))
        .map((setting) => setting.getType())
      expect(inError).toEqual(['integrations'])
      expect(
        registry()
          .get(registryName, 'integrations')
          .getErrorMessage(application)
      ).toBe('localBaserowIntegrationType.errorNoUser')
      expect(
        registry().get('application', applicationType).isInError(application)
      ).toBe(true)
    }
  )

  test('the sidebar flags an application whose integration is in error', async () => {
    const workspace = { id: 1, name: 'Workspace' }
    const application = {
      id: 10,
      name: 'App',
      type: 'builder',
      workspace,
      integrations: [LOCAL_BASEROW_OK],
      _: { type: registry().get('application', 'builder') },
    }
    const wrapper = await testApp.mount(SidebarApplication, {
      props: { application, workspace },
    })
    expect(wrapper.find('.tree__action--error').exists()).toBe(false)
    expect(wrapper.find('.tree__error-icon').exists()).toBe(false)

    await wrapper.setProps({
      application: {
        ...application,
        integrations: [LOCAL_BASEROW_NO_USER],
      },
    })
    expect(wrapper.find('.tree__action--error').exists()).toBe(true)
    expect(wrapper.find('.tree__error-icon').exists()).toBe(true)
  })

  test('a presentation subtitle can be flagged as an error', async () => {
    const wrapper = await testApp.mount(Presentation, {
      props: { title: 'Local Baserow', subtitle: 'Not configured' },
    })
    expect(wrapper.find('.presentation__subtitle--error').exists()).toBe(false)

    await wrapper.setProps({ subtitleError: true })
    expect(wrapper.find('.presentation__subtitle--error').text()).toBe(
      'Not configured'
    )
  })
})
