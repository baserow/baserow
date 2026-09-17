import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import MockAdapter from 'axios-mock-adapter'

describe('Grouped aggregate data source form', () => {
  let mock
  let wrapper

  beforeEach(() => {
    mock = new MockAdapter(useNuxtApp().$client, {
      onNoMatch: 'throwException',
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    mock.restore()
  })

  test.each([
    ['delete', ['field_2_sum', 'field_3']],
    ['field', ['field_2_sum', 'field_3']],
    ['aggregation', ['field_2_sum', 'field_3']],
    ['group', ['field_1_sum', 'field_2_sum']],
    ['ungroup', ['field_1_sum', 'field_2_sum']],
    ['row-id', ['field_1_sum', 'field_2_sum', 'field_3']],
    ['unchanged', ['field_1_sum', 'field_2_sum', 'field_3']],
  ])('%s changes emit only valid sorts', async (action, expectedReferences) => {
    const app = useNuxtApp()
    const { default: GroupedForm } =
      await import('@baserow_premium/integrations/localBaserow/components/services/LocalBaserowGroupedAggregateRowsForm.vue')
    mock.onGet('database/fields/table/1/').reply(200, [
      { id: 1, name: 'Amount', type: 'number' },
      { id: 2, name: 'Other amount', type: 'number' },
      { id: 3, name: 'Category', type: 'number', primary: true },
    ])
    wrapper = await mountSuspended(GroupedForm, {
      props: {
        application: { id: 1 },
        serviceType: app.$registry.get(
          'service',
          'local_baserow_grouped_aggregate_rows'
        ),
        defaultValues: {
          table_id: 1,
          aggregation_series: [
            { id: 10, field_id: 1, aggregation_type: 'sum' },
            { id: 11, field_id: 2, aggregation_type: 'sum' },
          ],
          aggregation_group_bys: [{ field_id: 3 }],
          aggregation_sorts: [
            { sort_on: 'SERIES', reference: 'field_1_sum', direction: 'ASC' },
            { sort_on: 'SERIES', reference: 'field_2_sum', direction: 'DESC' },
            { sort_on: 'GROUP_BY', reference: 'field_3', direction: 'ASC' },
          ],
        },
      },
      global: {
        stubs: {
          LocalBaserowServiceForm: true,
          ServiceRefinementForms: {
            template:
              '<div><slot name="group-form" /><slot name="sort-form" /></div>',
          },
          AggregationSortByForm: true,
          AggregationSeriesForm: {
            props: ['seriesIndex', 'defaultValues'],
            emits: ['delete-series', 'values-changed'],
            methods: { reset() {} },
            template: `<div>
              <button type="button" :data-test="'delete-' + seriesIndex" @click="$emit('delete-series', seriesIndex)">Delete</button>
              <button type="button" :data-test="'field-' + seriesIndex" @click="$emit('values-changed', {...defaultValues, field_id: 3})">Change field</button>
              <button type="button" :data-test="'aggregation-' + seriesIndex" @click="$emit('values-changed', {...defaultValues, aggregation_type: 'average'})">Change aggregation</button>
              <button type="button" :data-test="'unchanged-' + seriesIndex" @click="$emit('values-changed', {...defaultValues})">Keep series</button>
            </div>`,
          },
          AggregationGroupByForm: {
            emits: ['value-changed'],
            template: `<div>
              <button type="button" data-test="group" @click="$emit('value-changed', 2)">Change grouping</button>
              <button type="button" data-test="ungroup" @click="$emit('value-changed', 'none')">Remove grouping</button>
              <button type="button" data-test="row-id" @click="$emit('value-changed', null)">Group by row ID</button>
            </div>`,
          },
        },
      },
    })
    await flushPromises()
    const before = wrapper.emitted('values-changed')?.length || 0
    const control = ['group', 'ungroup', 'row-id'].includes(action)
      ? action
      : `${action}-0`
    await wrapper.get(`[data-test="${control}"]`).trigger('click')
    await flushPromises()
    const updates = wrapper.emitted('values-changed').slice(before)
    expect(updates.length).toBeGreaterThan(0)
    for (const [values] of updates) {
      expect(
        values.aggregation_sorts.map(({ reference }) => reference)
      ).toEqual(expectedReferences)
    }
    expect(updates.at(-1)[0]).toMatchSnapshot()
  })

  test('adding and editing series preserves all three data sources during save', async () => {
    const app = useNuxtApp()
    const { default: GroupedForm } =
      await import('@baserow_premium/integrations/localBaserow/components/services/LocalBaserowGroupedAggregateRowsForm.vue')
    const source = {
      id: 20,
      name: 'Grouped rows',
      type: 'local_baserow_grouped_aggregate_rows',
      table_id: 1,
      view_id: null,
      integration_id: null,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      aggregation_group_bys: [],
      aggregation_sorts: [],
      // Deliberately collide with the third data source's ID.
      aggregation_series: [{ id: 30, field_id: 1, aggregation_type: 'sum' }],
    }
    const first = { id: 10, name: 'First', type: 'local_baserow_list_rows' }
    const third = { id: 30, name: 'Third', type: 'local_baserow_list_rows' }
    const page = { id: 1, dataSources: [first, source, third], _: {} }
    mock.onGet('database/fields/table/1/').reply(200, [
      { id: 1, name: 'Amount', type: 'number', number_decimal_places: 0 },
      { id: 2, name: 'Other amount', type: 'number', number_decimal_places: 0 },
    ])
    // The wrapper saves via the same getFormValues contract as DataSourceForm.
    wrapper = await mountSuspended(
      {
        components: { GroupedForm },
        props: ['source', 'serviceType'],
        emits: ['save'],
        template: `<div>
          <GroupedForm ref="form" :application="{ id: 1 }"
            :service-type="serviceType" :default-values="source" />
          <button data-test="save" @click="$emit('save', $refs.form.getFormValues())">Save</button>
        </div>`,
      },
      {
        props: {
          source,
          serviceType: app.$registry.get('service', source.type),
        },
        global: {
          stubs: {
            LocalBaserowServiceForm: true,
            ServiceRefinementForms: true,
            Dropdown: {
              props: ['value', 'modelValue'],
              emits: ['input', 'update:modelValue', 'change'],
              template: `<select :value="modelValue ?? value" @change="change($event)"><slot /></select>`,
              methods: {
                change(event) {
                  const raw = event.target.value
                  const value = /^\d+$/.test(raw) ? Number(raw) : raw
                  this.$emit('input', value)
                  this.$emit('update:modelValue', value)
                  this.$emit('change', value)
                },
              },
            },
            DropdownItem: {
              props: ['value', 'name'],
              template: '<option :value="value">{{ name }}</option>',
            },
          },
        },
      }
    )
    await flushPromises()

    // Edit the persisted series, then add and configure another one.
    await wrapper.get('.aggregation-series-form select').setValue('average')
    const addButton = wrapper
      .findAll('a, button')
      .find((button) =>
        button.text().includes('localBaserowGroupedAggregateRowsForm.addSeries')
      )
    await addButton.trigger('click')
    const seriesForms = wrapper.findAll('.aggregation-series-form')
    expect(seriesForms).toHaveLength(2)
    await seriesForms[1].findAll('select')[0].setValue('sum')
    await seriesForms[1].findAll('select')[1].setValue('2')
    await wrapper.get('[data-test="save"]').trigger('click')
    const payload = wrapper.emitted('save').at(-1)[0]
    expect(payload).toMatchSnapshot()

    let respond
    mock.onPatch('builder/data-source/20/').reply(
      () =>
        new Promise((resolve) => {
          respond = resolve
        })
    )
    const saving = app.$store.dispatch('dataSource/debouncedUpdate', {
      page,
      dataSourceId: source.id,
      values: payload,
    })
    await flushPromises()
    expect(page.dataSources.map(({ id }) => id)).toEqual([10, 20, 30])
    expect(page.dataSources[0]).toEqual(first)
    expect(page.dataSources[2]).toEqual(third)
    expect(page.dataSources[1].aggregation_series).toEqual([
      { id: 30, field_id: 1, aggregation_type: 'average' },
      { field_id: 2, aggregation_type: 'sum' },
    ])
    await vi.waitFor(() => expect(respond).toBeDefined())
    expect(JSON.parse(mock.history.patch[0].data)).toEqual(payload)
    const savedSource = {
      ...source,
      ...payload,
      aggregation_series: [
        payload.aggregation_series[0],
        { ...payload.aggregation_series[1], id: 31 },
      ],
    }
    respond([200, savedSource])
    await saving
    expect(page.dataSources).toEqual([first, savedSource, third])
  })
})
