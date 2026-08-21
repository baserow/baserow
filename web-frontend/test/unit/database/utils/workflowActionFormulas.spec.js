import {
  rewriteActionFormulaIds,
  rewriteFormulaActionIds,
  unresolvedActionIds,
} from '@baserow/modules/database/utils/workflowActionFormulas'

describe('workflowActionFormulas', () => {
  test('a client id becomes the created action id', () => {
    expect(
      rewriteFormulaActionIds("get('previous_action.abc.id')", { abc: 7 })
    ).toBe("get('previous_action.7.id')")
  })

  test('two references in one formula are both rewritten', () => {
    expect(
      rewriteFormulaActionIds(
        "concat(get('previous_action.abc.id'),get('previous_action.def.id'))",
        { abc: 7, def: 8 }
      )
    ).toBe("concat(get('previous_action.7.id'),get('previous_action.8.id'))")
  })

  test('a reference to an already saved action is left alone', () => {
    expect(
      rewriteFormulaActionIds("get('previous_action.12.id')", { abc: 7 })
    ).toBe("get('previous_action.12.id')")
  })

  test('a literal that merely contains the id is untouched', () => {
    expect(
      rewriteFormulaActionIds("concat('abc',get('previous_action.abc.id'))", {
        abc: 7,
      })
    ).toBe("concat('abc',get('previous_action.7.id'))")
  })

  test('a formula with no reference comes back unchanged', () => {
    expect(rewriteFormulaActionIds("get('row.field_1')", { abc: 7 })).toBe(
      "get('row.field_1')"
    )
  })

  test('every formula in a payload is rewritten', () => {
    const payload = {
      type: 'local_baserow_create_row',
      service: {
        row_id: { formula: "get('previous_action.abc.id')", mode: 'simple' },
        field_mappings: [
          {
            field_id: 1,
            value: {
              formula: "get('previous_action.abc.Name')",
              mode: 'simple',
            },
          },
        ],
      },
    }

    const rewritten = rewriteActionFormulaIds(payload, { abc: 7 })

    expect(rewritten.service.row_id.formula).toBe("get('previous_action.7.id')")
    expect(rewritten.service.field_mappings[0].value.formula).toBe(
      "get('previous_action.7.Name')"
    )
    // The original is left as it was, so a failed save can be retried.
    expect(payload.service.row_id.formula).toBe("get('previous_action.abc.id')")
  })

  test('an unmapped client id is reported', () => {
    const payload = {
      url: { formula: "get('previous_action.abc.id')", mode: 'simple' },
    }

    expect(unresolvedActionIds(rewriteActionFormulaIds(payload, {}))).toEqual([
      'abc',
    ])
  })

  test('a resolved payload reports nothing', () => {
    const payload = {
      url: { formula: "get('previous_action.7.id')", mode: 'simple' },
    }

    expect(unresolvedActionIds(payload)).toEqual([])
  })
})
