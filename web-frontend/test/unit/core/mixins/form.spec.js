import form, {
  syncFormsWithDefaultValuesKey,
} from '@baserow/modules/core/mixins/form'
import { TestApp } from '@baserow/test/helpers/testApp'

// Minimal form component built on the shared form mixin. Renders an input bound to
// `values.name` (to simulate typing) and a span (to assert the effective value).
const TestForm = {
  name: 'TestForm',
  mixins: [form],
  template: `<div>
    <input class="inp" v-model="values.name" />
    <span class="disp">{{ values.name }}</span>
  </div>`,
  data() {
    return { values: { name: '' } }
  },
}

describe('form mixin defaultValues syncing', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = (props) => testApp.mount(TestForm, { props })

  test('off by default: an external defaultValues change does not touch values', async () => {
    const wrapper = await mountForm({ defaultValues: { name: 'bob' } })
    expect(wrapper.find('.disp').text()).toBe('bob')

    await wrapper.setProps({ defaultValues: { name: 'alice' } })

    // Existing behaviour is preserved: the form was only initialised once.
    expect(wrapper.find('.disp').text()).toBe('bob')
  })

  test('when enabled, a pristine field re-syncs on an external change (undo case)', async () => {
    const wrapper = await mountForm({
      defaultValues: { name: 'bob' },
      syncWithDefaultValues: true,
    })

    // User clears the field, and it gets saved (defaultValues follows to '').
    await wrapper.find('.inp').setValue('')
    await wrapper.setProps({ defaultValues: { name: '' } })
    expect(wrapper.find('.disp').text()).toBe('')

    // Undo reverts the underlying value back to 'bob' -> the form reflects it.
    await wrapper.setProps({ defaultValues: { name: 'bob' } })
    expect(wrapper.find('.disp').text()).toBe('bob')
  })

  test('when enabled, an in-progress local edit is never clobbered', async () => {
    const wrapper = await mountForm({
      defaultValues: { name: 'bob' },
      syncWithDefaultValues: true,
    })

    // User is typing (not yet saved, so defaultValues is still 'bob').
    await wrapper.find('.inp').setValue('bobby')

    // A concurrent external change arrives.
    await wrapper.setProps({ defaultValues: { name: 'alice' } })

    // The user's in-progress value wins; it isn't overwritten.
    expect(wrapper.find('.disp').text()).toBe('bobby')
  })

  test('an ancestor can enable syncing via provide/inject, without the prop', async () => {
    // Mirrors how the builder/automation editors enable syncing for all their forms.
    const wrapper = await testApp.mount(TestForm, {
      props: { defaultValues: { name: 'bob' } },
      global: { provide: { [syncFormsWithDefaultValuesKey]: true } },
    })
    expect(wrapper.find('.disp').text()).toBe('bob')

    await wrapper.setProps({ defaultValues: { name: 'alice' } })
    expect(wrapper.find('.disp').text()).toBe('alice')
  })

  test('the re-sync does not emit values-changed (no save/undo loop)', async () => {
    const wrapper = await mountForm({
      defaultValues: { name: 'bob' },
      syncWithDefaultValues: true,
    })

    const emitCountBefore = (wrapper.emitted('values-changed') || []).length

    // External change to a pristine field triggers a re-sync of `values`.
    await wrapper.setProps({ defaultValues: { name: 'alice' } })
    expect(wrapper.find('.disp').text()).toBe('alice')

    const emitCountAfter = (wrapper.emitted('values-changed') || []).length
    expect(emitCountAfter).toBe(emitCountBefore)
  })
})
