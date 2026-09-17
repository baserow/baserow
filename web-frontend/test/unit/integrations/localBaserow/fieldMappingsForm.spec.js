import { TestApp } from '@baserow/test/helpers/testApp'
import FieldMappingsForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingsForm'

const FIELDS = [{ id: 1, name: 'Name', type: 'text' }]
const MAPPINGS = [
  { field_id: 1, enabled: true, value: { formula: "'a'" }, trashed: false },
  // On a trashed field, so the table's field list leaves it out.
  { field_id: 2, enabled: true, value: { formula: "'b'" }, trashed: true },
  // On a field that is gone for good.
  { field_id: 3, enabled: true, value: { formula: "'c'" }, trashed: false },
]

describe('FieldMappingsForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountForm = async () =>
    testApp.mount(FieldMappingsForm, {
      props: { modelValue: MAPPINGS, fields: FIELDS },
      global: {
        provide: { workspace: { id: 1 } },
        stubs: { FieldMappingForm: true },
      },
    })

  test('editing a mapping sends the ones on trashed fields back', async () => {
    const wrapper = await mountForm()

    wrapper
      .findComponent({ name: 'FieldMappingForm' })
      .vm.$emit('update', { value: { formula: "'changed'" } })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [[{ ...MAPPINGS[0], value: { formula: "'changed'" } }, MAPPINGS[1]]],
    ])
  })
})
