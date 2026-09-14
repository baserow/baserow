import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import AgentApplicationForm from '@baserow_enterprise/components/agentApplication/AgentApplicationForm'

describe('AgentApplicationForm', () => {
  let mock = null

  beforeEach(() => {
    const { $client } = useNuxtApp()
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  async function mountForm() {
    return await mountSuspended(AgentApplicationForm, {
      props: {
        defaultName: 'Agent',
        loading: false,
        workspace: { id: 5, name: 'Workspace' },
      },
      global: {
        mocks: { $hasPermission: () => true },
      },
    })
  }

  test('a template chip fills the name and description', async () => {
    const wrapper = await mountForm()
    await wrapper.find('.agent-create__template').trigger('click')
    // Translations are not loaded in unit tests, so the keys render.
    expect(wrapper.vm.values.name).toBe('agentCreate.template_investName')
    expect(wrapper.vm.values.description).toBe(
      'agentCreate.template_investDescription'
    )
  })

  test('continue drafts the instructions and shows the review step', async () => {
    const wrapper = await mountForm()
    wrapper.vm.values.name = 'Finder'
    wrapper.vm.values.description = 'Find startups.'
    let draftBody = null
    mock
      .onPost('agent_application/workspace/5/instructions/draft/')
      .replyOnce((config) => {
        draftBody = JSON.parse(config.data)
        return [200, { instructions: '## Goal\nFind startups.' }]
      })
    mock
      .onGet(/agents/)
      .replyOnce(200, { results: [{ id: 3, name: 'Investor' }] })

    await wrapper.vm.continueToReview()
    await flushPromises()

    expect(draftBody).toEqual({ name: 'Finder', description: 'Find startups.' })
    expect(wrapper.vm.step).toBe(2)
    expect(wrapper.vm.values.instructions).toBe('## Goal\nFind startups.')
    expect(wrapper.text()).toContain('agentCreate.reviewTitle')
  })

  test('a blank description skips drafting', async () => {
    const wrapper = await mountForm()
    wrapper.vm.values.name = 'Finder'
    mock.onGet(/agents/).replyOnce(200, { results: [] })

    await wrapper.vm.continueToReview()
    await flushPromises()

    expect(mock.history.post).toHaveLength(0)
    expect(wrapper.vm.step).toBe(2)
  })

  test('the submitted values carry the setup choices', async () => {
    const wrapper = await mountForm()
    wrapper.vm.values.name = 'Finder'
    wrapper.vm.values.instructions = 'Do things.'
    wrapper.vm.values.run_mode = 'daily'
    wrapper.vm.values.web_search = true
    wrapper.vm.identityChoice = 'new'
    expect(wrapper.vm.getFormValues()).toEqual({
      name: 'Finder',
      description: '',
      instructions: 'Do things.',
      run_mode: 'daily',
      web_search: true,
      create_identity: true,
      permissions: 'ask_first',
    })

    wrapper.vm.identityChoice = 3
    expect(wrapper.vm.getFormValues().agent_identity_id).toBe(3)

    // Without an identity the permission preset is meaningless.
    wrapper.vm.identityChoice = 'none'
    const values = wrapper.vm.getFormValues()
    expect(values.permissions).toBeUndefined()
    expect(values.create_identity).toBeUndefined()
  })
})
