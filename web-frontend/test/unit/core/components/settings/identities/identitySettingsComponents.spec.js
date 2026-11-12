import { defineComponent, nextTick, ref } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import IdentityContext from '@baserow/modules/core/components/settings/identities/IdentityContext'
import IdentityGeneralSettingsForm from '@baserow/modules/core/components/settings/identities/IdentityGeneralSettingsForm'
import IdentityLastActiveField from '@baserow/modules/core/components/settings/identities/IdentityLastActiveField'

const ContextStub = { template: '<div><slot /></div>' }

describe('Identity settings components', () => {
  test('emits edit and deletes the selected identity', async () => {
    const identity = { id: 34, name: 'Writer' }
    const dispatch = vi.fn().mockResolvedValue({})
    const hide = vi.fn()
    const wrapper = await mountSuspended(
      { ...IdentityContext, methods: { ...IdentityContext.methods, hide } },
      {
        props: { identity, canUpdate: true, canDelete: true },
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
    expect(dispatch).toHaveBeenCalledWith('identity/delete', identity)
    expect(wrapper.emitted('deleted')).toEqual([[34]])
    expect(hide).toHaveBeenCalledTimes(2)
  })

  test('deleting an identity can unmount its menu before the request resolves', async () => {
    const visible = ref(true)
    const errors = []
    const identity = { id: 34, name: 'Writer' }
    const dispatch = vi.fn(async () => {
      visible.value = false
      await nextTick()
    })
    const Harness = defineComponent({
      components: { IdentityContext },
      setup: () => ({ visible, identity }),
      template:
        '<IdentityContext v-if="visible" :identity="identity" can-update can-delete />',
    })
    const wrapper = await mountSuspended(Harness, {
      global: {
        config: { errorHandler: (error) => errors.push(error) },
        mocks: { $store: { dispatch }, $t: (key) => key },
        stubs: { Context: ContextStub },
      },
    })

    await wrapper.find('.context__menu-item-link--delete').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('identity/delete', identity)
    expect(wrapper.find('.context__menu').exists()).toBe(false)
    expect(errors).toEqual([])
    wrapper.unmount()
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
    const wrapper = await mountSuspended(IdentityLastActiveField, {
      props: { row: { last_active: lastActive } },
    })

    expect(wrapper.text()).toBe(expected)
  })

  test('emits immutable name and role updates', async () => {
    const modelValue = { name: 'Writer', role_uid: 'MEMBER', untouched: true }
    const wrapper = await mountSuspended(IdentityGeneralSettingsForm, {
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

test('only recommends No access when the role is available', async () => {
  const wrapper = await mountSuspended(IdentityGeneralSettingsForm, {
    props: {
      modelValue: { name: 'Writer', role_uid: 'MEMBER' },
      workspace: { id: 12 },
      roles: [{ uid: 'NO_ACCESS', isDeactivated: true }],
    },
    global: { stubs: { WorkspaceRoleSelector: true } },
  })
  expect(wrapper.find('.control__helper-text').exists()).toBe(false)
  await wrapper.setProps({
    roles: [{ uid: 'NO_ACCESS', isDeactivated: false }],
  })
  expect(wrapper.get('.control__helper-text').text()).toBe(
    'identities.roleHelpText'
  )
  wrapper.unmount()
})
