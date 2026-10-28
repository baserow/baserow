import { defineComponent } from 'vue'
import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import FieldForm from '@baserow/modules/database/components/field/FieldForm'
import { FieldFormAdvancedSettingType } from '@baserow/modules/database/fieldFormAdvancedSettingTypes'
import form from '@baserow/modules/core/mixins/form'

const LabelSetting = defineComponent({
  mixins: [form],
  props: {
    fieldValues: { type: Object, required: true },
    database: { type: Object, required: true },
    table: { type: Object, required: true },
  },
  data() {
    return { allowedValues: ['label'], values: { label: '' } }
  },
  template: `<div class="label-setting">{{ fieldValues.type }}</div>
    <div class="label-setting__decimal-places">
      {{ fieldValues.number_decimal_places }}
    </div>`,
})

class LabelSettingType extends FieldFormAdvancedSettingType {
  static getType() {
    return 'label'
  }

  get component() {
    return LabelSetting
  }
}

describe('FieldForm advanced settings', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp
      .getRegistry()
      .register('fieldFormAdvancedSetting', new LabelSettingType({}))
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('fieldFormAdvancedSetting', 'label')
    await testApp.afterEach()
  })

  test('renders the registered settings and submits their values', async () => {
    const wrapper = await testApp.mount(FieldForm, {
      props: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [],
        database: { id: 1, workspace: { id: 1 } },
        defaultValues: { id: 1, name: 'Notes', type: 'text', label: 'saved' },
      },
      global: { stubs: { Dropdown: true, FieldConstraintsSubForm: true } },
    })
    await flushPromises()

    expect(wrapper.find('.label-setting').text()).toBe('text')

    wrapper.vm.submit()
    expect(wrapper.emitted('submitted')[0][0]).toMatchObject({
      name: 'Notes',
      label: 'saved',
    })
  })

  test('receives the unsaved values of the field type form', async () => {
    const wrapper = await testApp.mount(FieldForm, {
      props: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [],
        database: { id: 1, workspace: { id: 1 } },
        defaultValues: {
          id: 1,
          name: 'Amount',
          type: 'number',
          number_decimal_places: 0,
        },
      },
      global: { stubs: { Dropdown: true, FieldConstraintsSubForm: true } },
    })
    await flushPromises()

    wrapper.vm.$refs.childForm.values.number_decimal_places = 2
    await flushPromises()

    expect(wrapper.find('.label-setting__decimal-places').text()).toBe('2')
  })
})
