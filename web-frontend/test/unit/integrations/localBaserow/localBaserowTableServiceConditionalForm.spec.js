import { defineComponent } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'

import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm.vue'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput.vue'

const ViewFieldConditionsFormStub = defineComponent({
  name: 'ViewFieldConditionsForm',
  props: {
    filters: { type: Array, required: true },
  },
  setup() {
    return {
      filterType: {
        hasEditableValue: true,
        isDeprecated: () => false,
        getInputComponent: () => 'input',
      },
    }
  },
  template: `
    <div>
      <slot
        name="filterInputComponent"
        :slot-props="{
          filter: filters[0],
          field: { id: filters[0].field },
          filterType,
        }"
      />
    </div>
  `,
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { type: Object, required: true },
  },
  emits: ['input'],
  template: `
    <button
      class="formula-input-stub"
      :data-mode="modelValue.mode"
      @click="$emit('input', { formula: &quot;'Alice'&quot;, mode: 'simple' })"
    />
  `,
})

const FormulaInputStub = defineComponent({
  name: 'FormulaInputStub',
  template: '<button class="formula-input-field__mode-toggle" />',
})

describe('LocalBaserowTableServiceConditionalForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const fields = [{ id: 1, name: 'Name', type: 'text', primary: true }]

  test.each(['empty', 'not_empty'])(
    'preserves the %s controller when changing its target field',
    async (operator) => {
      const wrapper = await mountComponent(
        {
          fields: [...fields, { id: 2, name: 'Country', type: 'text' }],
          modelValue: [
            {
              id: 'filter-1',
              field: 1,
              type: 'equal',
              value: { formula: "get('dashboard_filter.1')", mode: 'simple' },
            },
          ],
        },
        {
          provide: {
            resolveServiceFilterOperator: () => ({
              type: operator,
              help: 'Set in Country',
            }),
            formulaComponent: FormulaInputStub,
          },
        }
      )
      expect(wrapper.get('.filters__type .dropdown__selected').text()).toBe(
        operator === 'empty' ? 'viewFilter.isEmpty' : 'viewFilter.isNotEmpty'
      )
      expect(wrapper.get('.filters__type .dropdown').classes()).toContain(
        'dropdown--disabled'
      )
      expect(wrapper.find('.formula-input-field__mode-toggle').exists()).toBe(
        true
      )
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
      await wrapper.get('.filters__type').trigger('focus')
      expect(document.body.querySelector('.tooltip').textContent).toBe(
        'Set in Country'
      )
      await wrapper.get('.filters__type').trigger('blur')
      await wrapper.get('.filters__field .dropdown__selected').trigger('click')
      await wrapper
        .get('.filters__field .select__item-name-text[title="Country"]')
        .trigger('click')
      expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([
        {
          id: 'filter-1',
          field: 2,
          type: 'equal',
          value: { formula: "get('dashboard_filter.1')", mode: 'simple' },
        },
      ])
    }
  )

  test('keeps ordinary source operators editable without a controller', async () => {
    const wrapper = await mountComponent({
      modelValue: [
        {
          id: 'filter-1',
          field: 1,
          type: 'equal',
          value: { formula: 'France', mode: 'raw' },
        },
      ],
    })
    expect(wrapper.get('.filters__type .dropdown__selected').text()).toBe(
      'viewFilter.is'
    )
    expect(wrapper.get('.filters__type .dropdown').classes()).not.toContain(
      'dropdown--disabled'
    )
  })

  async function mountComponent(props = {}, global = {}) {
    return await testApp.mount(LocalBaserowTableServiceConditionalForm, {
      props: {
        modelValue: [],
        filterGroups: [],
        filterType: 'AND',
        fields,
        ...props,
      },
      global,
    })
  }

  test('keeps Builder date conditions on the existing input contract', async () => {
    const page = { id: 1, elements: [], dataSources: [], _: {} }
    const builder = { id: 1, pages: [page] }
    const filter = {
      id: 'filter-1',
      field: 1,
      type: 'date_is',
      value: { formula: 'Asia/Dubai?2026-10-01?exact_date', mode: 'raw' },
    }
    const wrapper = await mountComponent(
      {
        fields: [{ id: 1, name: 'Date', type: 'date', date_format: 'ISO' }],
        modelValue: [filter],
      },
      {
        provide: {
          applicationContext: { builder, page, mode: 'editing' },
          elementPage: page,
          formulaComponent: ApplicationBuilderFormulaInput,
          dataProvidersAllowed: [],
        },
      }
    )
    const input = wrapper.get('.filters__value-input input')
    await input.setValue('2026-10-26')
    const updated = [
      {
        ...filter,
        value: { formula: 'Asia/Dubai?2026-10-26?exact_date', mode: 'raw' },
      },
    ]
    expect(wrapper.emitted('update:modelValue')).toEqual([[updated]])
    await wrapper.setProps({ modelValue: updated })
    await input.setValue('invalid')
    await input.setValue('')
    expect(wrapper.emitted('update:modelValue')).toEqual([[updated]])
    await input.setValue('invalid')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([
      {
        ...filter,
        value: { formula: 'Asia/Dubai?invalid?exact_date', mode: 'raw' },
      },
    ])
  })

  test('adding a filter group emits a new group and a seeded filter', async () => {
    const wrapper = await mountComponent()
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('addFilterGroup', {
      filterGroupId: 'group-1',
      parentGroupId: null,
    })
    await wrapper.vm.$nextTick()

    const groups = wrapper.emitted('update:filterGroups').at(-1)[0]
    expect(groups).toEqual([
      { id: 'group-1', filter_type: 'AND', parent_group: null },
    ])

    // A first filter is seeded inside the new group.
    const filters = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(filters).toHaveLength(1)
    expect(filters[0].group).toBe('group-1')
    expect(filters[0].field).toBe(fields[0].id)
  })

  test('adding a nested filter group carries the parent group id', async () => {
    const wrapper = await mountComponent({
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('addFilterGroup', {
      filterGroupId: 'group-2',
      parentGroupId: 'group-1',
    })
    await wrapper.vm.$nextTick()

    const groups = wrapper.emitted('update:filterGroups').at(-1)[0]
    expect(groups).toEqual([
      { id: 'group-1', filter_type: 'AND', parent_group: null },
      { id: 'group-2', filter_type: 'AND', parent_group: 'group-1' },
    ])
  })

  test('deleting a filter group removes it and its filters', async () => {
    const wrapper = await mountComponent({
      modelValue: [
        {
          id: 'f1',
          field: 1,
          type: 'equal',
          value: { formula: 'a', mode: 'raw' },
          group: 'group-1',
        },
        {
          id: 'f2',
          field: 1,
          type: 'equal',
          value: { formula: 'b', mode: 'raw' },
          group: null,
        },
      ],
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('deleteFilterGroup', {
      group: { id: 'group-1' },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterGroups').at(-1)[0]).toEqual([])
    // Only the ungrouped filter survives.
    const filters = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(filters.map((f) => f.id)).toEqual(['f2'])
  })

  test('updating a group filter type emits the updated groups', async () => {
    const wrapper = await mountComponent({
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('updateFilterType', {
      value: 'OR',
      filterGroup: { id: 'group-1' },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterGroups').at(-1)[0]).toEqual([
      { id: 'group-1', filter_type: 'OR', parent_group: null },
    ])
    // The top-level filter type is not touched.
    expect(wrapper.emitted('update:filterType')).toBeFalsy()
  })

  test('updating the top-level filter type emits update:filterType', async () => {
    const wrapper = await mountComponent()
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('updateFilterType', { value: 'OR' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterType').at(-1)[0]).toBe('OR')
    expect(wrapper.emitted('update:filterGroups')).toBeFalsy()
  })

  test('the formula toggle is rendered for a filter inside a group', async () => {
    // The raw-value/formula toggle (sigma) slot must reach filters nested in a
    // group, not just root-level filters.
    const wrapper = await mountComponent(
      {
        modelValue: [
          {
            id: 'f1',
            field: 1,
            type: 'equal',
            value: { formula: 'a', mode: 'raw' },
            group: 'group-1',
          },
        ],
        filterGroups: [
          { id: 'group-1', filter_type: 'AND', parent_group: null },
        ],
      },
      {
        provide: {
          formulaComponent: FormulaInputStub,
          dataProvidersAllowed: [],
        },
      }
    )

    expect(
      wrapper
        .find('.filters__group-item .formula-input-field__mode-toggle')
        .exists()
    ).toBe(true)
  })

  test.each([
    ['raw', undefined, 'raw'],
    ['simple', undefined, 'simple'],
    ['advanced', undefined, 'advanced'],
    ['advanced', true, 'advanced'],
    ['simple', false, 'raw'],
  ])(
    'renders mode %s with legacy flag %s as %s',
    async (mode, valueIsFormula, expectedMode) => {
      const wrapper = await mountComponent(
        {
          modelValue: [
            {
              id: 'filter-1',
              field: 1,
              type: 'equal',
              value: { formula: 'Alice', mode },
              ...(valueIsFormula === undefined
                ? {}
                : { value_is_formula: valueIsFormula }),
              group: null,
            },
          ],
        },
        {
          stubs: {
            ViewFieldConditionsForm: ViewFieldConditionsFormStub,
            InjectedFormulaInput: InjectedFormulaInputStub,
          },
        }
      )

      expect(wrapper.find('.formula-input-stub').attributes('data-mode')).toBe(
        expectedMode
      )
    }
  )

  test('emits filters using formula mode instead of value_is_formula', async () => {
    const wrapper = await mountComponent(
      {
        modelValue: [
          {
            id: 'filter-1',
            field: 1,
            type: 'equal',
            value: { formula: 'Alice', mode: 'raw' },
            value_is_formula: false,
            group: null,
          },
        ],
      },
      {
        stubs: {
          ViewFieldConditionsForm: ViewFieldConditionsFormStub,
          InjectedFormulaInput: InjectedFormulaInputStub,
        },
      }
    )

    await wrapper.find('.formula-input-stub').trigger('click')

    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([
      {
        id: 'filter-1',
        field: 1,
        type: 'equal',
        value: { formula: "'Alice'", mode: 'simple' },
        group: null,
      },
    ])
  })
})
