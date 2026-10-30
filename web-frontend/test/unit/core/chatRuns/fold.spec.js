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

describe('foldRunEvent', () => {
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
