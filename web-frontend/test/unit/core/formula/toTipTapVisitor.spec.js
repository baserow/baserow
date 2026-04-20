import { TestApp } from '@baserow/test/helpers/testApp'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import testCases from '@baserow_test_cases/tip_tap_visitor_cases.json'

describe('toTipTapVisitor', () => {
  let testApp = null
  beforeEach(() => {
    testApp = new TestApp()
  })

  testCases.forEach(({ formula, content }) => {
    it(`should return the expected formula for ${formula}`, () => {
      const functionCollection = new RuntimeFunctionCollection(
        testApp.store.$registry
      )
      // We don't want to test empty formula
      if (formula) {
        const tree = parseBaserowFormula(formula)
        const result = new ToTipTapVisitor(functionCollection).visit(tree)
        expect(result).toEqual(content)
      }
    })
  })

  describe('tolerant parsing (partial / pasted formulas)', () => {
    const visitTolerantly = (formula, mode = 'simple') => {
      const functionCollection = new RuntimeFunctionCollection(
        testApp.store.$registry
      )
      const tree = parseBaserowFormula(formula, false)
      return new ToTipTapVisitor(functionCollection, mode).visit(tree)
    }

    /**
     * Recursively collects every `{type, text}` leaf in a TipTap doc so tests
     * can assert on structural properties without pinning the exact tree
     * shape (which is sensitive to ANTLR's error recovery choices).
     */
    const flattenLeaves = (node, out = []) => {
      if (!node) return out
      if (Array.isArray(node)) {
        node.forEach((child) => flattenLeaves(child, out))
        return out
      }
      if (Array.isArray(node.content)) {
        flattenLeaves(node.content, out)
      } else if (node.type) {
        out.push({ type: node.type, text: node.text, attrs: node.attrs })
      }
      return out
    }

    const allText = (doc) =>
      flattenLeaves(doc)
        .filter((n) => n.type === 'text' && typeof n.text === 'string')
        .map((n) => n.text)
        .join('')

    const componentTypes = (doc) =>
      flattenLeaves(doc)
        .map((n) => n.type)
        .filter((t) => t !== 'text')

    const functionNames = (doc) =>
      flattenLeaves(doc)
        .filter((n) => n.type === 'function-formula-component')
        .map((n) => n.attrs?.functionName)

    it.each([
      'month',
      'month(',
      'year(today()',
      'month + year(today())',
      'concat("a", month)',
      'year(today())- 200*100+month + year(today())',
    ])('does not throw and produces a valid doc for %s', (formula) => {
      const simpleResult = visitTolerantly(formula, 'simple')
      const advancedResult = visitTolerantly(formula, 'advanced')

      expect(simpleResult?.type).toBe('doc')
      expect(advancedResult?.type).toBe('doc')
      // Synthetic "<missing 'X'>" markers must never leak into rendered text.
      expect(allText(simpleResult)).not.toMatch(/<missing/)
      expect(allText(advancedResult)).not.toMatch(/<missing/)
    })

    it('renders a bare identifier (`month`) as plain text', () => {
      const simple = visitTolerantly('month', 'simple')
      expect(allText(simple)).toBe('month')
      expect(componentTypes(simple)).toEqual([])
    })

    it('renders a dangling `month(` prefix as plain text without highlighting', () => {
      const simple = visitTolerantly('month(', 'simple')
      expect(allText(simple)).toBe('month(')
      expect(functionNames(simple)).toEqual([])
    })

    it('keeps the inner call highlighted when the outer paren is missing', () => {
      const simple = visitTolerantly('year(today()', 'simple')
      expect(allText(simple)).toContain('year(')

      const advanced = visitTolerantly('year(today()', 'advanced')
      // `today()` is a full valid sub-expression, it must keep its component.
      expect(functionNames(advanced)).toContain('today')
    })

    it('keeps valid siblings highlighted around a broken identifier', () => {
      const advanced = visitTolerantly('concat("a", month)', 'advanced')
      // `month` survives as plain text; the enclosing `concat(` prefix too.
      expect(allText(advanced)).toContain('month')
      expect(allText(advanced)).toContain('concat(')
    })

    it('highlights the valid prefix of a complex pasted formula', () => {
      const formula = 'year(today())- 200*100+month + year(today())'
      const advanced = visitTolerantly(formula, 'advanced')

      // All valid function calls are still rendered as components.
      expect(functionNames(advanced).filter((n) => n === 'year')).toHaveLength(
        2
      )
      expect(functionNames(advanced).filter((n) => n === 'today')).toHaveLength(
        2
      )
      // Operators detected before the broken identifier are preserved.
      const text = allText(advanced)
      expect(text).toContain('200')
      expect(text).toContain('100')
      expect(text).toContain('month')
      expect(componentTypes(advanced)).toContain('operator-formula-component')
    })
  })
})
