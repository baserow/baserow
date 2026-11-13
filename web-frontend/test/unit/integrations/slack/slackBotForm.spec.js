import flushPromises from 'flush-promises'

import SlackBotForm from '@baserow/modules/integrations/slack/components/integrations/SlackBotForm'
import { SLACK_APP_MANIFEST } from '@baserow/modules/integrations/slack/manifest'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Slack bot integration form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(SlackBotForm, {
      props: {
        application: { id: 1 },
        ...props,
      },
    })
  }

  test('omits an untouched token from the submitted values', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    expect('token' in wrapper.vm.getFormValues()).toBe(false)
  })

  test('includes a token the user typed', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    await wrapper.find('.form-input__input').setValue('xoxb-new')
    await flushPromises()

    expect(wrapper.vm.getFormValues().token).toBe('xoxb-new')
  })

  test('omits a token the user typed and then cleared', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })
    const input = wrapper.find('.form-input__input')

    await input.setValue('xoxb-new')
    await input.setValue('')
    await flushPromises()

    expect('token' in wrapper.vm.getFormValues()).toBe(false)
  })

  test('does not require a token when one is already saved', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    wrapper.vm.touch()
    await flushPromises()

    expect(wrapper.vm.isFormValid()).toBe(true)
  })

  test('requires a token when none is saved', async () => {
    const wrapper = await mountComponent({ defaultValues: {} })

    wrapper.vm.touch()
    await flushPromises()

    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('links to a Slack app prefilled with the scopes the action needs', async () => {
    const wrapper = await mountComponent({ defaultValues: {} })

    const link = wrapper.find('a[href^="https://api.slack.com/apps"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('target')).toBe('_blank')

    const url = new URL(link.attributes('href'))
    expect(url.searchParams.get('new_app')).toBe('1')
    const manifest = JSON.parse(url.searchParams.get('manifest_json'))
    expect(manifest).toEqual(SLACK_APP_MANIFEST)
    expect(manifest.oauth_config.scopes.bot).toEqual([
      'chat:write',
      'chat:write.public',
    ])
    expect(manifest.features.bot_user.display_name).toBe('Baserow')
  })

  test('shows only the token field when a token is already saved', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    expect(wrapper.find('a[href^="https://api.slack.com/apps"]').exists()).toBe(
      false
    )
    expect(wrapper.findAll('.slack-bot-form__step-marker')).toHaveLength(0)
    expect(wrapper.find('.form-input__input').exists()).toBe(true)
  })

  test('puts the token field in the third step of a new integration', async () => {
    const wrapper = await mountComponent({ defaultValues: {} })

    const steps = wrapper.findAll('.slack-bot-form__step')
    expect(steps).toHaveLength(3)
    expect(steps[2].find('.form-input__input').exists()).toBe(true)
  })

  test.each([{}, { has_token: true }])(
    'says who else can use the bot below the setup steps',
    async (defaultValues) => {
      const wrapper = await mountComponent({ defaultValues })

      const warning = wrapper.find('.slack-bot-form__warning')
      expect(warning.text()).toContain(
        'slackBotIntegrationType.slackBotWarning'
      )
      // After the private-channel note, which is the last of the help.
      const info = wrapper.find('.slack-bot-form__info').element
      expect(
        info.compareDocumentPosition(warning.element) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
    }
  )
})
