import { buildApprovalPreview } from '@baserow_enterprise/utils/agentApprovalPreview'

describe('buildApprovalPreview', () => {
  test('rows become a table and the other arguments label/value rows', () => {
    const preview = buildApprovalPreview({
      table_id: 5,
      rows: [
        { Name: 'Acme', Stage: 'Seed', order: 1 },
        { Name: 'Globex', Stage: null },
      ],
      thought: '',
    })
    expect(preview.kind).toBe('args')
    expect(preview.fields).toEqual([{ key: 'table_id', value: '5' }])
    expect(preview.table).toEqual({
      columns: ['Name', 'Stage'],
      rows: [
        ['Acme', 'Seed'],
        ['Globex', ''],
      ],
    })
  })

  test('only the first list of objects becomes the table', () => {
    const preview = buildApprovalPreview({
      items: [{ a: 1 }],
      more: [{ b: 2 }],
      tags: ['x', 'y'],
    })
    expect(preview.table.columns).toEqual(['a'])
    expect(preview.fields).toEqual([
      { key: 'more', value: '[{"b":2}]' },
      { key: 'tags', value: '["x","y"]' },
    ])
  })

  test('arguments without anything to show give no preview', () => {
    expect(buildApprovalPreview(null)).toBeNull()
    expect(buildApprovalPreview('text')).toBeNull()
    expect(buildApprovalPreview({})).toBeNull()
    expect(buildApprovalPreview({ note: '' })).toBeNull()
  })
})
