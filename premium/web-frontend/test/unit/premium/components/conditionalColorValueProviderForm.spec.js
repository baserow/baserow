import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

import ConditionalColorValueProviderForm from '@baserow_premium/components/views/ConditionalColorValueProviderForm.vue'
import { afterEach } from 'vitest'

let nextFilterUuid = 100
const mockUuid = () => nextFilterUuid++

vi.mock('@baserow/modules/core/utils/string', () => ({
  uuid: () => mockUuid(),
}))

vi.mock('uuid', () => ({
  v1: () => mockUuid(),
  v4: () => mockUuid(),
}))

describe('ConditionalColorValueProviderForm', () => {
  let testApp = {}
  const workspace = { id: 1, users: [] }
  const database = { id: 1, workspace_id: 1 }
  const table = { id: 2, database_id: 1 }
  const fields = [
    {
      id: 10,
      name: 'Name',
      type: 'text',
      primary: true,
    },
  ]
  const viewId = 3
  const testView = { id: viewId, type: 'grid', table_id: 2 }
  const basePropsData = {
    database,
    table,
    fields,
    options: {
      colors: [],
    },
    readOnly: false,
  }

  beforeEach(() => {
    testApp = new PremiumTestApp()

    nextFilterUuid = 100

    testApp.store.dispatch('workspace/forceCreate', workspace)
    testApp.store.commit('workspace/SET_SELECTED', workspace)
    testApp.store.dispatch('view/forceCreate', { data: { ...testView } })
  })

  afterEach(() => testApp.afterEach())

  test('can add a condition', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const color = { id: 1, operator: 'AND', color: 'red', filters: [] }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: { colors: [color] },
      },
    })

    // Initially no filters are present
    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(0)

    // Find the "Add condition" button and click it to add a new condition
    wrapper
      .find('.conditional-color-value-provider-form__color-filter-add')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [
      {
        ...color,
        filters: [
          {
            id: 100,
            field: 10,
            type: 'equal',
            value: '',
            preload_values: {},
            group: null,
          },
        ],
      },
    ]

    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])
    await wrapper.setProps({ options: { colors: expectedColors } })

    // The condition should be visible now
    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)
  })

  test('can remove a condition', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filters: [
        {
          id: 100,
          field: 10,
          type: 'equal',
          value: '',
          group: null,
        },
      ],
    }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: {
          colors: [color],
        },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    wrapper.find('.filters__remove').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [{ ...color, filters: [] }]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])

    await wrapper.setProps({ options: { colors: expectedColors } })
    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(0)
  })

  test('can change the operator from AND to OR', async () => {
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filters: [
        {
          id: 100,
          field: 10,
          type: 'equal',
          value: '',
        },
        {
          id: 101,
          field: 10,
          type: 'equal',
          value: '',
        },
      ],
    }
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: {
          colors: [color],
        },
      },
      mocks: { $t: (key) => key, $store: app.$store, $registry: app.$registry },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(2)

    wrapper
      .findAllComponents({ name: 'ViewFilterFormOperator' })
      .at(1)
      .findAllComponents({ name: 'DropdownItem' })
      .at(1)
      .find('a')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    expect(wrapper.emitted('update')[0]).toEqual([
      {
        colors: [
          {
            ...color,
            operator: 'OR', // The operator has been changed from AND to OR
          },
        ],
      },
    ])
  })

  test('can add a condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const color = { id: 1, operator: 'AND', color: 'red', filters: [] }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: { colors: [color] },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(0)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(0)

    wrapper
      .find('.conditional-color-value-provider-form__color-filter-group-add')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [
      {
        ...color,
        filter_groups: [
          {
            id: 100,
            filter_type: 'AND',
            parent_group: null,
          },
        ],
        filters: [
          {
            id: 101,
            field: 10,
            type: 'equal',
            value: '',
            preload_values: {},
            group: 100,
          },
        ],
      },
    ]

    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])
    await wrapper.setProps({ options: { colors: expectedColors } })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(1)
  })

  test('can remove a condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filter_groups: [
        {
          id: 100,
          filter_type: 'AND',
          parent_group: null,
        },
      ],
      filters: [
        {
          id: 101,
          field: 10,
          type: 'equal',
          value: '',
          preload_values: {},
          group: 100,
        },
      ],
    }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: { colors: [color] },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(1)

    wrapper
      .findComponent({ name: 'ViewFieldConditionItem' })
      .find('.filters__remove')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [
      {
        ...color,
        filters: [],
        filter_groups: [],
      },
    ]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])

    await wrapper.setProps({ options: { colors: expectedColors } })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(0)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(0)
  })

  test('can change the condition group filter_type from from AND to OR', async () => {
    const filters = [
      {
        id: 100,
        field: 10,
        type: 'equal',
        value: '',
        group: 98,
      },
      {
        id: 101,
        field: 10,
        type: 'equal',
        value: '',
        group: 98,
      },
      {
        id: 102,
        field: 10,
        type: 'equal',
        value: '',
        group: 99,
      },
    ]
    const filterGroups = [
      { filter_type: 'AND', id: 98, parent_group: null },
      { filter_type: 'AND', id: 99, parent_group: null },
    ]
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filters,
      filter_groups: filterGroups,
    }
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: {
          colors: [color],
        },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(3)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(2)

    expect(
      wrapper
        .findAllComponents({ name: 'ViewFilterFormOperator' })
        .at(2)
        .props().filterType
    ).toBe('AND')

    // First one is for the `WHERE` clause in root filter group, the second one is the
    // `WHERE` clause for the first filter group
    wrapper
      .findAllComponents({ name: 'ViewFilterFormOperator' })
      .at(2)
      .findAllComponents({ name: 'DropdownItem' })
      .at(1)
      .find('a')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')

    // The filter group with id 98 should have been updated to OR
    const expectedColors = [
      {
        ...color,
        filter_groups: [
          { filter_type: 'OR', id: 98, parent_group: null },
          filterGroups[1],
        ],
      },
    ]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])
    await wrapper.setProps({ options: { colors: expectedColors } })

    expect(
      wrapper
        .findAllComponents({ name: 'ViewFilterFormOperator' })
        .at(2)
        .props().filterType
    ).toBe('OR')
  })

  test.skip('can add a nested condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const filterGroups = [
      {
        id: 98,
        filter_type: 'AND',
        parent_group: null,
      },
    ]
    const filters = [
      {
        id: 99,
        field: 10,
        type: 'equal',
        value: '',
        preload_values: {},
        group: 98,
      },
    ]
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filter_groups: filterGroups,
      filters,
    }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: { colors: [color] },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(1)

    wrapper
      .find('.filters__group-item-action--add-filter-group')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [
      {
        ...color,
        filter_groups: [
          ...filterGroups,
          {
            id: 100,
            filter_type: 'AND',
            parent_group: 98,
          },
        ],
        filters: [
          ...filters,
          {
            id: 101,
            field: 10,
            type: 'equal',
            value: '',
            preload_values: {},
            group: 100,
          },
        ],
      },
    ]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])
    await wrapper.setProps({ options: { colors: expectedColors } })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(2)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(2)
  })

  test('can delete a nested condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const filterGroups = [
      {
        id: 98,
        filter_type: 'AND',
        parent_group: null,
      },
      {
        id: 100,
        filter_type: 'AND',
        parent_group: 98,
      },
    ]
    const filters = [
      {
        id: 99,
        field: 10,
        type: 'equal',
        value: '',
        preload_values: {},
        group: 98,
      },
      {
        id: 101,
        field: 10,
        type: 'equal',
        value: '',
        preload_values: {},
        group: 100,
      },
    ]
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filter_groups: filterGroups,
      filters,
    }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: {
          colors: [color],
        },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(2)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(2)

    wrapper
      .findAllComponents({ name: 'ViewFieldConditionItem' })
      .at(1)
      .find('.filters__remove')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')
    const expectedColors = [
      {
        ...color,
        filter_groups: [filterGroups[0]],
        filters: [filters[0]],
      },
    ]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])

    await wrapper.setProps({ options: { colors: expectedColors } })
    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(1)
  })

  test('removing the last condition delete the outermost condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const color = {
      id: 1,
      operator: 'AND',
      color: 'red',
      filter_groups: [
        {
          id: 100,
          filter_type: 'AND',
          parent_group: null,
        },
        {
          id: 101,
          filter_type: 'AND',
          parent_group: 100,
        },
      ],
      filters: [
        {
          id: 102,
          field: 10,
          type: 'equal',
          value: '',
          preload_values: {},
          group: 101,
        },
      ],
    }
    const wrapper = await testApp.mount(ConditionalColorValueProviderForm, {
      propsData: {
        ...basePropsData,
        view,
        options: {
          colors: [color],
        },
      },
    })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(1)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(2)

    wrapper
      .findComponent({ name: 'ViewFieldConditionItem' })
      .find('.filters__remove')
      .trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted()).toHaveProperty('update')

    // All filters have been removed, so the outermost filter group should be removed as
    // well.
    const expectedColors = [
      {
        ...color,
        filter_groups: [],
        filters: [],
      },
    ]
    expect(wrapper.emitted('update')[0]).toEqual([{ colors: expectedColors }])

    await wrapper.setProps({ options: { colors: expectedColors } })

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionItem' }).length
    ).toBe(0)

    expect(
      wrapper.findAllComponents({ name: 'ViewFieldConditionGroup' }).length
    ).toBe(0)
  })
})
