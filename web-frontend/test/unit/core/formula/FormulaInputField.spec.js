import { TestApp } from '@baserow/test/helpers/testApp'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import FormulaInputField, {
  disambiguateMinusOperator,
} from '@baserow/modules/core/components/formula/FormulaInputField.vue'

// ── disambiguateMinusOperator ──────────────────────────────────────

describe('disambiguateMinusOperator', () => {
  it('inserts spaces around binary minus before a digit', () => {
    expect(disambiguateMinusOperator('x-1')).toBe('x - 1')
  })

  it('does not touch minus at the start of formula', () => {
    expect(disambiguateMinusOperator('-1')).toBe('-1')
  })

  it('disambiguates after a closing parenthesis', () => {
    expect(disambiguateMinusOperator('today()-200')).toBe('today() - 200')
  })

  it('disambiguates multiple binary minuses', () => {
    expect(disambiguateMinusOperator('a-1+b-2')).toBe('a - 1+b - 2')
  })

  it('does not touch minus inside single-quoted strings', () => {
    expect(disambiguateMinusOperator("'x-1'")).toBe("'x-1'")
  })

  it('does not touch minus inside double-quoted strings', () => {
    expect(disambiguateMinusOperator('"x-1"')).toBe('"x-1"')
  })

  it('handles escaped quotes inside strings', () => {
    expect(disambiguateMinusOperator("'it\\'s-1'")).toBe("'it\\'s-1'")
  })

  it('does not disambiguate minus followed by non-digit', () => {
    expect(disambiguateMinusOperator('x-y')).toBe('x-y')
  })

  it('disambiguates in complex formula', () => {
    const input = '(Year(Today())-200)*100+Month(Today())'
    const result = disambiguateMinusOperator(input)
    expect(result).toBe('(Year(Today()) - 200)*100+Month(Today())')
  })

  it('returns empty string for empty input', () => {
    expect(disambiguateMinusOperator('')).toBe('')
  })

  it('handles digit-minus-digit', () => {
    expect(disambiguateMinusOperator('5-3')).toBe('5 - 3')
  })
})

// ── Advanced-mode roundtrip ─────────────────────────────────────────
// A "roundtrip" is the full conversion cycle:
//   formula string → ANTLR parse → AST → ToTipTapVisitor → TipTap JSON
//   → FromTipTapVisitor → formula string
// These tests verify that a formula survives this cycle and comes back
// semantically equivalent, catching bugs in either visitor.

describe('Advanced mode formula roundtrip', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  function roundtrip(formula) {
    const functionCollection = new RuntimeFunctionCollection(
      testApp.store.$registry
    )
    const disambiguated = disambiguateMinusOperator(formula)
    const tree = parseBaserowFormula(disambiguated)
    const tipTapContent = new ToTipTapVisitor(
      functionCollection,
      'advanced'
    ).visit(tree)
    const result = new FromTipTapVisitor(functionCollection, 'advanced').visit(
      tipTapContent
    )
    return result
  }

  it('roundtrips a simple function call', () => {
    expect(roundtrip('today()')).toBe('today()')
  })

  it('roundtrips a function with arguments', () => {
    // Advanced mode visitor drops whitespace around commas
    expect(roundtrip("if(true, 'yes', 'no')")).toBe("if(true,'yes','no')")
  })

  it('roundtrips a formula with binary minus', () => {
    // Minus operator adds a trailing space for disambiguation
    expect(roundtrip('year(today())-200')).toBe('year(today())-  200')
  })

  it('roundtrips a complex formula with minus', () => {
    const formula = '(year(today())-200)*100+month(today())'
    const result = roundtrip(formula)
    expect(result).toBe('(year(today())-  200)*100+month(today())')
  })

  it('roundtrips nested function calls', () => {
    expect(roundtrip('year(today())')).toBe('year(today())')
  })

  it('roundtrips grouped expressions', () => {
    expect(roundtrip('(1+2)*3')).toBe('(1+2)*3')
  })

  it('roundtrips addition', () => {
    expect(roundtrip('1+2')).toBe('1+2')
  })

  it('roundtrips boolean literal', () => {
    expect(roundtrip('true')).toBe('true')
  })

  it('roundtrips string literal', () => {
    expect(roundtrip("'hello'")).toBe("'hello'")
  })

  it('roundtrips number literal', () => {
    expect(roundtrip('42')).toBe('42')
  })

  it('roundtrips decimal literal', () => {
    expect(roundtrip('3.14')).toBe('3.14')
  })
})

// ── Validation on display ───────────────────────────────────────────
// An invalid stored formula (e.g. one that leaked a `$formula:` prefix)
// must surface its error state as soon as it is displayed, not only after
// the user edits the field.

