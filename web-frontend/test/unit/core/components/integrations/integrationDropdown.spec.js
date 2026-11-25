import { TestApp } from '@baserow/test/helpers/testApp'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import { SlackBotIntegrationType } from '@baserow/modules/integrations/slack/integrationTypes'

const APPLICATION = { id: 100, type: 'database', integrations: [] }
const SHARED_APPLICATION_ID = 99

// What the API returns: `application_id` tells the levels apart.
const own = (values) => ({ application_id: APPLICATION.id, ...values })
const ofWorkspace = (values) => ({
  application_id: SHARED_APPLICATION_ID,
  ...values,
})

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
      integrations: [own({ id: 9, name: 'Only bot' })],
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
      integrations: [own({ id: 9, name: 'Bot' })],
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

    await wrapper.setProps({ integrations: [own({ id: 9, name: 'Only bot' })] })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  test('the selected integration can be edited from the footer', async () => {
    // An export strips the token, so an imported bot arrives named and
    // unusable. A database has no integration settings page, so without this
    // there is nowhere to paste a new token.
    const wrapper = await mountDropdown({
      integrations: [own({ id: 9, name: 'Bot', token: '' })],
      modelValue: 9,
      allowEditing: true,
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    const editing = modals.find((modal) => !modal.props('create'))
    expect(editing.props('integration')).toMatchObject({ id: 9 })
  })

  test('a caller that has its own settings page is offered no edit', async () => {
    // Builder, automation and dashboard all have one. A second, less
    // discoverable route into the same modal is not worth having.
    const wrapper = await mountDropdown({
      integrations: [own({ id: 9, name: 'Bot', token: '' })],
      modelValue: 9,
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    expect(modals.every((modal) => modal.props('create'))).toBe(true)
  })

  test('nothing selected offers no edit', async () => {
    const wrapper = await mountDropdown({
      integrations: [own({ id: 9, name: 'Bot', token: '' })],
      allowEditing: true,
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    expect(modals.every((modal) => modal.props('create'))).toBe(true)
  })

  const sections = (wrapper) =>
    wrapper
      .findAllComponents({ name: 'DropdownSection' })
      .map((section) => [
        section.props('title'),
        section
          .findAllComponents({ name: 'DropdownItem' })
          .map((item) => item.props('name')),
      ])

  test('the workspace integrations are listed apart from the own ones', async () => {
    const wrapper = await mountDropdown({
      integrations: [
        own({ id: 9, name: 'Bot' }),
        ofWorkspace({ id: 12, name: 'Team bot' }),
        own({ id: 10, name: 'Alerts' }),
      ],
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    expect(sections(wrapper)).toEqual([
      ['integrationDropdown.applicationIntegrations', ['Bot', 'Alerts']],
      ['integrationDropdown.workspaceIntegrations', ['Team bot']],
    ])
  })

  test('the list looks as before when the workspace has none', async () => {
    const wrapper = await mountDropdown({
      integrations: [
        own({ id: 9, name: 'Bot' }),
        own({ id: 10, name: 'Alerts' }),
      ],
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    expect(sections(wrapper)).toEqual([])
    expect(
      wrapper
        .findAllComponents({ name: 'DropdownItem' })
        .map((item) => item.props('name'))
    ).toEqual(['Bot', 'Alerts'])
  })

  test('only the workspace section shows when the application has none', async () => {
    const wrapper = await mountDropdown({
      integrations: [ofWorkspace({ id: 12, name: 'Team bot' })],
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    expect(sections(wrapper)).toEqual([
      ['integrationDropdown.workspaceIntegrations', ['Team bot']],
    ])
  })

  test('a workspace integration says who it runs as', async () => {
    // It acts the same in every application, so whoever picks it should know
    // whose access it uses.
    const wrapper = await mountDropdown({
      integrationType: testApp.store.$registry.get(
        'integration',
        'local_baserow'
      ),
      integrations: [
        own({ id: 9, name: 'Own data' }),
        ofWorkspace({
          id: 12,
          name: 'Team data',
          authorized_subject: {
            id: 1,
            type: 'auth.User',
            first_name: 'Ada',
            username: 'ada@example.com',
          },
        }),
      ],
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const descriptions = Object.fromEntries(
      wrapper
        .findAllComponents({ name: 'DropdownItem' })
        .map((item) => [item.props('name'), item.props('description')])
    )
    expect(descriptions).toEqual({
      'Own data': null,
      'Team data': 'localBaserowIntegrationType.localBaserowWorkspaceHint',
    })
  })

  test('a selected workspace integration is not edited from here', async () => {
    // Editing it changes it for every application, which is done from the
    // workspace settings, by an Admin.
    const wrapper = await mountDropdown({
      integrations: [
        own({ id: 9, name: 'Bot', token: '' }),
        ofWorkspace({ id: 12, name: 'Team bot', token: '' }),
      ],
      modelValue: 12,
      allowEditing: true,
    })
    await wrapper.findComponent({ name: 'Dropdown' }).vm.show()
    await wrapper.vm.$nextTick()

    const modals = wrapper.findAllComponents(IntegrationCreateEditModal)
    expect(modals.every((modal) => modal.props('create'))).toBe(true)
    // Creating one still makes it the application's own.
    expect(modals[0].props('application')).toMatchObject({ id: APPLICATION.id })
  })
})

describe('IntegrationDropdown default priority', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    [[own({ id: 1 }), ofWorkspace({ id: 2 })], null, 1],
    [[ofWorkspace({ id: 2 })], null, 2],
    [[own({ id: 1 }), own({ id: 3 }), ofWorkspace({ id: 2 })], null, null],
    [[ofWorkspace({ id: 2 }), ofWorkspace({ id: 3 })], null, null],
    [[own({ id: 1 }), ofWorkspace({ id: 2 })], 2, null],
  ])(
    'selects only an unambiguous default (%j, selected %s)',
    async (integrations, modelValue, expected) => {
      const wrapper = await testApp.mount(IntegrationDropdown, {
        props: {
          application: { ...APPLICATION, type: 'builder' },
          integrationType: testApp.store.$registry.get(
            'integration',
            SlackBotIntegrationType.getType()
          ),
          integrations,
          modelValue,
          autoSelectFirst: true,
        },
      })
      expect(wrapper.emitted('update:modelValue')).toEqual(
        expected === null ? undefined : [[expected]]
      )
    }
  )
})
