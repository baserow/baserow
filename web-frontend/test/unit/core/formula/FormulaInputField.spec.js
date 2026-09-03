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

  it('does not flag an incomplete formula in a read-only field', async () => {
    // Read-only fields display snippets such as the help tooltip's `get()`
    // example, which is deliberately missing its path.
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: 'get()', mode: 'advanced', readOnly: true },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isFormulaInvalid).toBe(false)
    expect(wrapper.find('.formula-input-field--error').exists()).toBe(false)
    expect(wrapper.emitted('update:invalid')).toBeUndefined()
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
})

// ── Help tooltip example insertion ──────────────────────────────────
// Clicking an example in the Data Explorer's help tooltip inserts that
// example's formula into the editor at the cursor.

describe('FormulaInputField example insertion', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const example = { formula: "upper('hello')", result: "'HELLO'" }

  /** The editor text without the zero-width spaces used for cursor slots. */
  function editorText(wrapper) {
    return wrapper
      .find('.formula-input-field')
      .text()
      .replace(/\u200b/g, '')
  }

  it('inserts the example into an empty advanced-mode field', async () => {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: '', mode: 'advanced' },
    })
    expect(wrapper.emitted('input')).toBeUndefined()

    wrapper.vm.handleExampleSelected(example)
    await wrapper.vm.$nextTick()

    expect(editorText(wrapper)).toBe("upper('hello')")
    expect(wrapper.emitted('input').at(-1)).toEqual(["upper('hello')"])
  })

  it('inserts the example at the cursor', async () => {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: 'lower()', mode: 'advanced' },
    })
    // Place the cursor in the (empty) argument slot of `lower(`: ZWS (1),
    // function node (1), so position 3 sits right after the function name.
    wrapper.vm.editor.commands.setTextSelection(3)

    wrapper.vm.handleExampleSelected(example)
    await wrapper.vm.$nextTick()

    expect(editorText(wrapper)).toBe("lower(upper('hello'))")
    expect(wrapper.emitted('input').at(-1)).toEqual(["lower(upper('hello'))"])
  })

  it('ignores examples in simple mode', async () => {
    const wrapper = await testApp.mount(FormulaInputField, {
      props: { value: '', mode: 'simple' },
    })

    wrapper.vm.handleExampleSelected(example)
    await wrapper.vm.$nextTick()

    expect(editorText(wrapper)).toBe('')
    expect(wrapper.emitted('input')).toBeUndefined()
  })
})
