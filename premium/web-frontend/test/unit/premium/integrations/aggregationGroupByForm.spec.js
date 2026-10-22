import paletteColors from '@baserow/modules/core/assets/scss/colors.module.scss'
import MockAdapter from 'axios-mock-adapter'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import AggregationGroupByForm from '@baserow_premium/integrations/localBaserow/components/services/AggregationGroupByForm.vue'

const dropdownStubs = {
  Dropdown: {
    props: ['value'],
    emits: ['change'],
    template: `<select :value="String(value)" @change="$emit('change', parse($event.target.value))"><slot /></select>`,
    methods: {
      parse(value) {
        return value === 'null'
          ? null
          : /^\d+$/.test(value)
            ? Number(value)
            : value
      },
    },
  },
  DropdownItem: {
    props: ['value', 'name'],
    template: '<option :value="String(value)">{{ name }}</option>',
  },
}

describe('Multiple-select aggregation grouping', () => {
  let wrapper
  afterEach(() => wrapper?.unmount())

  test('uses Database field grouping compatibility', async () => {
    wrapper = await mountSuspended(AggregationGroupByForm, {
      props: {
        tableFields: [
          { id: 1, name: 'Date', type: 'date' },
          { id: 2, name: 'Duration', type: 'duration' },
          {
            id: 3,
            name: 'Rich text',
            type: 'long_text',
            long_text_enable_rich_text: true,
          },
        ],
        aggregationGroupBys: [],
      },
      global: { stubs: dropdownStubs },
    })

    const optionNames = wrapper.findAll('option').map((option) => option.text())
    expect(optionNames).toContain('Date')
    expect(optionNames).toContain('Duration')
    expect(optionNames).not.toContain('Rich text')
  })

  test('selects either mode, restores saved settings, and hides modes for Row Id', async () => {
    wrapper = await mountSuspended(AggregationGroupByForm, {
      props: {
        tableFields: [
          { id: 1, name: 'Tags', type: 'multiple_select', primary: true },
        ],
        aggregationGroupBys: [{ field_id: 1, mode: 'complete' }],
      },
      global: { stubs: dropdownStubs },
    })
    expect(wrapper.html()).toMatchSnapshot()
    expect(wrapper.findAll('select')[1].element.value).toBe('complete')
    await wrapper.findAll('select')[1].setValue('individual')
    expect(wrapper.emitted('mode-changed')).toEqual([['individual']])
    await wrapper.setProps({
      aggregationGroupBys: [{ field_id: 1, mode: 'individual' }],
    })
    expect(wrapper.findAll('select')[1].element.value).toBe('individual')
    await wrapper.findAll('select')[0].setValue('null')
    expect(wrapper.emitted('value-changed')).toEqual([[null]])
    expect(wrapper.findAll('select')).toHaveLength(1)
    await wrapper.setProps({ aggregationGroupBys: [{ field_id: 1 }] })
    expect(wrapper.findAll('select')[1].element.value).toBe('complete')
  })
})

const mountBucketLimitForm = (bucketLimit = null) =>
  mountSuspended(AggregationGroupByForm, {
    props: {
      tableFields: [{ id: 1, name: 'Tags', type: 'multiple_select' }],
      aggregationGroupBys: [{ field_id: 1 }],
      bucketLimit,
    },
    global: { stubs: dropdownStubs },
  })

describe('Bucket limit validation', () => {
  test.each([null, 1, 10, 0, 11, 1.5])(
    'validates limit %s',
    async (bucketLimit) => {
      const wrapper = await mountBucketLimitForm(bucketLimit)
      expect(wrapper.vm.v$.bucketLimitInput.$invalid).toBe(
        bucketLimit !== null &&
          (!Number.isInteger(bucketLimit) ||
            bucketLimit < 1 ||
            bucketLimit > 10)
      )
      const input = wrapper.get('input[type="number"]')
      await input.setValue('3')
      await input.trigger('blur')
      expect(wrapper.emitted('bucket-limit-changed')).toEqual([[3]])
      wrapper.unmount()
    }
  )
})

describe('Bucket limit saving', () => {
  let wrapper
  afterEach(() => {
    vi.useRealTimers()
    wrapper?.unmount()
  })

  test('emits once the user pauses instead of on every keystroke', async () => {
    wrapper = await mountBucketLimitForm()
    const input = wrapper.get('input[type="number"]')
    vi.useFakeTimers()
    await input.setValue('1')
    await vi.advanceTimersByTimeAsync(250)
    await input.setValue('10')
    await vi.advanceTimersByTimeAsync(499)
    expect(wrapper.emitted('bucket-limit-changed')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.emitted('bucket-limit-changed')).toEqual([[10]])
  })

  test('emits immediately when the input loses focus', async () => {
    wrapper = await mountBucketLimitForm()
    const input = wrapper.get('input[type="number"]')
    await input.setValue('5')
    expect(wrapper.emitted('bucket-limit-changed')).toBeUndefined()
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toEqual([[5]])
    // Leaving the input again without a change does not save again.
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toEqual([[5]])
  })

  test('never emits a value the backend would reject', async () => {
    wrapper = await mountBucketLimitForm(3)
    const input = wrapper.get('input[type="number"]')
    await input.setValue('11')
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toBeUndefined()
    expect(wrapper.vm.v$.bucketLimitInput.$error).toBe(true)
    expect(input.element.value).toBe('11')
    // A number input never reports a non-numeric string in a browser; guard the
    // parsing anyway so `NaN` cannot be saved as `null`.
    wrapper.vm.bucketLimitChangedByUser('e')
    await wrapper.vm.$nextTick()
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toBeUndefined()
    expect(wrapper.vm.v$.bucketLimitInput.$invalid).toBe(true)
    // Clearing the input is valid and removes the limit.
    await input.setValue('')
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toEqual([[null]])
  })

  test('a save response does not overwrite a value still being typed', async () => {
    wrapper = await mountBucketLimitForm()
    const input = wrapper.get('input[type="number"]')
    await input.setValue('10')
    // The dashboard saves asynchronously; an earlier save resolving now must
    // not reset the input.
    await wrapper.setProps({ bucketLimit: 1 })
    expect(input.element.value).toBe('10')
    await input.trigger('blur')
    expect(wrapper.emitted('bucket-limit-changed')).toEqual([[10]])
    // Once the typed value is emitted the saved value is followed again.
    await wrapper.setProps({ bucketLimit: 10 })
    expect(input.element.value).toBe('10')
    await wrapper.setProps({ bucketLimit: 4 })
    expect(input.element.value).toBe('4')
  })
})

