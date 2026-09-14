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
    }
  )
})
