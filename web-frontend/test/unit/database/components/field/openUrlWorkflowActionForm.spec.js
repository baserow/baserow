import { TestApp } from '@baserow/test/helpers/testApp'
import OpenUrlWorkflowActionForm from '@baserow/modules/database/components/field/OpenUrlWorkflowActionForm'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import DatabaseFormulaInput from '@baserow/modules/database/components/field/DatabaseFormulaInput'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// Read rather than imported: the i18n loader turns an imported locale file
// into compiled message ASTs, which the copy below can't be read off of.
const en = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'modules/database/locales/en.json'),
    'utf8'
  )
)

describe('OpenUrlWorkflowActionForm', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = async (defaultValues = {}) =>
    testApp.mount(OpenUrlWorkflowActionForm, {
      propsData: { defaultValues },
    })

  test('a blank target reports Same tab as selected', async () => {
    const wrapper = await mountForm({
      url: { formula: "'https://x.test'", mode: 'simple' },
    })

    expect(wrapper.findComponent(SegmentControl).vm.activeIndex).toBe(0)
  })

  test('a blank target selects New tab', async () => {
    const wrapper = await mountForm({
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'blank',
    })

    const segmentControl = wrapper.findComponent(SegmentControl)
    expect(segmentControl.vm.activeIndex).toBe(1)
    // Translations resolve to their key in the test environment, so the copy
    // the design asks for is asserted on the locale file itself.
    expect(segmentControl.vm.segments.map((s) => s.label)).toEqual([
      'openUrlWorkflowActionForm.sameTab',
      'openUrlWorkflowActionForm.newTab',
    ])
    expect(en.openUrlWorkflowActionForm.sameTab).toBe('Same tab')
    expect(en.openUrlWorkflowActionForm.newTab).toBe('New tab')
  })

  test('switching back to Same tab emits the self target', async () => {
    const wrapper = await mountForm({
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'blank',
    })

    await wrapper
      .findComponent(SegmentControl)
      .findAll('.segment-control__button')[0]
      .trigger('click')

    const emitted = wrapper.emitted('values-changed')
    expect(emitted[emitted.length - 1][0].target).toBe('self')
  })

  test('the url input resolves against the fields data provider only', async () => {
    const wrapper = await mountForm({
      url: { formula: "'https://x.test'", mode: 'simple' },
    })

    const input = wrapper.findComponent(DatabaseFormulaInput)
    expect(input.props('dataProvidersAllowed')).toEqual(['fields'])
    expect(input.vm.$attrs.placeholder).toBe(
      'openUrlWorkflowActionForm.urlPlaceholder'
    )
    expect(en.openUrlWorkflowActionForm.urlPlaceholder).toBe('URL...')
  })

  test('an unparseable formula blocks submission', async () => {
    const wrapper = await mountForm({
      url: { formula: "'https://x.test'", mode: 'simple' },
    })
    expect(wrapper.vm.isFormValid()).toBe(true)

    // The formula input only emits `input` for parseable formulas, so an
    // invalid one is only ever reported through `update:invalid`.
    await wrapper
      .findComponent(DatabaseFormulaInput)
      .vm.$emit('update:invalid', true)

    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('it only submits its own values', async () => {
    const wrapper = await mountForm({
      id: 7,
      order: 1,
      field_id: 3,
      type: 'open_url',
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'blank',
    })

    expect(wrapper.vm.getFormValues()).toEqual({
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'blank',
    })
  })
})
