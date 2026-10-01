import { buildTriggerPreview } from '@baserow_enterprise/utils/agentTriggerPreview'

const helpers = {
  t: (key) => key,
  formatDate: (value) => (value ? `date:${value}` : ''),
  tableLabel: (id) => `table:${id}`,
  rowLabel: (tableId, rowId) => `row:${rowId}`,
}

describe('buildTriggerPreview', () => {
  test('a row comment becomes a quote with row, table, time and mentions', () => {
    const preview = buildTriggerPreview(
      'row_comment_created',
      {
        table_id: 12,
        row_id: 7,
        message: '@Investor reach out',
        user: { id: 1, name: 'Bram' },
        mentions: [{ id: 3, name: 'Investor' }],
        created_on: '2026-10-01T09:41:00Z',
      },
      helpers
    )
    expect(preview.quote).toEqual({
      author: 'Bram',
      text: '@Investor reach out',
      at: 'date:2026-10-01T09:41:00Z',
    })
    expect(preview.fields.map((field) => [field.key, field.value])).toEqual([
      ['agentChatTrigger.row', 'row:7'],
      ['agentChatTrigger.table', 'table:12'],
      ['agentChatTrigger.posted', 'date:2026-10-01T09:41:00Z'],
      ['agentChatTrigger.mentioned', 'Investor'],
    ])
  })

  test('row events become a table without the order column', () => {
    const preview = buildTriggerPreview(
      'local_baserow_rows_created',
      {
        results: [
          { id: 1, order: '1.0', Name: 'Acme' },
          { id: 2, Name: null },
        ],
      },
      helpers
    )
    expect(preview.table).toEqual({
      columns: ['id', 'Name'],
      rows: [
        ['1', 'Acme'],
        ['2', ''],
      ],
    })
  })

  test('schedules, webhooks and emails list their own fields', () => {
    expect(
      buildTriggerPreview(
        'periodic',
        { triggered_at: 'a', next_run_at: 'b' },
        helpers
      ).fields.map((field) => field.value)
    ).toEqual(['date:a', 'date:b'])
    expect(
      buildTriggerPreview(
        'http_trigger',
        { method: 'POST', body: { x: 1 }, headers: {}, query_params: {} },
        helpers
      ).fields.map((field) => field.value)
    ).toEqual(['POST', '{}', '{}', '{"x":1}'])
    const email = buildTriggerPreview(
      'email_trigger',
      {
        from: { name: 'Ada', address: 'ada@example.com' },
        to: [{ address: 'agent@example.com' }],
        subject: 'Hello',
        body_text: 'Hi there',
      },
      helpers
    )
    expect(email.fields.map((field) => field.value)).toEqual([
      'Ada <ada@example.com>',
      'agent@example.com',
      'Hello',
    ])
    expect(email.body).toBe('Hi there')
  })

  test('unknown payloads fall back to their top-level keys', () => {
    expect(
      buildTriggerPreview('bogus', { a: 1, b: 'x' }, helpers).fields
    ).toEqual([
      { key: 'a', value: '1' },
      { key: 'b', value: 'x' },
    ])
    expect(buildTriggerPreview('periodic', null, helpers)).toBeNull()
  })
})
