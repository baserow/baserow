import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { TestApp } from '@baserow/test/helpers/testApp'
import { FromTipTapVisitor } from '@baserow/modules/core/formula/tiptap/fromTipTapVisitor'
import testCases from '@baserow_test_cases/tip_tap_visitor_cases.json'

describe('fromTipTapVisitor', () => {
  let testApp = null
  beforeEach(() => {
    testApp = new TestApp()
  })

  testCases.forEach(({ formula, content }) => {
    it('should return the expected formula', () => {
      const functionCollection = new RuntimeFunctionCollection(
        testApp.store.$registry
      )
      const result = new FromTipTapVisitor(functionCollection).visit(content)
      expect(result).toEqual(formula)
    })
  })
})
