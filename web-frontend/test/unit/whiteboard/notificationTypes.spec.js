import { describe, expect, test } from 'vitest'
import {
  WhiteboardCommentMentionNotificationType,
  WhiteboardCommentReplyNotificationType,
} from '@baserow/modules/whiteboard/notificationTypes'

describe('whiteboard comment notification types', () => {
  test('mention type id', () => {
    expect(WhiteboardCommentMentionNotificationType.getType()).toBe(
      'whiteboard_comment_mention'
    )
  })

  test('reply type id', () => {
    expect(WhiteboardCommentReplyNotificationType.getType()).toBe(
      'whiteboard_comment_reply'
    )
  })

  test('both types route to the right whiteboard with the comment query', () => {
    const data = { whiteboard_id: 7, comment_id: 42 }
    const expected = {
      name: 'whiteboard-application',
      params: { whiteboardId: 7 },
      query: { comment: 42 },
    }
    const t1 = new WhiteboardCommentMentionNotificationType({ app: {} })
    const t2 = new WhiteboardCommentReplyNotificationType({ app: {} })
    expect(t1.getRoute(data)).toEqual(expected)
    expect(t2.getRoute(data)).toEqual(expected)
  })
})