describe('Grouping mode persistence in data-source forms', () => {
  let wrapper
  let mock
  afterEach(() => {
    wrapper?.unmount()
    mock?.restore()
    useNuxtApp().$store.commit('dashboardApplication/RESET')
  })

  test.each(['builder', 'dashboard'])(
    '%s includes the selected mode when saving',
    async (surface) => {
      const app = useNuxtApp()
      mock = new MockAdapter(app.$client, { onNoMatch: 'throwException' })
      mock
        .onGet('database/fields/table/1/')
        .reply(200, [{ id: 1, name: 'Tags', type: 'multiple_select' }])
      const { default: Form } =
        surface === 'builder'
          ? await import('@baserow_premium/integrations/localBaserow/components/services/LocalBaserowGroupedAggregateRowsForm.vue')
          : await import('@baserow_premium/dashboard/components/data_source/GroupedAggregateRowsDataSourceForm.vue')
      app.$store.commit('dashboardApplication/RESET')
      app.$store.commit('dashboardApplication/ADD_INTEGRATION', {
        id: 1,
        context_data: {
          databases: [
            {
              id: 1,
              name: 'Database',
              tables: [{ id: 1, name: 'Table' }],
              views: [],
            },
          ],
        },
      })
      const source = {
        id: 1,
        integration_id: 1,
        table_id: 1,
        type: 'local_baserow_grouped_aggregate_rows',
        aggregation_group_bys: [{ field_id: 1, mode: 'complete' }],
        aggregation_series: [],
        aggregation_sorts: [],
        filters: [],
      }
      wrapper = await mountSuspended(
        {
          components: { Form },
          props: ['source', 'serviceType'],
          emits: ['save', 'change'],
          template: `<div>
        <Form ref="form" :application="{ id: 1 }" :dashboard="{ id: 1 }" :widget="{}"
          :data-source="source" :service-type="serviceType" :default-values="source"
          @values-changed="$emit('change', $event)" />
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
              ...dropdownStubs,
              LocalBaserowServiceForm: true,
              ApplicationSelector: true,
              ServiceRefinementForms: {
                template: '<div><slot name="group-form" /></div>',
              },
            },
          },
        }
      )
      await flushPromises()
      const groupForm = wrapper.findComponent(AggregationGroupByForm)
      await groupForm.findAll('select')[1].setValue('individual')
      if (surface === 'builder') {
        await wrapper.get('[data-test=save]').trigger('click')
        expect(wrapper.emitted('save').at(-1)[0].aggregation_group_bys).toEqual(
          [{ field_id: 1, mode: 'individual' }]
        )
      } else {
        expect(
          wrapper.emitted('change').at(-1)[0].aggregation_group_bys
        ).toEqual([{ field_id: 1, mode: 'individual' }])
      }
      const bucketLimitInput = groupForm.get('input[type="number"]')
      await bucketLimitInput.setValue('3')
      await bucketLimitInput.trigger('blur')
      if (surface === 'builder') {
        await wrapper.get('[data-test=save]').trigger('click')
        expect(wrapper.emitted('save').at(-1)[0].bucket_limit).toBe(3)
      } else {
        expect(wrapper.emitted('change').at(-1)[0].bucket_limit).toBe(3)
      }
    }
  )
})

describe('Dashboard series colors', () => {
  test('keeps the chart type when changing color and keeps color when changing type', async () => {
    const { default: Form } =
      await import('@baserow_premium/integrations/localBaserow/components/services/AggregationSeriesForm.vue')
    const config = {
      series_id: 1,
      series_chart_type: 'LINE',
      series_color: '#112233',
    }
    const wrapper = await mountSuspended(Form, {
      props: {
        tableFields: [{ id: 10, type: 'number', name: 'Amount' }],
        aggregationSeries: [{ id: 1, field_id: 10, aggregation_type: 'sum' }],
        seriesIndex: 0,
        defaultValues: { id: 1, field_id: 10, aggregation_type: 'sum' },
        widget: {
          type: 'chart',
          default_series_chart_type: 'BAR',
          series_config: [config],
        },
      },
    })
    wrapper
      .findComponent({ name: 'ColorSelectContext' })
      .vm.$emit('selected', 'blue')
    expect(wrapper.emitted('series-config-changed').at(-1)[0]).toEqual({
      ...config,
      series_color: paletteColors.blue,
    })
    wrapper.vm.seriesChartTypeChanged('BAR')
    expect(wrapper.emitted('series-config-changed').at(-1)[0]).toEqual({
      ...config,
      series_chart_type: 'BAR',
    })
    wrapper.unmount()
  })
})
