import { mountSuspended } from '@nuxt/test-utils/runtime'
import { defineComponent } from 'vue'

import MultiPageContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/MultiPageContainerElementForm'
import { PAGE_ELEMENT_BEHAVIOURS } from '@baserow/modules/builder/enums'

describe('MultiPageContainerElementForm', () => {
  const FormGroupStub = defineComponent({
    name: 'FormGroup',
    props: ['label'],
    template: '<div class="form-group-stub" :data-label="label"><slot /></div>',
  })

  const RadioGroupStub = defineComponent({
    name: 'RadioGroup',
    props: ['modelValue', 'options', 'type'],
    emits: ['update:modelValue'],
    template: '<div class="radio-group-stub" />',
  })

  const DropdownStub = defineComponent({
    name: 'Dropdown',
    props: ['modelValue', 'showSearch', 'small'],
    emits: ['update:modelValue'],
    template: '<div><slot /></div>',
  })

  const DropdownItemStub = defineComponent({
    name: 'DropdownItem',
    props: ['name', 'value'],
    template: '<div><slot /></div>',
  })

  const mountComponent = () => {
    return mountSuspended(MultiPageContainerElementForm, {
      props: {
        defaultValues: {
          behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
          share_type: 'all',
          pages: [],
          styles: {},
        },
      },
      mocks: {
        $t: (key) => key,
        $registry: {
          getOrderedList: () => [],
        },
        $store: {
          getters: {
            'page/getVisiblePages': () => [],
          },
        },
      },
      global: {
        provide: {
          workspace: {},
          builder: {
            theme: {},
          },
          currentPage: {},
          elementPage: {},
          mode: 'edit',
        },
        stubs: {
          Dropdown: DropdownStub,
          DropdownItem: DropdownItemStub,
          FormGroup: FormGroupStub,
          RadioGroup: RadioGroupStub,
        },
      },
    })
  }

  test('shows fixed behaviour controls without alignment controls', async () => {
    const wrapper = await mountComponent()

    const formGroupLabels = wrapper
      .findAll('.form-group-stub')
      .map((formGroup) => formGroup.attributes('data-label'))
    const behaviourOptions = wrapper
      .findComponent(RadioGroupStub)
      .props('options')

    expect(formGroupLabels).toEqual([
      'multiPageContainerElementForm.behaviour',
      'multiPageContainerElementForm.display',
    ])
    expect(behaviourOptions.map(({ value }) => value)).toEqual([
      PAGE_ELEMENT_BEHAVIOURS.NORMAL,
      PAGE_ELEMENT_BEHAVIOURS.FIXED,
    ])
  })
})
