import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import AgentTeamsFormField from '@baserow_enterprise/components/agents/AgentTeamsFormField'
import TeamService from '@baserow_enterprise/services/team'

vi.mock('@baserow_enterprise/services/team', () => ({
  default: vi.fn(),
}))

const RadioButtonStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: `
    <button
      class="team"
      :class="{ selected: modelValue }"
      @click="$emit('update:modelValue', !modelValue)"
    ><slot /></button>
  `,
}

const AlertStub = {
  template: '<div class="alert"><slot name="title" /><slot /></div>',
}

const ButtonStub = {
  emits: ['click'],
  template: '<button class="retry" @click="$emit(\'click\')"><slot /></button>',
}

describe('AgentTeamsFormField', () => {
  test('loads teams and emits selected team IDs', async () => {
    let resolveTeams
    const fetchAll = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveTeams = resolve
        })
    )
    TeamService.mockReturnValue({ fetchAll })

    const wrapper = await mountSuspended(AgentTeamsFormField, {
      props: {
        workspace: { id: 12 },
        modelValue: { name: 'Writer', team_ids: [1] },
      },
      global: {
        mocks: { $client: {}, $t: (key) => key },
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          RadioButton: RadioButtonStub,
          Alert: AlertStub,
          Button: ButtonStub,
        },
      },
    })

    expect(fetchAll).toHaveBeenCalledWith(12)
    expect(wrapper.find('.loading').exists()).toBe(true)

    resolveTeams({
      data: {
        results: [
          { id: 1, name: 'Engineering' },
          { id: 2, name: 'Support' },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('.loading').exists()).toBe(false)
    expect(wrapper.findAll('.team').map((team) => team.text())).toEqual([
      'Engineering',
      'Support',
    ])

    await wrapper.findAll('.team')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([
      { name: 'Writer', team_ids: [1, 2] },
    ])

    await wrapper.setProps({
      modelValue: { name: 'Writer', team_ids: [1, 2] },
    })
    await wrapper.findAll('.team')[0].trigger('click')
    expect(wrapper.emitted('update:modelValue')[1]).toEqual([
      { name: 'Writer', team_ids: [2] },
    ])
  })

  test('shows an error and retries when loading teams fails', async () => {
    const fetchAll = vi
      .fn()
      .mockRejectedValueOnce(new Error('Request failed'))
      .mockResolvedValueOnce({
        data: { results: [{ id: 1, name: 'Engineering' }] },
      })
    TeamService.mockReturnValue({ fetchAll })

    const wrapper = await mountSuspended(AgentTeamsFormField, {
      props: {
        workspace: { id: 12 },
        modelValue: { name: 'Writer', team_ids: [1] },
      },
      global: {
        mocks: { $client: {}, $t: (key) => key },
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          RadioButton: RadioButtonStub,
          Alert: AlertStub,
          Button: ButtonStub,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.loading').exists()).toBe(false)
    expect(wrapper.find('.alert').text()).toContain(
      'enterpriseAgents.teamsLoadError'
    )
    expect(wrapper.find('.agent-teams-form-field').exists()).toBe(false)

    await wrapper.find('.retry').trigger('click')
    await flushPromises()

    expect(fetchAll).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.alert').exists()).toBe(false)
    expect(wrapper.find('.team').text()).toBe('Engineering')
  })
})
