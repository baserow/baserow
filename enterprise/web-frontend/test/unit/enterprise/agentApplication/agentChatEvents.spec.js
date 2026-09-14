import {
  groupChatEvents,
  humanizeToolName,
  summarizeToolArgs,
  formatToolPayload,
} from '@baserow_enterprise/utils/agentChatEvents'

const tool = (id, result = { status: 'ok', content: 'done' }) => ({
  type: 'tool_call',
  id,
  tool_name: 'list_rows',
  args: { table_id: 1 },
  result,
})

describe('groupChatEvents', () => {
  test('groups consecutive tool calls with folded reasoning', () => {
    const events = [
      { type: 'human', id: 1, content: 'Hi' },
      tool('a'),
      { type: 'ai/reasoning', content: 'thinking' },
      tool('b'),
      { type: 'ai/message', content: 'Done' },
    ]
    const blocks = groupChatEvents(events, { running: false })
    expect(blocks.map((block) => block.type)).toEqual([
      'message',
      'tool_group',
      'message',
    ])
    const group = blocks[1]
    expect(group.key).toBe('tools-a')
    expect(group.steps.map((step) => step.kind)).toEqual([
      'tool',
      'reasoning',
      'tool',
    ])
    expect(group.toolCount).toBe(2)
    expect(group.live).toBe(false)
    expect(group.hasError).toBe(false)
  })

  test('trailing reasoning after the last tool call is its own block', () => {
    const events = [tool('a'), { type: 'ai/reasoning', content: 'thinking' }]
    const blocks = groupChatEvents(events, { running: true })
    expect(blocks.map((block) => block.type)).toEqual([
      'tool_group',
      'reasoning',
    ])
    expect(blocks[1].live).toBe(true)
  })

  test('a live group and errors are flagged', () => {
    const events = [
      tool('a', { status: 'error', content: 'boom' }),
      tool('b', null),
    ]
    const [group] = groupChatEvents(events, { running: true })
    expect(group.live).toBe(true)
    expect(group.hasError).toBe(true)
    expect(groupChatEvents(events, { running: false })[0].live).toBe(false)
  })

  test('the last group stays live between calls until the answer starts', () => {
    const finished = [tool('a'), tool('b')]
    expect(groupChatEvents(finished, { running: true })[0].live).toBe(true)
    const answering = [...finished, { type: 'ai/message', content: 'Done' }]
    expect(groupChatEvents(answering, { running: true })[0].live).toBe(false)
    const thinking = [...finished, { type: 'ai/reasoning', content: 'next' }]
    expect(groupChatEvents(thinking, { running: true })[0].live).toBe(true)
  })

  test('approval sets split groups', () => {
    const events = [tool('a'), { type: 'approval_set', ids: [1, 2] }, tool('b')]
    const blocks = groupChatEvents(events)
    expect(blocks.map((block) => block.type)).toEqual([
      'tool_group',
      'approval_set',
      'tool_group',
    ])
    expect(blocks[1].key).toBe('approvals-1-2')
    expect(blocks[1].ids).toEqual([1, 2])
  })

  test('the opening system message of a triggered chat is a trigger row', () => {
    const events = [
      { type: 'system', id: 1, content: 'Trigger: rows created' },
      { type: 'system', id: 2, content: 'note' },
    ]
    expect(
      groupChatEvents(events, { chatSource: 'trigger' }).map((b) => b.type)
    ).toEqual(['trigger', 'system'])
    expect(
      groupChatEvents(events, { chatSource: 'manual' }).map((b) => b.type)
    ).toEqual(['system', 'system'])
  })
})

describe('helpers', () => {
  test('humanizeToolName', () => {
    expect(humanizeToolName('create_view_filters')).toBe('Create view filters')
    expect(humanizeToolName('')).toBe('')
  })

  test('summarizeToolArgs truncates values and pairs', () => {
    expect(summarizeToolArgs({ table_id: 12, name: 'Leads' })).toBe(
      'table_id: 12 · name: Leads'
    )
    expect(summarizeToolArgs({ a: 1, b: 2, c: 3, d: 4 }, { maxPairs: 2 })).toBe(
      'a: 1 · b: 2 · …'
    )
    expect(
      summarizeToolArgs({ text: 'x'.repeat(50) }, { maxValueLength: 10 })
    ).toBe(`text: ${'x'.repeat(9)}…`)
    expect(summarizeToolArgs({ rows: [{ id: 1 }], none: null })).toBe(
      'rows: [{"id":1}] · none: —'
    )
    expect(
      summarizeToolArgs({ thought: ' Adding the test row ', rows: [{}] })
    ).toBe('Adding the test row')
    expect(summarizeToolArgs(null)).toBe('')
    expect(summarizeToolArgs('raw string')).toBe('raw string')
  })

  test('formatToolPayload pretty prints JSON', () => {
    expect(formatToolPayload({ a: 1 })).toBe('{\n  "a": 1\n}')
    expect(formatToolPayload('{"a":1}')).toBe('{\n  "a": 1\n}')
    expect(formatToolPayload('plain')).toBe('plain')
    expect(formatToolPayload(null)).toBe('')
  })
})
