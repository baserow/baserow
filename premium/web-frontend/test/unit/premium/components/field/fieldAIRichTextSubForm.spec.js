import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import FieldAIRichTextSubForm from '@baserow_premium/components/field/FieldAIRichTextSubForm'

describe('FieldAIRichTextSubForm component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (defaultValues, { primary = false } = {}) =>
    testApp.mount(FieldAIRichTextSubForm, {
      props: {
        table: { id: 10 },
        view: {},
        allFieldsInTable: [],
        database: { id: 100, workspace: { id: 1 } },
        fieldType: 'ai',
        primary,
        defaultValues,
      },
    })

  const checkbox = (wrapper) => wrapper.find('input.checkbox__native')

  const submittedValues = async (wrapper) => {
    wrapper.vm.submit()
    await wrapper.vm.$nextTick()
    return wrapper.emitted('submitted')[0][0]
  }

  test('a new AI field starts with rich text formatting', async () => {
    const wrapper = await mountComponent({ name: '', type: '' })

    expect(checkbox(wrapper).element.checked).toBe(true)
    expect(await submittedValues(wrapper)).toEqual({
      long_text_enable_rich_text: true,
    })
  })

  test('a field converted from a type without the option starts rich', async () => {
    const wrapper = await mountComponent({ id: 1, type: 'text' })

    expect(checkbox(wrapper).element.checked).toBe(true)
  })

  test.each([true, false])(
    'an existing AI field keeps its stored flag %s',
    async (stored) => {
      const wrapper = await mountComponent({
        id: 1,
        type: 'ai',
        ai_output_type: 'text',
        long_text_enable_rich_text: stored,
      })

      expect(checkbox(wrapper).element.checked).toBe(stored)
      expect(await submittedValues(wrapper)).toEqual({
        long_text_enable_rich_text: stored,
      })
    }
  )

  test('an existing AI field without a stored flag stays plain', async () => {
    const wrapper = await mountComponent({ id: 1, type: 'ai' })

    expect(checkbox(wrapper).element.checked).toBe(false)
  })

  test.each([true, false])(
    'a long text field converted to AI keeps its flag %s',
    async (stored) => {
      const wrapper = await mountComponent({
        id: 1,
        type: 'long_text',
        long_text_enable_rich_text: stored,
      })

      expect(checkbox(wrapper).element.checked).toBe(stored)
    }
  )

  test('unticking the option submits plain text', async () => {
    const wrapper = await mountComponent({ name: '', type: '' })

    await checkbox(wrapper).setValue(false)

    expect(await submittedValues(wrapper)).toEqual({
      long_text_enable_rich_text: false,
    })
  })

  test.each([
    { name: '', type: '' },
    { id: 1, type: 'long_text', long_text_enable_rich_text: true },
  ])(
    'a primary field hides the option and submits plain text (%o)',
    async (defaultValues) => {
      const wrapper = await mountComponent(defaultValues, { primary: true })

      expect(checkbox(wrapper).exists()).toBe(false)
      expect(await submittedValues(wrapper)).toEqual({
        long_text_enable_rich_text: false,
      })
    }
  )
})
