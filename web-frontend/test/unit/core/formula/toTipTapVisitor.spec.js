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
})
