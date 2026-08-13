import PresenceBar from '@baserow/modules/core/components/presence/PresenceBar'
import { ANONYMOUS_USER_ID } from '@baserow/modules/core/utils/presenceColors'
import { TestApp } from '@baserow/test/helpers/testApp'

const SPACE = 'table-1'

describe('PresenceBar component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const seed = (entries) =>
    testApp.store.commit('presence/SET_MEMBERS', { space: SPACE, entries })

  // `maxVisible` comes from runtime config and defaults to 3, which is fewer
  // than some of the cases below. Raised past every badge count so the
  // overflow slice can never be what makes an assertion pass.
  const mountComponent = () =>
    testApp.mount(PresenceBar, {
      props: { spaceName: SPACE },
      global: {
        mocks: { $config: { public: { baserowPresenceVisibleUsers: '10' } } },
      },
    })

  const badges = (wrapper) => wrapper.findAll('.presence-bar__avatar')

  const anonymous = (presenceId) => ({
    presence_id: presenceId,
    user_id: ANONYMOUS_USER_ID,
  })

  // `ANONYMOUS_USER_ID` is a module import, so a template referencing it
  // directly resolves it against the instance, finds nothing, and Vue warns on
  // every render. The comparison then silently evaluates against `undefined`,
  // which is never equal to a user id, so every anonymous visitor falls through
  // to the same `user_id` key.
  test('renders without warning about an undefined property', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    seed([anonymous('pid-a'), anonymous('pid-b')])
    await mountComponent()

    const messages = warn.mock.calls.map((call) => call.join(' '))
    warn.mockRestore()

    expect(messages.filter((m) => m.includes('ANONYMOUS_USER_ID'))).toEqual([])
  })

  test('renders a badge per anonymous visitor', async () => {
    seed([anonymous('pid-1'), anonymous('pid-2'), anonymous('pid-3')])

    const wrapper = await mountComponent()

    expect(badges(wrapper)).toHaveLength(3)
  })

  test('renders a badge per signed in user alongside anonymous ones', async () => {
    seed([
      { presence_id: 'pid-1', user_id: 10 },
      { presence_id: 'pid-2', user_id: 20 },
      anonymous('pid-3'),
      anonymous('pid-4'),
    ])

    const wrapper = await mountComponent()

    expect(badges(wrapper)).toHaveLength(4)
  })

  test('renders nothing when the space has no other users', async () => {
    seed([])

    const wrapper = await mountComponent()

    expect(wrapper.find('.presence-bar').exists()).toBe(false)
  })
})
