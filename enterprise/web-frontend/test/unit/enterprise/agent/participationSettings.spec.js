import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentParticipationSettings from '@baserow_enterprise/components/agent/AgentParticipationSettings'

describe('agent participation settings', () => {
  let app
  beforeEach(() => {
    app = new TestApp()
  })
  afterEach(async () => {
    await app.afterEach()
    vi.restoreAllMocks()
  })

  const endpoint = '/agent-permissions/8/'
  const editor = { role: 'EDITOR', subjects: [] }
  function mockRules(chat = editor, approve = editor) {
    app.mock.onGet(endpoint).reply(200, { chat, approve })
    vi.spyOn(app.store, 'dispatch').mockResolvedValue()
  }

  async function choose(wrapper, index, roleLabel) {
    const field = wrapper.findAll('.control')[index]
    await field.get('.dropdown__selected').trigger('click')
    await field
      .findAll('.select__item-link')
      .find((item) => item.text().includes(roleLabel))
      .trigger('click')
    await flushPromises()
  }

  function mount(licensed, editable = true) {
    const nuxt = Object.create(app.nuxtApp)
    Object.defineProperty(nuxt, '$hasFeature', { value: () => licensed })
    return app.mount(AgentParticipationSettings, {
      props: { agent: { id: 8 }, workspace: { id: 1 }, editable },
      global: {
        plugins: [
          {
            install: (instance) => {
              instance.$nuxt = nuxt
            },
          },
        ],
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
  }

  test('opens the RBAC paywall without fetching rules', async () => {
    const wrapper = await mount(false)
    await wrapper.get('.control button').trigger('click')
    expect(wrapper.find('.paywall').exists()).toBe(true)
    expect(app.mock.history.get).toHaveLength(0)
  })

  test('renders saved roles for a read-only configuration viewer', async () => {
    mockRules(
      { role: 'BUILDER', subjects: [] },
      { role: 'NOBODY', subjects: [] }
    )
    const wrapper = await mount(true, false)
    expect(
      wrapper
        .findAll('.dropdown--disabled .dropdown__selected-text')
        .map((item) => item.text())
    ).toEqual(['fieldPermissionModal.builderTitle', 'agentPermissions.NOBODY'])
  })

  test('disables Nobody until a trigger exists and applies valid roles immediately', async () => {
    mockRules()
    app.mock
      .onPut(endpoint + 'chat/')
      .reply(200, { role: 'NOBODY', subjects: [] })
    const wrapper = await mount(true)
    await choose(wrapper, 0, 'agentPermissions.NOBODY')
    expect(wrapper.get('.select__item.disabled').text()).toContain(
      'agentPermissions.needsTrigger'
    )
    expect(app.mock.history.put).toHaveLength(0)
    await wrapper.setProps({ hasTrigger: true })
    await choose(wrapper, 0, 'agentPermissions.NOBODY')
    expect(JSON.parse(app.mock.history.put[0].data)).toEqual({
      role: 'NOBODY',
      subjects: [],
    })
    expect(wrapper.get('.dropdown__selected-text').text()).toBe(
      'agentPermissions.NOBODY'
    )
    expect(document.querySelector('.modal__box')).toBeNull()
  })

  test('can change the other permission while the first request is pending', async () => {
    mockRules()
    let finishChat
    app.mock.onPut(endpoint + 'chat/').reply(
      () =>
        new Promise((resolve) => {
          finishChat = resolve
        })
    )
    app.mock
      .onPut(endpoint + 'approve/')
      .reply(200, { role: 'ADMIN', subjects: [] })
    const wrapper = await mount(true)
    await choose(wrapper, 0, 'fieldPermissionModal.builderTitle')
    await choose(wrapper, 1, 'fieldPermissionModal.adminTitle')
    expect(app.mock.history.put).toHaveLength(2)
    finishChat([200, { role: 'BUILDER', subjects: [] }])
    await flushPromises()
    expect(
      wrapper.findAll('.dropdown__selected-text').map((item) => item.text())
    ).toEqual([
      'fieldPermissionModal.builderTitle',
      'fieldPermissionModal.adminTitle',
    ])
  })

  test('restores the saved role when an immediate change fails', async () => {
    mockRules()
    app.dontFailOnErrorResponses()
    app.mock.onPut(endpoint + 'approve/').reply(500, {})
    const wrapper = await mount(true)
    await choose(wrapper, 1, 'fieldPermissionModal.builderTitle')
    expect(app.mock.history.put).toHaveLength(1)
    expect(wrapper.findAll('.dropdown__selected-text')[1].text()).toBe(
      'fieldPermissionModal.editorTitle'
    )
    expect(wrapper.findAll('.dropdown--disabled')).toHaveLength(0)
  })

  test('applies a removal from an existing custom rule without a separate save', async () => {
    const team = (id, name) => ({
      subject_type: 'baserow_enterprise.Team',
      subject_id: id,
      subject: { id, name },
    })
    const support = team(21, 'Support')
    const finance = team(22, 'Finance')
    const rule = { role: 'CUSTOM', subjects: [support, finance] }
    mockRules(editor, rule)
    app.mock
      .onPut(endpoint + 'approve/')
      .reply(200, { ...rule, subjects: [finance] })
    const wrapper = await mount(true)
    await wrapper.get('.control button').trigger('click')
    const modal = () => document.querySelector('.modal__box')
    modal().querySelector('.field-permission-subjects__item button').click()
    await flushPromises()
    expect(app.mock.history.put).toHaveLength(1)
    expect(JSON.parse(app.mock.history.put[0].data)).toEqual({
      role: 'CUSTOM',
      subjects: [
        { subject_type: finance.subject_type, subject_id: finance.subject_id },
      ],
    })
    expect(
      modal().querySelector('.field-permission-subjects__list').textContent
    ).toContain('Finance')
    expect(
      modal().querySelector('.field-permission-subjects__item button').disabled
    ).toBe(true)
  })

  test('starts a custom rule with the first person or team and keeps at least one', async () => {
    const teamType = 'baserow_enterprise.Team'
    const team = {
      subject_type: teamType,
      subject_id: 21,
      subject: { id: 21, name: 'Support' },
    }
    mockRules()
    app.mock.onGet(endpoint + 'options/').reply(200, {
      count: 1,
      results: [
        {
          subject_type: teamType,
          subject_id: 21,
          name: 'Support',
          subject_count: 2,
        },
      ],
    })
    app.mock
      .onPut(endpoint + 'approve/')
      .reply(200, { role: 'CUSTOM', subjects: [team] })
    const wrapper = await mount(true)
    await choose(wrapper, 1, 'agentPermissions.CUSTOM')
    const modal = () => document.querySelector('.modal__box')
    expect(modal()).toBeTruthy()
    expect(app.mock.history.put).toHaveLength(0)
    modal().querySelector('.dropdown__selected').click()
    await flushPromises()
    await wrapper.setProps({ workspace: { id: 1, _: { permissions: [] } } })
    await flushPromises()
    expect(modal().querySelector('.dropdown__items.hidden')).toBeNull()
    modal().querySelector('.select__item-link').click()
    await flushPromises()
    expect(app.mock.history.put).toHaveLength(1)
    expect(JSON.parse(app.mock.history.put[0].data)).toEqual({
      role: 'CUSTOM',
      subjects: [{ subject_type: teamType, subject_id: 21 }],
    })
    expect(
      modal().querySelector('.field-permission-subjects__item button').disabled
    ).toBe(true)
    expect(wrapper.findAll('.control')[1].text()).toContain(
      'agentPermissions.managePeople'
    )
  })
})
