import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import AgentContext from '@baserow/modules/core/components/settings/agents/AgentContext'
import AgentGeneralSettingsForm from '@baserow/modules/core/components/settings/agents/AgentGeneralSettingsForm'
import AgentLastActiveField from '@baserow/modules/core/components/settings/agents/AgentLastActiveField'

const ContextStub = { template: '<div><slot /></div>' }

describe('Agent settings components', () => {
  test('emits edit and deletes the selected agent', async () => {
    const agent = { id: 34, name: 'Writer' }
    const dispatch = vi.fn().mockResolvedValue({})
    const hide = vi.fn()
    const wrapper = await mountSuspended(
      { ...AgentContext, methods: { ...AgentContext.methods, hide } },
      {
        props: { agent, canUpdate: true, canDelete: true },
        global: {
          mocks: { $store: { dispatch }, $t: (key) => key },
          stubs: { Context: ContextStub },
        },
      }
    )

    const actions = wrapper.findAll('.context__menu-item-link')
    await actions[0].trigger('click')
    expect(wrapper.emitted('edit')).toEqual([[]])

    await actions[1].trigger('click')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('agent/delete', agent)
    expect(wrapper.emitted('deleted')).toEqual([[34]])
    expect(hide).toHaveBeenCalledTimes(2)
  })

  test.each([
    [null, '—'],
    [
      '2026-09-14T12:00:00Z',
      new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
        new Date('2026-09-14T12:00:00Z')
      ),
    ],
  ])('formats the last active value %s', async (lastActive, expected) => {
    const wrapper = await mountSuspended(AgentLastActiveField, {
      props: { row: { last_active: lastActive } },
    })

    expect(wrapper.text()).toBe(expected)
  })

  test('emits immutable name and role updates', async () => {
    const modelValue = { name: 'Writer', role_uid: 'MEMBER', untouched: true }
    const wrapper = await mountSuspended(AgentGeneralSettingsForm, {
      props: {
        modelValue,
        workspace: { id: 12 },
        roles: [],
      },
      global: {
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template:
              '<button class="name" @click="$emit(\'update:modelValue\', \'Editor\')" />',
          },
          WorkspaceRoleSelector: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template:
              '<button class="role" @click="$emit(\'update:modelValue\', \'ADMIN\')" />',
          },
        },
      },
    })

    await wrapper.find('.name').trigger('click')
    await wrapper.find('.role').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{ name: 'Editor', role_uid: 'MEMBER', untouched: true }],
      [{ name: 'Writer', role_uid: 'ADMIN', untouched: true }],
    ])
    expect(modelValue).toEqual({
      name: 'Writer',
      role_uid: 'MEMBER',
      untouched: true,
    })
  })
})