describe('FormulaInputField validates on display', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountField(value) {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value, mode: 'advanced' },
    })
    await wrapper.vm.$nextTick()
    return wrapper
  }

  it('flags an invalid initial value without requiring an edit', async () => {
    const wrapper = await mountField('$formula: now()')
    expect(wrapper.vm.isFormulaInvalid).toBe(true)
    expect(wrapper.find('.formula-input-field--error').exists()).toBe(true)
  })

  it('does not flag a valid initial value', async () => {
    const wrapper = await mountField('now()')
    expect(wrapper.vm.isFormulaInvalid).toBe(false)
    expect(wrapper.find('.formula-input-field--error').exists()).toBe(false)
  })

  it('re-validates when the displayed value changes', async () => {
    const wrapper = await mountField('now()')
    expect(wrapper.vm.isFormulaInvalid).toBe(false)

    await wrapper.setProps({ value: '$formula: now()' })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isFormulaInvalid).toBe(true)
  })

  it('emits update:invalid when validity changes', async () => {
    const wrapper = await mountField('now()')
    expect(wrapper.emitted('update:invalid')).toBeUndefined()

    await wrapper.setProps({ value: '$formula: now()' })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:invalid').at(-1)).toEqual([true])

    await wrapper.setProps({ value: 'today()' })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:invalid').at(-1)).toEqual([false])
  })

  it('emits update:invalid for an invalid initial value', async () => {
    const wrapper = await mountField('$formula: now()')
    expect(wrapper.emitted('update:invalid').at(-1)).toEqual([true])
  })
})

describe('FormulaInputField mode changes', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  it('keeps an expert formula empty after switching to basic mode', async () => {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: 'now()', mode: 'advanced' },
    })

    wrapper.vm.handleModeChange('simple')
    await wrapper.setProps({ mode: 'simple' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.formula-input-field--formula-empty').exists()).toBe(
      true
    )
    expect(wrapper.emitted('input').at(-1)).toEqual([''])
  })

  it('keeps a basic formula when switching to expert mode', async () => {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: 'now()', mode: 'simple' },
    })

    wrapper.vm.handleModeChange('advanced')
    await wrapper.setProps({ mode: 'advanced' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.formula-input-field--formula-empty').exists()).toBe(
      false
    )
    expect(wrapper.emitted('input').at(-1)).toEqual(['now()'])
  })

  async function mountField(props = {}, slots = {}) {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: {
        value: '',
        mode: 'simple',
        allowRawValues: true,
        ...props,
      },
      slots,
    })
    await wrapper.vm.$nextTick()
    return wrapper
  }

  it('does not show the raw mode toggle unless raw values are allowed', async () => {
    const wrapper = await mountField({ allowRawValues: false })

    expect(wrapper.find('.formula-input-field__raw-mode-toggle').exists()).toBe(
      false
    )
  })

  it('renders a default form input in raw mode', async () => {
    const wrapper = await mountField({
      value: '#acc8f8',
      mode: 'raw',
    })

    const input = wrapper.find('.form-input__input')
    expect(input.exists()).toBe(true)
    expect(input.element.value).toBe('#acc8f8')

    await input.setValue('#ffffff')
    expect(wrapper.emitted('input').at(-1)).toEqual(['#ffffff'])
  })

  it('renders the raw input slot when provided', async () => {
    const wrapper = await mountField(
      {
        value: 'primary',
        mode: 'raw',
      },
      {
        'raw-input': `
          <template #raw-input="{ value, input }">
            <textarea
              class="custom-raw-input"
              :value="value"
              @input="input($event.target.value)"
            />
          </template>
        `,
      }
    )

    const input = wrapper.find('.custom-raw-input')
    const rawInputContainer = wrapper.find('.formula-input-field__raw-input')
    expect(input.exists()).toBe(true)
    expect(rawInputContainer.find('.custom-raw-input').exists()).toBe(true)
    expect(input.element.value).toBe('primary')

    await input.setValue('secondary')
    expect(wrapper.emitted('input').at(-1)).toEqual(['secondary'])
  })

  it('switches from raw mode to simple mode without changing the value', async () => {
    const wrapper = await mountField({
      value: "#acc'8f8",
      mode: 'raw',
    })

    await wrapper.find('.formula-input-field__raw-mode-toggle').trigger('click')

    expect(wrapper.emitted('update:mode').at(-1)).toEqual(['simple'])
    expect(wrapper.emitted('input').at(-1)).toEqual(["#acc'8f8"])
  })

  it('asks for confirmation before switching a populated simple formula to raw mode', async () => {
    const wrapper = await mountField({
      value: "'#acc8f8'",
      mode: 'simple',
    })

    await wrapper.find('.formula-input-field__raw-mode-toggle').trigger('click')

    expect(wrapper.vm.$refs.rawModeModal.$refs.modal.open).toBe(true)
    expect(wrapper.emitted('update:mode')).toBeUndefined()
    expect(wrapper.emitted('input')).toBeUndefined()
  })

  it('clears a simple formula when confirming the switch to raw mode', async () => {
    const wrapper = await mountField({
      value: "'#acc8f8'",
      mode: 'simple',
    })

    await wrapper.find('.formula-input-field__raw-mode-toggle').trigger('click')
    wrapper.vm.$refs.rawModeModal.confirm()

    expect(wrapper.emitted('update:mode').at(-1)).toEqual(['raw'])
    expect(wrapper.emitted('input').at(-1)).toEqual([''])
  })

  it('switches an empty simple formula to raw mode without confirmation', async () => {
    const wrapper = await mountField()

    await wrapper.find('.formula-input-field__raw-mode-toggle').trigger('click')

    expect(wrapper.vm.$refs.rawModeModal.$refs.modal.open).toBe(false)
    expect(wrapper.emitted('update:mode').at(-1)).toEqual(['raw'])
    expect(wrapper.emitted('input').at(-1)).toEqual([''])
  })
})
