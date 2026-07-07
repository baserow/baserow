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
})
