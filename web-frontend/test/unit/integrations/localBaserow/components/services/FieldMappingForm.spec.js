import { mountSuspended } from '@nuxt/test-utils/runtime'
import FieldMappingForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

describe('FieldMappingForm', () => {
  const mountComponent = ({ props = {} }) => {
    return mountSuspended(FieldMappingForm, {
      props: {
        field: { id: 1, name: 'Name', type: 'text' },
        ...props,
      },
      global: {
        provide: {
          workspace: { id: 1 },
          formulaComponent: { template: '<div />' },
          dataProvidersAllowed: [],
        },
        stubs: {
          // InViewport lazily renders its default slot via an intersection
          // observer, which never fires in jsdom - stub it so the formula input
          // (and its v-model) actually mounts.
          InViewport: { template: '<div><slot /></div>' },
        },
      },
    })
  }

  test('enabling a field emits the canonical empty formula, not the string literal', async () => {
    // The empty-string literal ('""') can't be represented by the formula editor:
    // it renders empty and emits '' on its first update, which registers a spurious
    // field-value change. During undo/redo that extra action discards the redo stack
    // ("No more actions to redo"). Enabling must use the canonical empty formula.
    const wrapper = await mountComponent({ props: { mapping: undefined } })

    await wrapper.find('button').trigger('click')

    const emitted = wrapper.emitted('update')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toStrictEqual({
      enabled: true,
      value: { formula: '' },
    })
  })

  test('commits a pending debounced edit when another field re-renders the list', async () => {
    // Repro at normal human pace: type a value in one field, then click to enable
    // the next field within the 500ms debounce. The parent re-emits the whole
    // mappings array, re-rendering this field with its last *committed* value.
    // Without committing the in-flight edit first, the typed value is silently
    // dropped - it's never emitted, so no set-value action is recorded and it
    // can't be undone/redone.
    const wrapper = await mountComponent({
      props: {
        mapping: { field_id: 1, enabled: true, value: { formula: '' } },
      },
    })

    // The InjectedFormulaInput drives `fieldValue` via v-model; emitting its
    // update stands in for the user typing.
    wrapper
      .findComponent(InjectedFormulaInput)
      .vm.$emit('update:modelValue', { formula: "'typed'" })
    await wrapper.vm.$nextTick()

    // Another field is enabled -> the parent re-emits the array, so this field's
    // `mapping` prop is replaced while its committed value is still empty.
    await wrapper.setProps({
      mapping: { field_id: 1, enabled: true, value: { formula: '' } },
    })

    // The pending edit must have been committed, not dropped.
    const emitted = wrapper.emitted('update') || []
    expect(emitted).toContainEqual([{ value: { formula: "'typed'" } }])
  })
})
