import {
  RuntimeAdd,
  RuntimeAnd,
  RuntimeCapitalize,
  RuntimeConcat,
  RuntimeDateTimeFormat,
  RuntimeDay,
  RuntimeDivide,
  RuntimeEqual,
  RuntimeGenerateUUID,
  RuntimeGet,
  RuntimeGetProperty,
  RuntimeGreaterThan,
  RuntimeGreaterThanOrEqual,
  RuntimeHour,
  RuntimeIf,
  RuntimeIsEven,
  RuntimeIsOdd,
  RuntimeLessThan,
  RuntimeLessThanOrEqual,
  RuntimeLower,
  RuntimeMinus,
  RuntimeMinute,
  RuntimeMonth,
  RuntimeMultiply,
  RuntimeNotEqual,
  RuntimeNow,
  RuntimeOr,
  RuntimeReplace,
  RuntimeRandomBool,
  RuntimeRandomFloat,
  RuntimeRandomInt,
  RuntimeRound,
  RuntimeSecond,
  RuntimeToday,
  RuntimeUpper,
  RuntimeYear,
  RuntimeLength,
  RuntimeContains,
  RuntimeReverse,
  RuntimeJoin,
  RuntimeSplit,
  RuntimeIsEmpty,
  RuntimeStrip,
  RuntimeSum,
  RuntimeAvg,
  RuntimeAt,
  RuntimeToArray,
} from '@baserow/modules/core/runtimeFormulaTypes'
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

describe('RuntimeGet', () => {
  test.each([
    { args: [['id']], expected: 101 },
    { args: [['fruit']], expected: 'Apple' },
    { args: [['color']], expected: 'Red' },
  ])('should get the correct object value', ({ args, expected }) => {
    const formulaType = new RuntimeGet()
    const context = {
      id: 101,
      fruit: 'Apple',
      color: 'Red',
    }
    const result = formulaType.execute(context, args)
    expect(result).toBe(expected)
  })
})

