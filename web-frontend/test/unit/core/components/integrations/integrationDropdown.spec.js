import { TestApp } from '@baserow/test/helpers/testApp'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import { SlackBotIntegrationType } from '@baserow/modules/integrations/slack/integrationTypes'

const APPLICATION = { id: 100, type: 'database', integrations: [] }

describe('IntegrationDropdown', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountDropdown = async (props = {}) =>
    testApp.mount(IntegrationDropdown, {
      props: {
        application: APPLICATION,
        integrations: [],
        integrationType: testApp.store.$registry.get(
          'integration',
          SlackBotIntegrationType.getType()
        ),
        ...props,
      },
    })

  test('creating an integration selects it through the v-model event', async () => {
    // A parent binds this with `v-model`, which in Vue 3 listens for
    // `update:modelValue` and nothing else. Emitting only `input` drops the
    // selection of the bot that was just created.
    const wrapper = await mountDropdown()
    // The footer, and so the modal, only renders while the dropdown is open.
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    wrapper
      .findComponent(IntegrationCreateEditModal)
      .vm.$emit('created', { id: 7, name: 'Bot' })

    expect(wrapper.emitted('update:modelValue')).toEqual([[7]])
  })

  test('the only integration is selected through the v-model event too', async () => {
    const wrapper = await mountDropdown({ autoSelectFirst: true })

    await wrapper.setProps({
      integrations: [{ id: 9, name: 'Only bot' }],
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toEqual([[9]])
  })

  test('the footer takes focus and answers the keyboard', async () => {
    // An anchor with no `href` is skipped by tab and answers no key, which
    // makes creating the first bot unreachable without a mouse.
    const wrapper = await mountDropdown()
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const footer = wrapper.find('.select__footer-button')
    expect(footer.element.tagName).toBe('BUTTON')
    expect(footer.attributes('type')).toBe('button')
  })

  test('picking one from the list reaches the parent both ways', async () => {
    // Declaring `update:modelValue` keeps a parent's listener out of
    // `$attrs`, so it no longer falls through to the dropdown below. This
    // component has to re-emit it or the list stops selecting anything.
    const wrapper = await mountDropdown({
      integrations: [{ id: 9, name: 'Bot' }],
    })

    wrapper.findComponent({ name: 'Dropdown' }).vm.$emit('input', 9)

    expect(wrapper.emitted('update:modelValue')).toEqual([[9]])
    expect(wrapper.emitted('input')).toEqual([[9]])
  })

  test('the only integration is not auto-selected over one already chosen', async () => {
    // The guard has to read what the parent bound, which under `v-model`
    // arrives as `modelValue` and never as `value`.
    const wrapper = await mountDropdown({
      autoSelectFirst: true,
      modelValue: 3,
    })

    await wrapper.setProps({ integrations: [{ id: 9, name: 'Only bot' }] })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  test('the selected integration can be edited from the footer', async () => {
    // An export strips the token, so an imported bot arrives named and
    // unusable. A database has no integration settings page, so without this
    // there is nowhere to paste a new token.
    const wrapper = await mountDropdown({
      integrations: [{ id: 9, name: 'Bot', token: '' }],
      modelValue: 9,
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    const editing = modals.find((modal) => !modal.props('create'))
    expect(editing.props('integration')).toMatchObject({ id: 9 })
  })

  test('nothing selected offers no edit', async () => {
    const wrapper = await mountDropdown({
      integrations: [{ id: 9, name: 'Bot', token: '' }],
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    expect(modals.every((modal) => modal.props('create'))).toBe(true)
  })
})
