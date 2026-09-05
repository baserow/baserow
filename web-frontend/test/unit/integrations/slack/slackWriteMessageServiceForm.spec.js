import { TestApp } from '@baserow/test/helpers/testApp'
import SlackWriteMessageServiceForm from '@baserow/modules/integrations/slack/components/services/SlackWriteMessageServiceForm'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'

const APPLICATION_ID = 100

describe('SlackWriteMessageServiceForm', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('application/forceCreate', {
      id: APPLICATION_ID,
      name: 'Customers',
      type: 'database',
      workspace: { id: 1 },
      tables: [],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const application = () =>
    testApp.store.getters['application/get'](APPLICATION_ID)

  test('a bot created from the dropdown is the one the action carries', async () => {
    // The whole point of emitting the Vue 3 event: creating the first bot
    // selects it, so nobody has to reopen the dropdown and pick it again.
    testApp.mock
      .onPost(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, {
        id: 7,
        type: 'slack_bot',
        name: 'Bot',
        order: '1',
        token: 'xoxb-made-up',
      })

    const wrapper = await testApp.mount(SlackWriteMessageServiceForm, {
      props: { application: application(), defaultValues: {} },
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    await wrapper
      .findComponent(IntegrationCreateEditModal)
      .vm.submit({ name: 'Bot', token: 'xoxb-made-up' })

    await wrapper.vm.$nextTick()

    // The selected value, not the item list: the list holds the name either
    // way, so only this says the action carries it.
    expect(wrapper.find('.dropdown__selected').text()).toContain('Bot')
    // And the alert saying the action has no bot is gone.
    expect(wrapper.findComponent({ name: 'Alert' }).exists()).toBe(false)
  })
})
