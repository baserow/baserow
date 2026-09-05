import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'

// Read rather than imported: the i18n loader turns an imported locale file
// into compiled message ASTs, which the copy below can't be read off of.
const en = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'modules/integrations/locales/en.json'),
    'utf8'
  )
)

describe('SlackBotIntegrationType', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const integrationType = () =>
    testApp._app.$registry.get('integration', 'slack_bot')

  test('entering a token says who else will be able to use it', () => {
    // A database's integrations are shared by everyone who can build in it,
    // and the create modal is where that decision gets made. Ownership would
    // remove the need for this (ADR 006 section 5).
    expect(integrationType().warning).toBe(
      'slackBotIntegrationType.slackBotWarning'
    )
    expect(en.slackBotIntegrationType.slackBotWarning).toBe(
      'Anyone who can build in this application can send messages through ' +
        'this bot, without seeing the token. Use a bot whose access you are ' +
        'happy to share.'
    )
  })

  test('a bot with no token is summarised as unconfigured', () => {
    expect(integrationType().getSummary({ token: '' })).toBe(
      'slackBotIntegrationType.slackBotNoToken'
    )
    expect(integrationType().getSummary({ token: 'xoxb-real' })).toBe(
      'slackBotIntegrationType.slackBotSummary'
    )
  })
})