describe('RuntimeAdd', () => {
  test.each([
    { args: [1, 2], expected: 3 },
    { args: [2, 3], expected: 5 },
    { args: [2, 3.14], expected: 5.140000000000001 },
    { args: [2.43, 3.14], expected: 5.57 },
    { args: [-4, 23], expected: 19 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeAdd()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // These are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [null], expected: null },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
    // These are valid
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeAdd()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeAdd()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeMinus', () => {
  test.each([
    { args: [3, 2], expected: 1 },
    { args: [3.14, 4.56], expected: -1.4199999999999995 },
    { args: [45.25, -2], expected: 47.25 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeMinus()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // These are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [null], expected: null },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
    // These are valid
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeMinus()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeMinus()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeMultiply', () => {
  test.each([
    { args: [3, 1], expected: 3 },
    { args: [3.14, 4.56], expected: 14.318399999999999 },
    { args: [52.14, -2], expected: -104.28 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeMultiply()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // These are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [null], expected: null },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
    // These are valid
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeMultiply()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeMultiply()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeDivide', () => {
  test.each([
    { args: [4, 2], expected: 2 },
    { args: [3.14, 1.56], expected: 2.0128205128205128 },
    { args: [23.24, -2], expected: -11.62 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeDivide()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // These are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [null], expected: null },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
    // These are valid
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeDivide()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeDivide()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeEqual', () => {
  test.each([
    { args: [2, 2], expected: true },
    { args: [2, 3], expected: false },
    { args: ['foo', 'foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeEqual()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeEqual()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeEqual()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeNotEqual', () => {
  test.each([
    { args: [2, 2], expected: false },
    { args: [2, 3], expected: true },
    { args: ['foo', 'foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeNotEqual()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeNotEqual()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeNotEqual()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeGreaterThan', () => {
  test.each([
    { args: [2, 2], expected: false },
    { args: [2, 3], expected: false },
    { args: [3, 2], expected: true },
    { args: ['apple', 'ball'], expected: false },
    { args: ['ball', 'apple'], expected: true },
    { args: ['a', 1], expected: null },
    { args: [1, 'a'], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThan()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThan()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThan()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeLessThan', () => {
  test.each([
    { args: [2, 2], expected: false },
    { args: [2, 3], expected: true },
    { args: [3, 2], expected: false },
    { args: ['apple', 'ball'], expected: true },
    { args: ['ball', 'apple'], expected: false },
    { args: ['a', 1], expected: null },
    { args: [1, 'a'], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeLessThan()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeLessThan()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeLessThan()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeGreaterThanOrEqual', () => {
  test.each([
    { args: [2, 2], expected: true },
    { args: [2, 3], expected: false },
    { args: [3, 2], expected: true },
    { args: ['apple', 'ball'], expected: false },
    { args: ['ball', 'apple'], expected: true },
    { args: ['a', 1], expected: null },
    { args: [1, 'a'], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThanOrEqual()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThanOrEqual()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeGreaterThanOrEqual()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeLessThanOrEqual', () => {
  test.each([
    { args: [2, 2], expected: true },
    { args: [2, 3], expected: true },
    { args: [3, 2], expected: false },
    { args: ['apple', 'ball'], expected: true },
    { args: ['ball', 'apple'], expected: false },
    { args: ['a', 1], expected: null },
    { args: [1, 'a'], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeLessThanOrEqual()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [null], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeLessThanOrEqual()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeLessThanOrEqual()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeUpper', () => {
  test.each([
    { args: ['apple'], expected: 'APPLE' },
    { args: ['bAll'], expected: 'BALL' },
    { args: ['Foo Bar'], expected: 'FOO BAR' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeUpper()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeUpper()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeUpper()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeLower', () => {
  test.each([
    { args: ['apple'], expected: 'apple' },
    { args: ['bAll'], expected: 'ball' },
    { args: ['Foo Bar'], expected: 'foo bar' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeLower()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeLower()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeLower()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeCapitalize', () => {
  test.each([
    { args: ['apple'], expected: 'Apple' },
    { args: ['bAll'], expected: 'Ball' },
    { args: ['Foo Bar'], expected: 'Foo bar' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeCapitalize()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // All types are allowed
    { args: ['foo'], expected: undefined },
    { args: [true], expected: undefined },
    { args: [{}], expected: undefined },
    { args: [[]], expected: undefined },
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: [1], expected: undefined },
    { args: [3.14], expected: undefined },
    { args: ['23'], expected: undefined },
    { args: ['23.23'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeCapitalize()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeCapitalize()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeRound', () => {
  test.each([
    { args: ['23.45', 2], expected: 23.45 },
    // Defaults to 2 decimal places
    { args: [33.4567], expected: 33.46 },
    { args: [33, 0], expected: 33 },
    { args: [49.4587, 3], expected: 49.459 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeRound()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Number types are allowed
    { args: ['23.34'], expected: undefined },
    { args: [123], expected: undefined },
    { args: [123.45], expected: undefined },
    // Other types are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeRound()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeRound()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeIsEven', () => {
  test.each([
    { args: ['23.34'], expected: false },
    { args: [24], expected: true },
    { args: [33.4567], expected: false },
    { args: [33], expected: false },
    { args: [50], expected: true },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeIsEven()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Number types are allowed
    { args: ['23.34'], expected: undefined },
    { args: [123], expected: undefined },
    { args: [123.45], expected: undefined },
    // Other types are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsEven()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsEven()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeIsOdd', () => {
  test.each([
    { args: ['23.34'], expected: true },
    { args: [24], expected: false },
    { args: [33.4567], expected: true },
    { args: [33], expected: true },
    { args: [50], expected: false },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeIsOdd()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Number types are allowed
    { args: ['23.34'], expected: undefined },
    { args: [123], expected: undefined },
    { args: [123.45], expected: undefined },
    // Other types are invalid
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
    {
      args: [new Date(2025, 10, 6, 12, 30)],
      expected: new Date(2025, 10, 6, 12, 30),
    },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsOdd()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsOdd()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeDateTimeFormat', () => {
  test.each([
    { args: ['2025-11-03', 'YY/MM/DD'], expected: '25/11/03' },
    {
      args: ['2025-11-03', 'DD/MM/YYYY HH:mm:ss'],
      expected: '03/11/2025 00:00:00',
    },
    {
      args: ['2025-11-06 11:30:30.861096+00:00', 'DD/MM/YYYY HH:mm:ss'],
      expected: '06/11/2025 11:30:30',
    },
    { args: ['2025-11-06 11:30:30.861096+00:00', 'SSS'], expected: '861' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeDateTimeFormat()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeDateTimeFormat()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: true },
    { args: ['foo', 'bar', 'baz', 'x'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeDateTimeFormat()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeDay', () => {
  test.each([
    { args: ['2025-11-03'], expected: 3 },
    { args: ['2025-11-04 11:30:30.861096+00:00'], expected: 4 },
    { args: ['2025-11-05 11:30:30.861096+00:00'], expected: 5 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeDay()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeDay()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeDay()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeMonth', () => {
  test.each([
    // JS months are 0-indexed
    { args: ['2025-09-03'], expected: 8 },
    { args: ['2025-10-04 11:30:30.861096+00:00'], expected: 9 },
    { args: ['2025-11-05 11:30:30.861096+00:00'], expected: 10 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeMonth()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeMonth()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeMonth()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeYear', () => {
  test.each([
    // JS months are 0-indexed
    { args: ['2023-09-03'], expected: 2023 },
    { args: ['2024-10-04 11:30:30.861096+00:00'], expected: 2024 },
    { args: ['2025-11-05 11:30:30.861096+00:00'], expected: 2025 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeYear()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeYear()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeYear()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeHour', () => {
  test.each([
    // JS months are 0-indexed
    { args: ['2023-09-03'], expected: 0 },
    { args: ['2024-10-04 11:30:30.861096+00:00'], expected: 11 },
    { args: ['2025-11-05 12:30:30.861096+00:00'], expected: 12 },
    { args: ['2025-11-05 16:30:30.861096+00:00'], expected: 16 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeHour()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeHour()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeHour()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeMinute', () => {
  test.each([
    // JS months are 0-indexed
    { args: ['2023-09-03'], expected: 0 },
    { args: ['2024-10-04 11:28:31.861096+00:00'], expected: 28 },
    { args: ['2025-11-05 12:29:32.861096+00:00'], expected: 29 },
    { args: ['2025-11-05 16:30:33.861096+00:00'], expected: 30 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeMinute()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeMinute()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeMinute()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeSecond', () => {
  test.each([
    // JS months are 0-indexed
    { args: ['2023-09-03'], expected: 0 },
    { args: ['2024-10-04 11:28:31.861096+00:00'], expected: 31 },
    { args: ['2025-11-05 12:29:32.861096+00:00'], expected: 32 },
    { args: ['2025-11-05 16:30:33.861096+00:00'], expected: 33 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeSecond()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Date values are valid
    { args: [new Date(2025, 10, 6, 12, 30)], expected: undefined },
    { args: ['2025-11-06'], expected: undefined },
    { args: ['2025-11-06 11:30:30.861096+00:00'], expected: undefined },
    // All other types are invalid
    { args: ['23.34'], expected: '23.34' },
    { args: [123], expected: 123 },
    { args: [123.45], expected: 123.45 },
    { args: ['foo'], expected: 'foo' },
    { args: [true], expected: true },
    { args: [{}], expected: {} },
    { args: [[]], expected: [] },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeSecond()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeSecond()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeNow', () => {
  beforeAll(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2025-11-11T10:40:33.638Z'))
  })

  afterAll(() => {
    jest.useRealTimers()
  })

  test('execute returns expected value', () => {
    const formulaType = new RuntimeNow()
    const parsedArgs = formulaType.parseArgs([])
    const result = formulaType.execute({}, parsedArgs)
    expect(result.toISOString()).toBe('2025-11-11T10:40:33.638Z')
  })

  test.each([
    { args: [], expected: true },
    { args: ['foo'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeNow()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeToday', () => {
  beforeAll(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2025-11-11T10:40:33.638Z'))
  })

  afterAll(() => {
    jest.useRealTimers()
  })

  test('execute returns expected value', () => {
    const formulaType = new RuntimeToday()
    const parsedArgs = formulaType.parseArgs([])
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe('2025-11-11')
  })

  test.each([
    { args: [], expected: true },
    { args: ['foo'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeToday()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeGetProperty', () => {
  test.each([
    { args: ['{"foo": "bar"}', 'foo'], expected: 'bar' },
    { args: [{ foo: 'bar' }, 'baz'], expected: undefined },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeGetProperty()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toBe(expected)
  })

  test.each([
    // Object like values are allowed
    { args: ['{"foo": "bar"}', 'foo'], expected: undefined },
    { args: [{ foo: 'bar' }, 'baz'], expected: undefined },
    // Invalid types for 1st arg (2nd arg is cast to string)
    { args: ['foo', 'foo'], expected: 'foo' },
    { args: [12.34, 'bar'], expected: 12.34 },
    { args: [null, 'bar'], expected: null },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeGetProperty()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeGetProperty()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeRandomInt', () => {
  test.each([{ args: [1, 100] }, { args: [10.24, 100.54] }])(
    'execute returns expected value',
    ({ args }) => {
      const formulaType = new RuntimeRandomInt()
      const parsedArgs = formulaType.parseArgs(args)
      const result = formulaType.execute({}, parsedArgs)
      expect(result).toEqual(expect.any(Number))
    }
  )

  test.each([
    // Object like values are allowed
    { args: [1, 100], expected: undefined },
    { args: [2.5, 56.64], expected: undefined },
    { args: ['3', '4.5'], expected: undefined },
    // Invalid types for 1st arg
    { args: [{}, 5], expected: {} },
    { args: ['foo', 5], expected: 'foo' },
    // Invalid types for 2nd arg
    { args: [5, {}], expected: {} },
    { args: [5, 'foo'], expected: 'foo' },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeRandomInt()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeRandomInt()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeRandomFloat', () => {
  test.each([{ args: [1, 100] }, { args: [10.24, 100.54] }])(
    'execute returns expected value',
    ({ args }) => {
      const formulaType = new RuntimeRandomFloat()
      const parsedArgs = formulaType.parseArgs(args)
      const result = formulaType.execute({}, parsedArgs)
      expect(result).toEqual(expect.any(Number))
    }
  )

  test.each([
    // Object like values are allowed
    { args: [1, 100], expected: undefined },
    { args: [2.5, 56.64], expected: undefined },
    { args: ['3', '4.5'], expected: undefined },
    // Invalid types for 1st arg
    { args: [{}, 5], expected: {} },
    { args: ['foo', 5], expected: 'foo' },
    // Invalid types for 2nd arg
    { args: [5, {}], expected: {} },
    { args: [5, 'foo'], expected: 'foo' },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeRandomFloat()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeRandomFloat()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeRandomBool', () => {
  test('execute returns expected value', () => {
    const formulaType = new RuntimeRandomBool()
    const parsedArgs = formulaType.parseArgs([])
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expect.any(Boolean))
  })

  test.each([
    { args: [], expected: true },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeRandomBool()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeGenerateUUID', () => {
  test('execute returns expected value', () => {
    const formulaType = new RuntimeGenerateUUID()
    const parsedArgs = formulaType.parseArgs([])
    const result = formulaType.execute({}, parsedArgs)

    expect(typeof result).toBe('string')
    const uuidV4Regex =
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

    expect(uuidV4Regex.test(result)).toBe(true)
  })

  test.each([
    { args: [], expected: true },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeGenerateUUID()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeIf', () => {
  test.each([
    { args: [true, 'foo', 'bar'], expected: 'foo' },
    { args: [false, 'foo', 'bar'], expected: 'bar' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeIf()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    // Valid types for 1st arg (2nd and 3rd args can be Any)
    { args: [true, 'foo', 'bar'], expected: undefined },
    { args: [false, 'foo', 'bar'], expected: undefined },
    { args: ['true', 'foo', 'bar'], expected: undefined },
    { args: ['false', 'foo', 'bar'], expected: undefined },
    { args: ['True', 'foo', 'bar'], expected: undefined },
    { args: ['False', 'foo', 'bar'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeIf()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: false },
    { args: ['foo', 'bar', 'baz'], expected: true },
    { args: ['foo', 'bar', 'baz', 'x'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeIf()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeAnd', () => {
  test.each([
    { args: [true, true], expected: true },
    { args: [true, false], expected: false },
    { args: [false, false], expected: false },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeAnd()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    // Valid types for 1st arg
    { args: [true, true], expected: undefined },
    { args: [false, true], expected: undefined },
    { args: ['true', true], expected: undefined },
    { args: ['false', true], expected: undefined },
    { args: ['True', true], expected: undefined },
    { args: ['False', true], expected: undefined },
    // Valid types for 2nd arg
    { args: [true, false], expected: undefined },
    { args: [true, false], expected: undefined },
    { args: [true, 'true'], expected: undefined },
    { args: [true, 'false'], expected: undefined },
    { args: [true, 'True'], expected: undefined },
    { args: [true, 'False'], expected: undefined },
    // Invalid types for 1st arg
    { args: ['foo', true], expected: undefined },
    { args: [{}, true], expected: undefined },
    { args: ['', true], expected: undefined },
    { args: [100, true], expected: undefined },
    // Invalid types for 2nd arg
    { args: [true, 'foo'], expected: undefined },
    { args: [true, {}], expected: undefined },
    { args: [true, ''], expected: undefined },
    { args: [true, 100], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeAnd()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeAnd()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})
//

describe('RuntimeOr', () => {
  test.each([
    { args: [true, true], expected: true },
    { args: [true, false], expected: true },
    { args: [false, false], expected: false },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeOr()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    // Valid types for 1st arg
    { args: [true, true], expected: undefined },
    { args: [false, true], expected: undefined },
    { args: ['true', true], expected: undefined },
    { args: ['false', true], expected: undefined },
    { args: ['True', true], expected: undefined },
    { args: ['False', true], expected: undefined },
    // Valid types for 2nd arg
    { args: [true, false], expected: undefined },
    { args: [true, false], expected: undefined },
    { args: [true, 'true'], expected: undefined },
    { args: [true, 'false'], expected: undefined },
    { args: [true, 'True'], expected: undefined },
    { args: [true, 'False'], expected: undefined },
    // Invalid types for 1st arg
    { args: ['foo', true], expected: undefined },
    { args: [{}, true], expected: undefined },
    { args: ['', true], expected: undefined },
    { args: [100, true], expected: undefined },
    // Invalid types for 2nd arg
    { args: [true, 'foo'], expected: undefined },
    { args: [true, {}], expected: undefined },
    { args: [true, ''], expected: undefined },
    { args: [true, 100], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeOr()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeOr()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeReplace', () => {
  test.each([
    { args: ['Hello, world!', 'l', '-'], expected: 'He--o, wor-d!' },
    { args: ['1112111', 2, 3], expected: '1113111' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeReplace()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['foo', 'bar', 'baz'], expected: undefined },
    { args: [100, 200, 300], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeReplace()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: false },
    { args: ['foo', 'bar', 'baz'], expected: true },
    { args: ['foo', 'bar', 'baz', 'x'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeReplace()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeLength', () => {
  test.each([
    { args: ['Hello, world!'], expected: 13 },
    { args: ['0'], expected: 1 },
    { args: [4], expected: null },
    { args: [{ a: 'b', c: 'd' }], expected: 2 },
    { args: [['a', 'b', 'c', 'd']], expected: 4 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeLength()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['foo'], expected: undefined },
    { args: ['{"foo": "bar"}'], expected: undefined },
    { args: ['["foo", "bar"]'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeLength()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeLength()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeContains', () => {
  test.each([
    { args: ['Hello, world!', 'll'], expected: true },
    { args: ['Hello, world!', 'goodbye'], expected: false },
    { args: [{ foo: 'bar' }, 'foo'], expected: true },
    { args: [['foo', 'bar'], 'foo'], expected: true },
    { args: [1, 'foo'], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeContains()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['foo'], expected: undefined },
    { args: ['{"foo": "bar"}'], expected: undefined },
    { args: ['["foo", "bar"]'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeContains()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeContains()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeReverse', () => {
  test.each([
    { args: ['Hello, world!'], expected: '!dlrow ,olleH' },
    { args: ['😀💙🚀'], expected: '🚀💙😀' },
    { args: [['foo', 'bar']], expected: ['bar', 'foo'] },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeReverse()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['foo'], expected: undefined },
    { args: ['😀💙🚀'], expected: undefined },
    { args: ['["foo", "bar"]'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeReverse()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeReverse()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeJoin', () => {
  test.each([
    { args: [['foo', 'bar']], expected: 'foo,bar' },
    { args: ['foo', '*'], expected: 'f*o*o' },
    { args: [1], expected: null },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeJoin()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['["foo", "bar"]'], expected: undefined },
    { args: ['["foo", "bar"]', 'baz'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeJoin()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeJoin()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeSplit', () => {
  test.each([
    { args: ['foobar', 'b'], expected: ['foo', 'ar'] },
    { args: ['foobar'], expected: ['f', 'o', 'o', 'b', 'a', 'r'] },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeSplit()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['foobar'], expected: undefined },
    { args: ['foobar', 'baz'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeSplit()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeSplit()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeIsEmpty', () => {
  test.each([
    { args: [''], expected: true },
    { args: [undefined], expected: true },
    { args: [null], expected: true },
    { args: [[]], expected: true },
    { args: [{}], expected: true },
    { args: ['[]'], expected: false },
    { args: ['{}'], expected: false },
    { args: [' '], expected: true },
    { args: ['0'], expected: false },
    { args: [0], expected: false },
    { args: [0.1], expected: false },
    { args: ['foo'], expected: false },
    { args: [['foo']], expected: false },
    { args: [{ foo: 'bar' }], expected: false },
    { args: ['["foo"]'], expected: false },
    { args: ['{"foo": "bar"}'], expected: false },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeIsEmpty()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: [''], expected: undefined },
    { args: ['foobar'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsEmpty()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeIsEmpty()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeStrip', () => {
  test.each([
    { args: [''], expected: null },
    { args: [' '], expected: null },
    { args: [' foo '], expected: 'foo' },
    { args: ['foo'], expected: 'foo' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeStrip()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: [''], expected: undefined },
    { args: ['foobar'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeStrip()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeStrip()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeSum', () => {
  test.each([
    { args: [[2.5, 3, 'foo', 4]], expected: null },
    { args: [['2', '3', '4']], expected: 9 },
    { args: [[2.5, 3, 4]], expected: 9.5 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeSum()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: [''], expected: undefined },
    { args: ['[]'], expected: undefined },
    { args: [[]], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeSum()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeSum()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeAvg', () => {
  test.each([
    { args: [[1, 2, 'foo', 3, 4]], expected: null },
    { args: [[1, 2, 3, 4]], expected: 2.5 },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeAvg()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: [''], expected: undefined },
    { args: ['[]'], expected: undefined },
    { args: [[]], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeAvg()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeAvg()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeAt', () => {
  test.each([
    { args: [['foo', 'bar'], 0], expected: 'foo' },
    { args: ['foobar', 3], expected: 'b' },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeAt()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: ['[]', 1], expected: undefined },
    { args: [[], '2'], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeAt()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: false },
    { args: ['foo', 'bar'], expected: true },
    { args: ['foo', 'bar', 'baz'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeAt()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})

describe('RuntimeToArray', () => {
  test.each([
    { args: ['1,2,foo,bar'], expected: ['1', '2', 'foo', 'bar'] },
    { args: ['1'], expected: ['1'] },
    { args: [1], expected: ['1'] },
    { args: ['foo'], expected: ['foo'] },
    { args: [''], expected: [] },
  ])('execute returns expected value', ({ args, expected }) => {
    const formulaType = new RuntimeToArray()
    const parsedArgs = formulaType.parseArgs(args)
    const result = formulaType.execute({}, parsedArgs)
    expect(result).toEqual(expected)
  })

  test.each([
    { args: [''], expected: undefined },
    { args: [[]], expected: undefined },
  ])('validates type of args', ({ args, expected }) => {
    const formulaType = new RuntimeToArray()
    const result = formulaType.validateTypeOfArgs(args)
    expect(result).toStrictEqual(expected)
  })

  test.each([
    { args: [], expected: false },
    { args: ['foo'], expected: true },
    { args: ['foo', 'bar'], expected: false },
  ])('validates number of args', ({ args, expected }) => {
    const formulaType = new RuntimeToArray()
    const result = formulaType.validateNumberOfArgs(args)
    expect(result).toStrictEqual(expected)
  })
})
