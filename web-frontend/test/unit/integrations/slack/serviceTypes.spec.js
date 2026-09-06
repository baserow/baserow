import { TestApp } from '@baserow/test/helpers/testApp'

describe('SlackWriteMessageServiceType.getErrorMessage', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const serviceType = () =>
    testApp._app.$registry.get('service', 'slack_write_message')

  test('a half-filled service is described rather than thrown over', () => {
    // The form starts with `text: {}` and no channel, and the button editor
    // asks for this message on every render, so each step of filling the
    // form in has to be readable.
    const partial = [
      {},
      { integration_id: 1 },
      { integration_id: 1, channel: '' },
      { integration_id: 1, channel: 'general' },
      { integration_id: 1, channel: 'general', text: {} },
      { integration_id: 1, channel: 'general', text: { formula: '' } },
    ]
    for (const service of partial) {
      expect(() => serviceType().getErrorMessage({ service })).not.toThrow()
      expect(serviceType().getErrorMessage({ service })).toBeTruthy()
    }
  })

  test('a filled service has nothing to say', () => {
    const service = {
      integration_id: 1,
      channel: 'general',
      text: { formula: "'hi'" },
    }

    expect(serviceType().getErrorMessage({ service })).toBeFalsy()
  })
})
