import { describe, expect, test } from 'vitest'
import { removeActionInputReferences } from '@baserow/modules/agent/utils/actionFormulas'

const inputId = '11111111-1111-4111-8111-111111111111'
const path = `tool_input.${inputId}`
const formula = (text, mode = 'simple') => ({
  formula: text,
  mode,
  version: '0.1',
})

describe('removing action input references', () => {
  test.each([
    [`get('${path}')`, ''],
    [`GET( ('${path}') )`, ''],
    [
      `concat('Hello 👋 ', get('${path}'), get('tool_input.other'))`,
      "concat('Hello 👋 ', '', get('tool_input.other'))",
    ],
    [`concat(get('${path}'), '-', get("${path}"))`, "concat('', '-', '')"],
    [`if(true, get('${path}'), 'fallback')`, "if(true, '', 'fallback')"],
    [`'get(\\'${path}\\')'`, `'get(\\'${path}\\')'`],
    ["get('tool_input.other')", "get('tool_input.other')"],
    [`concat(get('${path}'),`, `concat(get('${path}'),`],
  ])('rewrites %s without touching surrounding content', (source, expected) => {
    expect(removeActionInputReferences(formula(source), [inputId])).toEqual(
      formula(expected)
    )
  })

  test('handles nested service fields and advanced formulas, preserving raw strings and metadata', () => {
    const service = {
      integration_id: 10,
      body: formula(`get('${path}')`, 'raw'),
      headers: [
        {
          name: formula("'x-name'"),
          value: {
            ...formula(`get('${path}')`, 'advanced'),
            format: 'markdown',
          },
        },
      ],
      optional: null,
    }
    const result = removeActionInputReferences(service, [inputId])
    expect(result).toEqual({
      ...service,
      headers: [
        {
          ...service.headers[0],
          value: { ...service.headers[0].value, formula: '' },
        },
      ],
    })
    expect(service.headers[0].value.formula).toBe(`get('${path}')`)
  })
})
