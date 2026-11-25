import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentChannelsSection from '@baserow_enterprise/components/agent/AgentChannelsSection'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'

const mocks = vi.hoisted(() => ({ service: {} }))

vi.mock('@baserow_enterprise/services/agentChannels', () => ({
  default: () => mocks.service,
}))

const publicChat = (values = {}) => ({
  id: 1,
  type: 'public_chat',
  enabled: true,
  slug: 'support',
  has_password: false,
  title: 'Support',
  welcome_text: '',
  ...values,
})

const failure = () =>
  Object.assign(new Error(), { handler: { notifyIf: vi.fn() } })

describe('agent channels', () => {
  let app, agent

  beforeEach(async () => {
    app = new TestApp()
    await app.store.dispatch('workspace/forceCreate', { id: 1, name: 'W' })
    agent = await app.store.dispatch('application/forceCreate', {
      id: 8,
      name: 'Support agent',
      type: 'agent',
      workspace: { id: 1 },
    })
    mocks.service = {
      list: vi.fn().mockResolvedValue({ data: [publicChat()] }),
      create: vi.fn(),
      update: vi.fn((agentId, channelId, values) =>
        Promise.resolve({
          data: publicChat({
            has_password: Boolean(values.password),
            ...values,
          }),
        })
      ),
      delete: vi.fn(),
    }
  })

  afterEach(async () => {
    await app.afterEach()
    vi.restoreAllMocks()
  })

  async function mountSection({
    licensed = true,
    editable = true,
    templatePreview = false,
  } = {}) {
    vi.spyOn(app.nuxtApp.$licenseHandler, 'hasFeature').mockImplementation(
      (feature) => licensed && feature === EnterpriseFeatures.RBAC
    )
    const wrapper = await app.mount(AgentChannelsSection, {
      props: {
        sectionType: app
          .getRegistry()
          .get('agentConfigurationSection', 'channels'),
        editable,
      },
      global: {
        provide: {
          agentApplication: ref(agent),
          agentTemplatePreview: templatePreview,
        },
        stubs: {
          PaidFeaturesModal: {
            template: '<div v-if="open" class="paywall"/>',
            data: () => ({ open: false }),
            methods: {
              show() {
                this.open = true
              },
            },
          },
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  const titleInput = (wrapper) =>
    wrapper.get('.agent-public-chat-card__title-input input')
  const inModal = (selector) => document.body.querySelector(selector)

  test('lists the agent channels, and says nobody outside can talk without any', async () => {
    const wrapper = await mountSection()
    expect(mocks.service.list).toHaveBeenCalledWith(8)
    expect(wrapper.findAll('.agent-public-chat-card')).toHaveLength(1)
    expect(wrapper.get('.agent-public-chat-card__name').text()).toBe('Support')

    mocks.service.list.mockResolvedValue({ data: [] })
    const empty = await mountSection()
    expect(empty.find('.agent-public-chat-card').exists()).toBe(false)
    expect(empty.get('.agent-channels__empty').text()).toBe(
      'agentChannels.empty'
    )

    mocks.service.list.mockClear()
    const preview = await mountSection({ templatePreview: true })
    expect(mocks.service.list).not.toHaveBeenCalled()
    expect(preview.find('.agent-channels__empty').exists()).toBe(true)
  })

  test('adds a public chat and opens its card', async () => {
    mocks.service.list.mockResolvedValue({ data: [] })
    mocks.service.create.mockResolvedValue({
      data: publicChat({ id: 5, title: '' }),
    })
    const wrapper = await mountSection()
    await wrapper.get('.agent-channels__add').trigger('click')
    await flushPromises()

    expect(mocks.service.create).toHaveBeenCalledWith(8, {
      type: 'public_chat',
    })
    const card = wrapper.get('.agent-public-chat-card')
    expect(card.get('.agent-public-chat-card__name').text()).toBe(
      'agentChannels.publicChat'
    )
    expect(
      card.get('.agent-public-chat-card__toggle').attributes('aria-expanded')
    ).toBe('true')
  })

  test('without Advanced or Enterprise, the add button opens the paywall', async () => {
    const wrapper = await mountSection({ licensed: false })
    const add = wrapper.get('.agent-channels__add')
    expect(add.find('.iconoir-lock').exists()).toBe(true)

    await add.trigger('click')
    expect(wrapper.find('.paywall').exists()).toBe(true)
    expect(mocks.service.create).not.toHaveBeenCalled()
  })

  test('saves a changed title once, and puts the old one back when it fails', async () => {
    mocks.service.update.mockRejectedValue(failure())
    const wrapper = await mountSection()
    const input = titleInput(wrapper)
    await input.setValue('Help desk')
    await input.trigger('blur')
    await flushPromises()

    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { title: 'Help desk' }],
    ])
    expect(input.element.value).toBe('Support')
    expect(wrapper.get('.agent-public-chat-card__name').text()).toBe('Support')
  })

  test('copies the public address of the chat', async () => {
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue()
    const wrapper = await mountSection()
    await wrapper.get('.agent-public-chat-card__copy').trigger('click')

    expect(writeText).toHaveBeenCalledWith(
      `${app.nuxtApp.$config.public.baserowEmbeddedShareUrl}/public/agent-chat/support`
    )
  })

  test('sets a password, and switching protection off sends an empty one', async () => {
    const wrapper = await mountSection()
    const protection = () =>
      wrapper.get('.agent-public-chat-card__password-switch')
    await protection().trigger('click')
    const password = inModal('.agent-public-chat-password-modal__input input')
    password.value = 'long secret'
    password.dispatchEvent(new Event('input'))
    inModal('.agent-public-chat-password-modal__save').click()
    await flushPromises()

    expect(inModal('.agent-public-chat-password-modal')).toBe(null)
    expect(protection().classes()).toContain('switch--active')
    await protection().trigger('click')
    inModal('.agent-public-chat-disable-password-modal__disable').click()
    await flushPromises()

    expect(protection().classes()).not.toContain('switch--active')
    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { password: 'long secret' }],
      [8, 1, { password: '' }],
    ])
  })

  test('sends two quick toggles one after the other and shows what the server last accepted', async () => {
    let answerFirst
    mocks.service.update
      .mockReturnValueOnce(new Promise((resolve) => (answerFirst = resolve)))
      .mockRejectedValueOnce(failure())
    const wrapper = await mountSection()
    const enabled = () => wrapper.get('.agent-public-chat-card__switch')
    await enabled().trigger('click')
    await enabled().trigger('click')
    await flushPromises()

    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { enabled: false }],
    ])
    answerFirst({ data: publicChat({ enabled: false }) })
    await flushPromises()

    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { enabled: false }],
      [8, 1, { enabled: true }],
    ])
    expect(enabled().classes()).not.toContain('switch--active')
  })

  test('a user who cannot update the agent gets no add button and disabled fields', async () => {
    const wrapper = await mountSection({ editable: false })

    expect(wrapper.find('.agent-channels__add').exists()).toBe(false)
    expect(titleInput(wrapper).element.disabled).toBe(true)
    expect(wrapper.findComponent(RichTextEditor).props('editable')).toBe(false)
    expect(wrapper.findAll('.switch--disabled')).toHaveLength(2)
    expect(wrapper.find('.agent-public-chat-card__delete').exists()).toBe(false)
  })
})
