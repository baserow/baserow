import { mountSuspended } from '@nuxt/test-utils/runtime'
import { defineComponent } from 'vue'

import SimpleContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/SimpleContainerElementForm'
import {
  PAGE_ELEMENT_ALIGNMENTS,
  PAGE_ELEMENT_BEHAVIOURS,
} from '@baserow/modules/builder/enums'

describe('SimpleContainerElementForm', () => {
  const FormGroupStub = defineComponent({
    name: 'FormGroup',
    props: ['helperText', 'label'],
    template:
      '<div class="form-group-stub" :data-helper-text="helperText" :data-label="label"><slot /></div>',
  })

  const RadioGroupStub = defineComponent({
    name: 'RadioGroup',
    props: ['modelValue', 'options', 'type'],
    emits: ['update:modelValue'],
    template: '<div class="radio-group-stub" />',
  })

  const mountComponent = (defaultValues = {}) => {
    return mountSuspended(SimpleContainerElementForm, {
      props: {
        defaultValues: {
          behaviour: PAGE_ELEMENT_BEHAVIOURS.NORMAL,
          alignment: PAGE_ELEMENT_ALIGNMENTS.TOP,
          styles: {},
          parent_element_id: null,
          ...defaultValues,
        },
      },
      mocks: {
        $t: (key) => key,
        $registry: {
          getOrderedList: () => [],
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
          FormGroup: FormGroupStub,
          RadioGroup: RadioGroupStub,
        },
      },
    })
  }

  const getFormGroupLabels = (wrapper) => {
    return wrapper
      .findAll('.form-group-stub')
      .map((formGroup) => formGroup.attributes('data-label'))
  }

  test('shows positioning controls for root containers', async () => {
    const wrapper = await mountComponent({
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })

    expect(getFormGroupLabels(wrapper)).toEqual([
      'simpleContainerElementForm.behaviourLabel',
      'simpleContainerElementForm.alignmentLabel',
    ])
  })

  test('disables positioning controls for nested containers', async () => {
    const wrapper = await mountComponent({
      parent_element_id: 1,
      behaviour: PAGE_ELEMENT_BEHAVIOURS.FIXED,
    })

    expect(getFormGroupLabels(wrapper)).toEqual([
      'simpleContainerElementForm.behaviourLabel',
    ])
    expect(
      wrapper.find('.form-group-stub').attributes('data-helper-text')
    ).toBe('simpleContainerElementForm.rootContainerOnlyHelper')
    expect(
      wrapper.findComponent(RadioGroupStub).props('options')
    ).toMatchObject([
      { value: PAGE_ELEMENT_BEHAVIOURS.NORMAL, disabled: true },
      { value: PAGE_ELEMENT_BEHAVIOURS.STICKY, disabled: true },
      { value: PAGE_ELEMENT_BEHAVIOURS.FIXED, disabled: true },
    ])
  })
})
