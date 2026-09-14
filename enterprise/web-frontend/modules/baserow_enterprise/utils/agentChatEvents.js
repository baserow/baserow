/**
 * Pure helpers turning the flat chat event list of the `agentChat` store into
 * the blocks the conversation renders: trigger rows, messages, reasoning,
 * grouped tool calls and approval cards.
 */

const MESSAGE_TYPES = ['human', 'ai/message', 'ai/error', 'ai/cancelled']

export function humanizeToolName(name) {
  const text = String(name || '')
    .replace(/_/g, ' ')
    .trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function eventKey(event, index, prefix) {
  return event.id !== undefined ? `${prefix}-${event.id}` : `${prefix}-${index}`
}

/**
 * Groups the events. Consecutive tool calls become one `tool_group` block
 * (finished reasoning between two tool calls is folded in as a step); the
 * first system message of a trigger-started conversation becomes the
 * `trigger` block; a reasoning event that is still streaming is never folded
 * so it can be rendered live.
 */
export function groupChatEvents(events, { running = false, chatSource } = {}) {
  const blocks = []
  const lastIndex = events.length - 1
  let group = null

  const closeGroup = () => {
    if (group === null) {
      return
    }
    // Reasoning after the last tool call belongs to the answer, not the
    // group.
    while (group.steps.length > 0 && group.steps.at(-1).kind !== 'tool') {
      const step = group.steps.pop()
      blocks.push({ type: 'reasoning', key: step.key, event: step.event })
    }
    group.toolCount = group.steps.filter((step) => step.kind === 'tool').length
    group.live = false
    group.hasError = group.steps.some(
      (step) => step.kind === 'tool' && step.event.result?.status === 'error'
    )
    blocks.push(group)
    group = null
  }

  events.forEach((event, index) => {
    const isLive = running && index === lastIndex
    if (event.type === 'tool_call') {
      if (group === null) {
        group = {
          type: 'tool_group',
          key: eventKey(event, index, 'tools'),
          steps: [],
        }
      }
      group.steps.push({
        kind: 'tool',
        key: eventKey(event, index, 'tool'),
        event,
      })
      return
    }
    if (event.type === 'ai/reasoning') {
      const key = eventKey(event, index, 'reasoning')
      if (group !== null && !isLive) {
        group.steps.push({ kind: 'reasoning', key, event })
      } else {
        closeGroup()
        blocks.push({ type: 'reasoning', key, event, live: isLive })
      }
      return
    }
    closeGroup()
    if (event.type === 'system') {
      if (chatSource === 'trigger' && index === 0) {
        blocks.push({
          type: 'trigger',
          key: eventKey(event, index, 'trigger'),
          event,
        })
      } else {
        blocks.push({
          type: 'system',
          key: eventKey(event, index, 'system'),
          event,
        })
      }
    } else if (event.type === 'approval_set') {
      blocks.push({
        type: 'approval_set',
        key: `approvals-${event.ids.join('-')}`,
        ids: event.ids,
      })
    } else if (MESSAGE_TYPES.includes(event.type)) {
      blocks.push({
        type: 'message',
        key: eventKey(event, index, 'message'),
        event,
      })
    }
  })
  closeGroup()
  // While the run is in progress, the agent is still "working on" the last
  // group of tool calls until it starts answering (a message after it), even
  // between two calls when no call is pending.
  if (running) {
    const last = blocks.at(-1)
    const beforeLast = blocks.at(-2)
    if (last?.type === 'tool_group') {
      last.live = true
    } else if (
      last?.type === 'reasoning' &&
      last.live &&
      beforeLast?.type === 'tool_group'
    ) {
      beforeLast.live = true
    }
  }
  return blocks
}

function stringifyValue(value, maxValueLength) {
  let text
  if (value === null || value === undefined) {
    text = '—'
  } else if (typeof value === 'object') {
    text = JSON.stringify(value)
  } else {
    text = String(value)
  }
  return text.length > maxValueLength
    ? `${text.slice(0, maxValueLength - 1)}…`
    : text
}

/**
 * A one-line summary of tool arguments. The assistant tools carry the
 * model's intent in a `thought` argument, which reads far better than the
 * raw values, so it wins; otherwise "table_id: 12 · name: Leads".
 */
export function summarizeToolArgs(
  args,
  { maxPairs = 3, maxValueLength = 40 } = {}
) {
  if (args === null || args === undefined) {
    return ''
  }
  if (typeof args !== 'object' || Array.isArray(args)) {
    return stringifyValue(args, maxValueLength * maxPairs)
  }
  if (typeof args.thought === 'string' && args.thought.trim() !== '') {
    return args.thought.trim()
  }
  const entries = Object.entries(args)
  const parts = entries
    .slice(0, maxPairs)
    .map(([key, value]) => `${key}: ${stringifyValue(value, maxValueLength)}`)
  if (entries.length > maxPairs) {
    parts.push('…')
  }
  return parts.join(' · ')
}

/**
 * Pretty JSON for objects and JSON strings, the raw text otherwise.
 */
export function formatToolPayload(value) {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }
  return JSON.stringify(value, null, 2)
}
