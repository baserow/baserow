import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateOnboardingCancelModal from '@baserow/modules/database/components/onboarding/TemplateOnboardingCancelModal'

describe('TemplateDatabaseOnboardingStepType.getCancelModal', () => {
  let testApp = null
  let stepType = null

  beforeEach(() => {
    testApp = new TestApp()
    stepType = testApp.getRegistry().get('databaseOnboardingStep', 'template')
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('offers the template modal when the instance has templates', async () => {
    testApp.mockServer.mock
      .onGet('/templates/')
      .reply(200, [
        { id: 1, name: 'Category', templates: [{ id: 1, name: 'Template' }] },
      ])

    const modal = await stepType.getCancelModal()

    expect(modal.component).toBe(TemplateOnboardingCancelModal)
    expect(modal.props.categories).toHaveLength(1)
    expect(modal.props.databaseStepType).toBe('template')
  })

  test('does not offer a modal when the instance has no templates', async () => {
    testApp.mockServer.mock
      .onGet('/templates/')
      .reply(200, [{ id: 1, name: 'Category', templates: [] }])

    expect(await stepType.getCancelModal()).toBe(null)
  })
})
