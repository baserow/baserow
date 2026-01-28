import {
  clone,
  isPromise,
  mappingToStringifiedJSONLines,
  getValueAtPath,
} from '@baserow/modules/core/utils/object'

describe('test utils object', () => {
  test('clone', () => {
    const o = {
      a: '1',
      b: '2',
      c: {
        d: '3',
      },
    }
    const cloned = clone(o)

    expect(o !== cloned).toBe(true)
    o.a = '5'
    o.c.d = '6'
    expect(cloned.a).toBe('1')
    expect(cloned.c.d).toBe('3')
  })

  test('mappingToStringifiedJSONLines', () => {
    expect(
      mappingToStringifiedJSONLines(
        {
          key_1: 'Value 1',
          key_2: 'Value 2',
          key_3: 'Value 3',
        },
        {
          key_1: '',
          key_a: [
            {
              key_b: '',
              key_2: '',
              key_3: '',
              key_c: {
                key_d: {
                  key_1: '',
                  key_e: [
                    {
                      key_3: '',
                    },
                  ],
                },
              },
            },
          ],
          key_2: '',
        }
      )
    ).toMatchObject({
      2: 'Value 1',
      6: 'Value 2',
      10: 'Value 1',
      13: 'Value 3',
      20: 'Value 2',
    })
  })

  test('isPromise', () => {
    expect(isPromise(new Promise(() => null))).toBeTruthy()
    expect(isPromise('string')).toBeFalsy()

    // This is one downside of the function, it shouldn't return true
    // but it does. Unfortunately this is as close to a good promise detection
    // as we can get
    expect(isPromise({ then: () => null, catch: () => null })).toBeTruthy()
  })

  test.each([
    ['a.b.c', 123],
    ['list.1.d', 789],
    ['list[1]d', 789],
    ['a.b.x', null],
    ['list.5.d', null],
    [
      '',
      {
        a: { b: { c: 123 } },
        list: [{ d: 456 }, { d: 789, e: 111 }],
        nested: [{ nested: [{ a: 1 }, { a: 2 }] }, { nested: [{ a: 3 }] }],
        b: ['1', '2', '3'],
      },
    ],
    ['a.b', { c: 123 }],
    ['a[b]', { c: 123 }],
    ['list', [{ d: 456 }, { d: 789, e: 111 }]],
    ['list.*', [{ d: 456 }, { d: 789, e: 111 }]],
    ['list.*.c', null],
    ['list.*.d', [456, 789]],
    ['list.*.e', [111]],
    ['nested.*.nested.*.a', [[1, 2], [3]]],
    ['nested[*].nested[*].a', [[1, 2], [3]]],
    ['nested.*.nested.0.a', [1, 3]],
    ['nested.*.nested.1.a', [2]],
    ['b', ['1', '2', '3']],
    ['b.*', ['1', '2', '3']],
    ['b.0', '1'],
  ])('getValueAtPath', (path, result) => {
    const obj = {
      a: { b: { c: 123 } },
      list: [{ d: 456 }, { d: 789, e: 111 }],
      nested: [{ nested: [{ a: 1 }, { a: 2 }] }, { nested: [{ a: 3 }] }],
      b: ['1', '2', '3'],
    }
    expect(getValueAtPath(obj, path)).toStrictEqual(result)
  })
})
