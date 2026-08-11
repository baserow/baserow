import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import MoreStep from '@baserow/modules/core/components/onboarding/MoreStep'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: { label: { type: String, default: '' } },
  template: '<div class="form-group-stub" :data-label="label"><slot /></div>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: { modelValue: { type: String, default: '' } },
  template: '<div class="dropdown-stub"><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  template: '<div />',
})

const CheckboxStub = defineComponent({
  name: 'Checkbox',
  template: '<div />',
})

async function mountComponent(data) {
  return await mountSuspended(MoreStep, {
    props: { data },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
        Checkbox: CheckboxStub,
      },
      mocks: { $t: (key) => key },
    },
  })
}

const labels = (wrapper) =>
  wrapper.findAll('.form-group-stub').map((g) => g.attributes('data-label'))

describe('More onboarding step', () => {
  test('asks for the team when no earlier step collected one', async () => {
    const wrapper = await mountComponent({})
    await nextTick()

    expect(labels(wrapper)).toContain('teamStep.description')
    expect(wrapper.emitted('update-data').at(-1)[0].team).toBe('')
  })

  test('skips the team question and reuses the earlier answer', async () => {
    const wrapper = await mountComponent({
      database: { type: 'ai', team: 'Client services' },
    })
    await nextTick()

    expect(labels(wrapper)).not.toContain('teamStep.description')
    expect(wrapper.emitted('update-data').at(-1)[0].team).toBe(
      'Client services'
    )
  })

  test('follows the earlier answer when it changes', async () => {
    const wrapper = await mountComponent({
      database: { type: 'ai', team: 'Client services' },
    })
    await nextTick()

    await wrapper.setProps({
      data: {
        database: { type: 'ai', team: 'Client services' },
        ai_prompt: { team: 'Sales' },
      },
    })
    await nextTick()

    expect(wrapper.emitted('update-data').at(-1)[0].team).toBe('Sales')
  })

  test('does not treat its own answer as an earlier one', async () => {
    const wrapper = await mountComponent({ more: { team: 'Marketing' } })
    await nextTick()

    expect(labels(wrapper)).toContain('teamStep.description')
  })
})
