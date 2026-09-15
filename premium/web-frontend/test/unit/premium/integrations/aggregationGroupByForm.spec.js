import { mountSuspended } from '@nuxt/test-utils/runtime'
import AggregationGroupByForm from '@baserow_premium/integrations/localBaserow/components/services/AggregationGroupByForm.vue'

const stubs = {
  Dropdown: {
    props: ['value', 'error'],
    template:
      '<select :value="String(value)" :aria-invalid="error"><slot /></select>',
  },
  DropdownItem: {
    props: ['value', 'name', 'disabled'],
    template:
      '<option :value="String(value)" :disabled="disabled">{{ name }}</option>',
  },
}

describe('Row ID grouping availability', () => {
  let wrapper
  afterEach(() => wrapper?.unmount())

  test.each([
    'multiple_select',
    'multiple_collaborators',
    'link_row',
    'file',
    'text',
    'single_select',
  ])('validates Row Id grouping for a %s primary field', async (type) => {
    wrapper = await mountSuspended(AggregationGroupByForm, {
      props: {
        tableFields: [{ id: 1, type, name: 'Primary', primary: true }],
        aggregationGroupBys: [{ field_id: null }],
      },
      global: { stubs },
    })
    const disabled = !['text', 'single_select'].includes(type)
    expect(wrapper.get('option[value="null"]').element.disabled).toBe(disabled)
    expect(wrapper.get('select').attributes('aria-invalid')).toBe(
      String(disabled)
    )
    expect(wrapper.get('option[value="none"]').element.disabled).toBe(false)
  })

  test('a multi-valued non-primary field does not disable Row Id grouping', async () => {
    wrapper = await mountSuspended(AggregationGroupByForm, {
      props: {
        tableFields: [
          { id: 1, type: 'text', name: 'Primary', primary: true },
          { id: 2, type: 'multiple_select', name: 'Tags', primary: false },
        ],
        aggregationGroupBys: [],
      },
      global: { stubs },
    })
    expect(wrapper.get('option[value="null"]').element.disabled).toBe(false)
  })
})
