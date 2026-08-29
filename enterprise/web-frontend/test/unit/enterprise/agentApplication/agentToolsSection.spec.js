import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import AgentToolsSection from '@baserow_enterprise/components/agentApplication/AgentToolsSection'

const RadioGroupStub = defineComponent({
  name: 'RadioGroup',
  props: ['modelValue', 'options', 'type'],
  emits: ['input', 'update:modelValue'],
  template: `
    <div class="radio-group-stub">
      <button
        v-for="option in options"
        :key="option.value"
        class="radio-stub"
        :data-value="option.value"
        @click="$emit('input', option.value)"
      >{{ option.label }}</button>
    </div>`,
})

const SwitchInputStub = defineComponent({
  name: 'SwitchInput',
  props: ['value', 'disabled', 'small'],
  emits: ['input'],
  template: `
    <button
      class="switch-stub"
      :data-value="value"
      @click="$emit('input', !value)"
    ><slot /></button>`,
})

const ContextStub = defineComponent({
  name: 'Context',
  template: '<div class="context-stub" style="display: none"><slot /></div>',
})

describe('AgentToolsSection workspace tool configuration', () => {
  let store = null
  let mock = null

  const application = {
    id: 42,
    agent_identity_id: 7,
    workspace: { id: 5 },
  }

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  async function mountSection(workspaceConfig) {
    mock
      .onGet('agent_application/42/tools/')
      .replyOnce(200, [
        { id: 1, type: 'workspace', name: '', config: workspaceConfig },
      ])
    await store.dispatch('agentApplication/fetchTools', { applicationId: 42 })

    return await mountSuspended(AgentToolsSection, {
      props: { application },
      global: {
        stubs: {
          RadioGroup: RadioGroupStub,
          SwitchInput: SwitchInputStub,
          Context: ContextStub,
          AgentGroupedAddMenu: true,
        },
        mocks: {
          $hasPermission: () => true,
        },
      },
    })
  }

  test('switching to read only merges the mode into the existing config', async () => {
    const wrapper = await mountSection({ custom_key: 'kept' })

    let requestBody = null
    mock.onPatch('agent_application/tools/1/').replyOnce((config) => {
      requestBody = JSON.parse(config.data)
      return [
        200,
        {
          id: 1,
          type: 'workspace',
          name: '',
          config: requestBody.config,
        },
      ]
    })

    await wrapper.find('.radio-stub[data-value="read_only"]').trigger('click')
    await flushPromises()

    expect(requestBody).toStrictEqual({
      config: { custom_key: 'kept', mode: 'read_only' },
    })
    // In read only mode nothing writes, so the approval switch disappears.
    expect(
      wrapper.find('.agent-configuration__tool-options').findAll('.switch-stub')
        .length
    ).toBe(0)
  })

  test('toggling write approval merges the flag into the existing config', async () => {
    const wrapper = await mountSection({ custom_key: 'kept' })

    let requestBody = null
    mock.onPatch('agent_application/tools/1/').replyOnce((config) => {
      requestBody = JSON.parse(config.data)
      return [
        200,
        {
          id: 1,
          type: 'workspace',
          name: '',
          config: requestBody.config,
        },
      ]
    })

    // Defaults to on, so the first toggle turns the approval requirement off.
    await wrapper
      .find('.agent-configuration__tool-options .switch-stub')
      .trigger('click')
    await flushPromises()

    expect(requestBody).toStrictEqual({
      config: { custom_key: 'kept', require_write_approval: false },
    })
  })

  test('selecting the already active mode does not save', async () => {
    const wrapper = await mountSection({})

    await wrapper.find('.radio-stub[data-value="read_write"]').trigger('click')
    await flushPromises()

    // No PATCH handler is registered, so a request would throw.
    expect(mock.history.patch.length).toBe(0)
  })
})
