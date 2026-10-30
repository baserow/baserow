import { describe, expect, test } from 'vitest'

import {
  foldRunEvent,
  initialRunView,
} from '@baserow/modules/core/chatRuns/fold'

const fold = (events) =>
  events.reduce(
    (view, [kind, data = {}], index) =>
      foldRunEvent(view, { seq: index + 1, kind, data }),
    initialRunView()
  )
const delta = (segment, text) => ['text.delta', { segment, text }]
const message = { id: 5, content: 'Done' }
const step = (id, status = 'running') => ({ id, tool: 'list_tables', status })

describe('foldRunEvent', () => {
  test('updates parallel steps in call order, then replaces them from history', () => {
    const a = step('a', 'done')
    const b = step('b', 'failed')
    const saved = step('saved', 'done')

    expect(
      fold([
        ['step', step('a')],
        ['step', step('b')],
        ['step', b],
        ['step', a],
      ]).steps
    ).toEqual([a, b])
    expect(
      fold([
        ['step', a],
        ['run.baseline', { steps: [b] }],
        ['run.finished', { status: 'completed', message: { steps: [saved] } }],
      ]).steps
    ).toEqual([saved])
  })

  test('clears steps on an empty baseline and ends unresolved calls on finish', () => {
    expect(
      fold([
        ['step', step('a')],
        ['run.baseline', {}],
      ]).steps
    ).toEqual([])
    expect(
      fold([
        ['step', step('a')],
        ['run.finished', { status: 'cancelled' }],
      ]).steps
    ).toEqual([step('a', 'stopped')])
  })

  test.each([
    ['a new run is queued', [['run.created']], { status: 'queued', text: '' }],
    ['a started run is running', [['run.started']], { status: 'running' }],
    [
      'the deltas of a segment add up',
      [delta(0, 'Hel'), delta(0, 'lo')],
      { segment: 0, text: 'Hello' },
    ],
    [
      'a new segment starts over',
      [delta(0, 'Hel'), delta(1, 'Bye')],
      { segment: 1, text: 'Bye' },
    ],
    [
      'progress keeps the latest text',
      [
        ['progress', { text: 'Listing tables' }],
        ['progress', { text: 'Creating rows' }],
      ],
      { progress: 'Creating rows' },
    ],
    [
      'a stop request is remembered',
      [['run.cancel_requested']],
      { cancelRequested: true },
    ],
    [
      'the final event keeps how the run ended and its saved message',
      [['run.finished', { status: 'failed', error_code: 'timeout', message }]],
      { status: 'failed', errorCode: 'timeout', message },
    ],
    [
      'a baseline replaces the output',
      [
        delta(0, 'Hel'),
        [
          'run.baseline',
          { segment: 0, text: 'Hello', progress: { text: 'Reading' } },
        ],
      ],
      { segment: 0, text: 'Hello', progress: 'Reading' },
    ],
    [
      'an empty baseline clears the output',
      [
        delta(0, 'Hel'),
        ['progress', { text: 'Reading' }],
        ['run.baseline', { segment: null, text: '', progress: null }],
      ],
      { segment: -1, text: '', progress: '' },
    ],
  ])('%s', (_, events, expected) => {
    expect(fold(events)).toMatchObject(expected)
  })

  test('an unknown kind leaves the view as it is', () => {
    const view = initialRunView()

    expect(foldRunEvent(view, { seq: 1, kind: 'future.kind', data: {} })).toBe(
      view
    )
  })
})
