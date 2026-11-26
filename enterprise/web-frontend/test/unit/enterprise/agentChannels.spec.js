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

const chatSettings = {
  enabled: true,
  title: 'Support',
  welcome_text: '',
  accent_color: '',
  background: 'gradient',
  background_color: '',
}

const publicChat = (values = {}) => ({
  id: 1,
  type: 'public_chat',
  slug: 'support',
  has_password: false,
  ...chatSettings,
  ...values,
})

const websiteWidget = (values = {}) => ({
  id: 2,
  type: 'website_widget',
  slug: 'widget',
  enabled: true,
  title: 'Support',
  welcome_text: '',
  accent_color: '',
  button_text: 'Chat with us',
  button_position: 'bottom_right',
  ...values,
})

const failure = () =>
  Object.assign(new Error(), {
    handler: {
      notifyIf: vi.fn(),
      getMessage: () => ({ title: 'Not saved', message: '' }),
      handled: vi.fn(),
    },
  })

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
    wrapper.get('.agent-public-chat-content__title-input input')
  const inModal = (selector) => document.body.querySelector(selector)

  async function addFromMenu(wrapper, label) {
    await wrapper.get('.agent-channels__add').trigger('click')
    await flushPromises()
    const item = [
      ...document.body.querySelectorAll('.menu-list__item-button'),
    ].find((button) => button.textContent.includes(label))
    item.click()
    await flushPromises()
  }

  test('lists the agent channels, and says nobody outside can talk without any', async () => {
    const wrapper = await mountSection()
    expect(mocks.service.list).toHaveBeenCalledWith(8)
    expect(wrapper.findAll('.agent-channel-card')).toHaveLength(1)
    expect(wrapper.get('.agent-channel-card__name').text()).toBe('Support')

    mocks.service.list.mockResolvedValue({ data: [] })
    const empty = await mountSection()
    expect(empty.find('.agent-channel-card').exists()).toBe(false)
    expect(empty.get('.agent-channels__empty').text()).toBe(
      'agentChannels.empty'
    )

    mocks.service.list.mockClear()
    const preview = await mountSection({ templatePreview: true })
    expect(mocks.service.list).not.toHaveBeenCalled()
    expect(preview.find('.agent-channels__empty').exists()).toBe(true)
  })

  test('adds a channel of the type picked in the menu and opens its card', async () => {
    mocks.service.list.mockResolvedValue({ data: [] })
    mocks.service.create.mockResolvedValue({
      data: publicChat({ id: 5, title: '' }),
    })
    const wrapper = await mountSection()
    await addFromMenu(wrapper, 'agentChannels.publicChat')

    expect(mocks.service.create).toHaveBeenCalledWith(8, {
      type: 'public_chat',
    })
    const card = wrapper.get('.agent-channel-card')
    expect(card.get('.agent-channel-card__name').text()).toBe(
      'agentChannels.publicChat'
    )
    expect(
      card.get('.agent-channel-card__toggle').attributes('aria-expanded')
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
    expect(wrapper.get('.agent-channel-card__name').text()).toBe('Support')
  })

  test('copies the public address of the chat', async () => {
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue()
    const wrapper = await mountSection()
    await wrapper.get('.agent-channel-copy-field__copy').trigger('click')

    expect(writeText).toHaveBeenCalledWith(
      `${app.nuxtApp.$config.public.baserowEmbeddedShareUrl}/public/agent-chat/support`
    )
  })

  test('a password shows as set only once saved, and a failed removal keeps it', async () => {
    let answerSet
    mocks.service.update
      .mockReturnValueOnce(new Promise((resolve) => (answerSet = resolve)))
      .mockRejectedValueOnce(failure())
    const wrapper = await mountSection()
    const protection = () =>
      wrapper.get('.agent-public-chat-form__password-switch')
    await protection().trigger('click')
    const password = inModal('.agent-public-chat-password-modal__input input')
    password.value = 'long secret'
    password.dispatchEvent(new Event('input'))
    inModal('.agent-public-chat-password-modal__save').click()
    await flushPromises()

    expect(
      inModal('.agent-public-chat-password-modal__save').classList
    ).toContain('button--loading')
    expect(protection().classes()).not.toContain('switch--active')
    answerSet({ data: publicChat({ has_password: true }) })
    await flushPromises()
    expect(inModal('.agent-public-chat-password-modal')).toBe(null)
    expect(protection().classes()).toContain('switch--active')

    await protection().trigger('click')
    inModal('.agent-public-chat-disable-password-modal__disable').click()
    await flushPromises()

    expect(
      inModal('.agent-public-chat-disable-password-modal__disable')
    ).not.toBe(null)
    expect(document.body.textContent).toContain('Not saved')
    expect(protection().classes()).toContain('switch--active')
    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { password: 'long secret' }],
      [8, 1, { password: '' }],
    ])
  })

  test('a welcome text whose markdown is too long is kept and not saved', async () => {
    const wrapper = await mountSection()
    const editor = wrapper.findComponent(RichTextEditor)
    editor.vm.editor.commands.setContent(
      `<p><strong>${'a'.repeat(1999)}</strong></p>`
    )
    editor.vm.$emit('update:modelValue', {})
    editor.vm.$emit('blur')
    await flushPromises()

    expect(mocks.service.update).not.toHaveBeenCalled()
    expect(editor.vm.serializeToMarkdown()).toBe(`**${'a'.repeat(1999)}**`)
    expect(wrapper.text()).toContain('agentChannels.welcomeTextTooLong')
  })

  test('without Advanced or Enterprise, a chat can only be switched off and deleted', async () => {
    const wrapper = await mountSection({ licensed: false })
    const enabled = () => wrapper.get('.agent-channel-card__switch')

    expect(titleInput(wrapper).element.disabled).toBe(true)
    expect(wrapper.findComponent(RichTextEditor).props('editable')).toBe(false)
    expect(
      wrapper.get('.agent-public-chat-form__password-switch').classes()
    ).toContain('switch--disabled')
    expect(wrapper.find('.agent-channel-card__delete').exists()).toBe(true)
    await enabled().trigger('click')
    await flushPromises()

    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { enabled: false }],
    ])
    expect(enabled().classes()).toContain('switch--disabled')
  })

  test('sends two quick toggles one after the other and shows what the server last accepted', async () => {
    let answerFirst
    mocks.service.update
      .mockReturnValueOnce(new Promise((resolve) => (answerFirst = resolve)))
      .mockRejectedValueOnce(failure())
    const wrapper = await mountSection()
    const enabled = () => wrapper.get('.agent-channel-card__switch')
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

  test('starts on Gradient and lets the builder choose Plain', async () => {
    const wrapper = await mountSection()
    const [gradient, plain] = wrapper.findAll(
      '.agent-public-chat-form__background .segment-control__button'
    )
    expect(gradient.classes()).toContain('segment-control__button--active')
    expect(gradient.text()).toBe('agentChannels.backgroundGradient')
    expect(wrapper.findAll('.agent-channel-color-field')).toHaveLength(2)
    await plain.trigger('click')
    await flushPromises()
    expect(mocks.service.update.mock.calls).toEqual([
      [8, 1, { background: 'plain' }],
    ])
  })

  test('without Advanced or Enterprise, the appearance cannot be changed', async () => {
    const wrapper = await mountSection({ licensed: false })
    const card = wrapper.get('.agent-channel-card')

    expect(card.get('.agent-channel-color-field').attributes()).toHaveProperty(
      'inert'
    )
    expect(
      card
        .findAll('.agent-public-chat-form__background .segment-control__button')
        .every((button) => button.attributes('disabled') !== undefined)
    ).toBe(true)
  })

  test('a user who cannot update the agent gets no add button and disabled fields', async () => {
    const wrapper = await mountSection({ editable: false })

    expect(wrapper.find('.agent-channels__add').exists()).toBe(false)
    expect(titleInput(wrapper).element.disabled).toBe(true)
    expect(wrapper.findComponent(RichTextEditor).props('editable')).toBe(false)
    expect(wrapper.findAll('.switch--disabled')).toHaveLength(2)
    expect(wrapper.find('.agent-channel-card__delete').exists()).toBe(false)
  })

  describe('website widget', () => {
    beforeEach(() => {
      mocks.service.list.mockResolvedValue({ data: [websiteWidget()] })
      mocks.service.update.mockImplementation((agentId, channelId, values) =>
        Promise.resolve({ data: websiteWidget(values) })
      )
    })

    test('is added with the translated button text, an accent color only, and its embed code', async () => {
      mocks.service.list.mockResolvedValue({ data: [] })
      mocks.service.create.mockResolvedValue({ data: websiteWidget() })
      const writeText = vi
        .spyOn(navigator.clipboard, 'writeText')
        .mockResolvedValue()
      const wrapper = await mountSection()
      await addFromMenu(wrapper, 'agentChannels.websiteWidget')

      expect(mocks.service.create).toHaveBeenCalledWith(8, {
        type: 'website_widget',
        button_text: 'agentChannels.defaultButtonText',
      })
      expect(wrapper.find('.agent-public-chat-form__password').exists()).toBe(
        false
      )
      expect(wrapper.find('.agent-public-chat-form__background').exists()).toBe(
        false
      )
      expect(wrapper.findAll('.agent-channel-color-field')).toHaveLength(1)
      await wrapper.get('.agent-channel-copy-field__copy').trigger('click')
      expect(writeText).toHaveBeenCalledWith(
        `<script src="${app.nuxtApp.$config.public.publicBackendUrl}/api/agent/public-chat/widget/widget.js" async></script>`
      )
    })

    test('saves a trimmed button text, an empty one, and its position', async () => {
      const wrapper = await mountSection()
      const text = wrapper.get('.agent-website-widget-form__button-text input')
      await text.setValue('  Ask us  ')
      await text.trigger('blur')
      await text.setValue('   ')
      await text.trigger('blur')
      const [left] = wrapper.findAll(
        '.agent-website-widget-form__position .segment-control__button'
      )
      await left.trigger('click')
      await flushPromises()

      expect(text.element.value).toBe('')
      expect(mocks.service.update.mock.calls).toEqual([
        [8, 2, { button_text: 'Ask us' }],
        [8, 2, { button_text: '' }],
        [8, 2, { button_position: 'bottom_left' }],
      ])
    })
  })
})
