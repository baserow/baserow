import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, describe } from 'vitest'

import ViewOwnershipMenuLink from '@baserow_premium/components/views/ViewOwnershipMenuLink'

describe('ViewOwnershipMenuLink permission gating', () => {
  const database = {
    id: 1,
    workspace: { id: 10 },
  }

  const collaborativeView = {
    id: 100,
    name: 'My View',
    ownership_type: 'collaborative',
  }

  const personalView = {
    id: 101,
    name: 'My Personal View',
    ownership_type: 'personal',
    owned_by_id: 256,
  }

  const mountComponent = (view, hasPermission) =>
    mountSuspended(ViewOwnershipMenuLink, {
      props: { view, database },
      global: {
        mocks: {
          $hasPermission: hasPermission,
          $hasFeature: () => true,
          $registry: {
            get(type, name) {
              return {
                getType: () => name,
                isDeactivated: () => false,
              }
            },
          },
        },
        stubs: {
          PaidFeaturesModal: true,
        },
      },
    })

  test('shows button on collaborative view when user has view update permission', async () => {
    const wrapper = await mountComponent(
      collaborativeView,
      () => true
    )
    expect(wrapper.find('.context__menu-item').exists()).toBe(true)
  })

  test('hides button on collaborative view when user lacks view update permission', async () => {
    const wrapper = await mountComponent(
      collaborativeView,
      () => false
    )
    expect(wrapper.find('.context__menu-item').exists()).toBe(false)
  })

  test('shows button on personal view when user has view update permission on collaborative target', async () => {
    const wrapper = await mountComponent(
      personalView,
      () => true
    )
    expect(wrapper.find('.context__menu-item').exists()).toBe(true)
  })

  test('hides button on personal view when user lacks view update permission', async () => {
    const wrapper = await mountComponent(
      personalView,
      () => false
    )
    expect(wrapper.find('.context__menu-item').exists()).toBe(false)
  })

  test('hides button on personal view when user can update personal but not collaborative', async () => {
    const wrapper = await mountComponent(
      personalView,
      (_operation, context) => context.ownership_type === 'personal'
    )
    expect(wrapper.find('.context__menu-item').exists()).toBe(false)
  })

  test('checks permission against target ownership type, not current', async () => {
    const calls = []
    await mountComponent(
      personalView,
      (operation, context) => {
        calls.push({ operation, ownershipType: context.ownership_type })
        return true
      }
    )
    expect(calls).toContainEqual({
      operation: 'database.table.view.update',
      ownershipType: 'collaborative',
    })
  })
})
