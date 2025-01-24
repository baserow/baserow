import { RuntimeConcat } from '@baserow/modules/core/runtimeFormulaTypes'
import { expect } from '@jest/globals'

/** Tests for the RuntimeConcat class. */
describe('RuntimeConcat', () => {
  test.each([
    { args: [[['Apple', 'Banana']], 'Cherry'], expected: 'Apple,BananaCherry' },
    {
      args: [[['Apple', 'Banana']], ',Cherry'],
      expected: 'Apple,Banana,Cherry',
    },
    {
      args: [[['Apple', 'Banana']], ', Cherry'],
      expected: 'Apple,Banana, Cherry',
    },
  ])('should concatenate the runtime args correctly', ({ args, expected }) => {
    const runtimeConcat = new RuntimeConcat()
    const result = runtimeConcat.execute({}, args)
    expect(result).toBe(expected)
  })
})
