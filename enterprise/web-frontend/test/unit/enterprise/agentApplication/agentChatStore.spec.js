import { expect } from 'vitest'
import MockAdapter from 'axios-mock-adapter'

describe('agentChat store', () => {
  let store = null
  let mock = null

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    store.dispatch('agentChat/newConversation')
  })

  afterEach(() => {
    mock.restore()
  })

  test('openConversation maps messages to events and stores the source', async () => {
    mock.onGet('agent_application/42/chats/uuid-9/messages/').replyOnce(200, {
      chat: { id: 9, uuid: 'uuid-9', status: 'idle', source: 'trigger' },
      messages: [
        { id: 1, role: 'human', content: 'Hello', artifacts: null },
        {
          id: 2,
          role: 'ai',
          content: 'Done',
          artifacts: {
            events: [
              { type: 'ai/reasoning', content: 'Thinking about it' },
              {
                type: 'tool_call',
                id: 'call-1',
                tool_name: 'list_rows',
                args: { table_id: 1 },
                result: { status: 'ok', content: '3 rows' },
              },
            ],
          },
        },
      ],
    })

    await store.dispatch('agentChat/openConversation', {
      applicationId: 42,
      chatUuid: 'uuid-9',
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'human', id: 1, content: 'Hello' },
      { type: 'ai/reasoning', content: 'Thinking about it' },
      {
        type: 'tool_call',
        id: 'call-1',
        tool_name: 'list_rows',
        args: { table_id: 1 },
        result: { status: 'ok', content: '3 rows' },
      },
      { type: 'ai/message', content: 'Done' },
    ])
    expect(store.getters['agentChat/getChatId']).toBe(9)
    expect(store.getters['agentChat/getSource']).toBe('trigger')
    expect(store.getters['agentChat/isRunning']).toBe(false)
  })

  test('sendMessage adds an optimistic human event and sets running', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']

    mock
      .onPost(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(202, {
        id: 7,
        uuid: chatUuid,
        title: '',
        status: 'in_progress',
        source: 'manual',
        updated_on: '2026-08-27T10:00:00Z',
        prompt_message_id: 100,
      })

    await store.dispatch('agentChat/sendMessage', {
      application: { id: 42 },
      content: 'Hello agent',
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([{ type: 'human', content: 'Hello agent', id: 100 }])
    expect(store.getters['agentChat/getChatId']).toBe(7)
    expect(store.getters['agentChat/isRunning']).toBe(true)

    // The websocket echo of the sender's own message must be skipped, while
    // another user's message must be appended.
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'human', id: 100, content: 'Hello agent' },
    })
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'human', id: 101, content: 'From another user' },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'human', content: 'Hello agent', id: 100 },
      { type: 'human', id: 101, content: 'From another user' },
    ])
  })

  test('handleChatDeleted resets the open conversation', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    const previousUuid = store.getters['agentChat/getCurrentChatUuid']

    // Another chat being deleted does nothing.
    await store.dispatch('agentChat/handleChatDeleted', { chatId: 8 })
    expect(store.getters['agentChat/getChatId']).toBe(7)

    await store.dispatch('agentChat/handleChatDeleted', { chatId: 7 })
    expect(store.getters['agentChat/getChatId']).toBe(null)
    expect(store.getters['agentChat/getEvents']).toStrictEqual([])
    expect(store.getters['agentChat/getCurrentChatUuid']).not.toBe(previousUuid)
  })

  test('sendMessage removes the optimistic event when the request fails', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']

    mock
      .onPost(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(400, { error: 'ERROR_INVALID' })

    await expect(
      store.dispatch('agentChat/sendMessage', {
        application: { id: 42 },
        content: 'Hello agent',
      })
    ).rejects.toThrow()

    expect(store.getters['agentChat/getEvents']).toStrictEqual([])
  })

  test('handleRealtimeEvent appends a tool_call and merges the tool result', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: {
        type: 'tool_call',
        id: 'call-1',
        tool_name: 'list_rows',
        args: { table_id: 1 },
      },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      {
        type: 'tool_call',
        id: 'call-1',
        tool_name: 'list_rows',
        args: { table_id: 1 },
        result: null,
      },
    ])

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: {
        type: 'tool',
        id: 'call-1',
        tool_name: 'list_rows',
        status: 'ok',
        content: '3 rows found',
      },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      {
        type: 'tool_call',
        id: 'call-1',
        tool_name: 'list_rows',
        args: { table_id: 1 },
        result: { status: 'ok', content: '3 rows found' },
      },
    ])
  })

  test('handleRealtimeEvent finalizes the answer on ai/message', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_RUNNING', true)

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: {
        type: 'ai/message',
        content: 'The final answer',
        sources: [],
      },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'ai/message', content: 'The final answer', sources: [] },
    ])
    expect(store.getters['agentChat/isRunning']).toBe(false)
  })

  test('events racing the send response are buffered and applied once the chat id is known', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']

    mock
      .onPost(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(202, {
        id: 7,
        uuid: chatUuid,
        status: 'in_progress',
        source: 'manual',
        updated_on: '2026-08-27T10:00:00Z',
      })

    // Don't await, so the realtime events race the POST response.
    const sendPromise = store.dispatch('agentChat/sendMessage', {
      application: { id: 42 },
      content: 'Hello agent',
    })

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/reasoning', content: 'Early chunk' },
    })
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 99,
      event: { type: 'ai/reasoning', content: 'Another chat' },
    })

    await sendPromise

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'human', content: 'Hello agent' },
      { type: 'ai/reasoning', content: 'Early chunk' },
    ])
  })

  test('answer chunks stream into a partial message finalized by ai/message', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/answer_chunk', content: 'The ans' },
    })
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/answer_chunk', content: 'The answer' },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'ai/message', content: 'The answer', partial: true },
    ])

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/message', content: 'The answer.', sources: [] },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      {
        type: 'ai/message',
        content: 'The answer.',
        sources: [],
        partial: false,
      },
    ])
    expect(store.getters['agentChat/isRunning']).toBe(false)
  })

  test('own echo racing the send response in an existing chat is not duplicated', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']
    // An existing conversation already has a chat id before sending.
    store.commit('agentChat/SET_CHAT_ID', 7)

    mock
      .onPost(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(202, {
        id: 7,
        uuid: chatUuid,
        status: 'in_progress',
        source: 'manual',
        updated_on: '2026-08-27T10:00:00Z',
        prompt_message_id: 100,
      })

    // Don't await: the websocket echo of the sender's own message arrives
    // before the POST response tags the optimistic event with its id.
    const sendPromise = store.dispatch('agentChat/sendMessage', {
      application: { id: 42 },
      content: 'Second message',
    })

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'human', id: 100, content: 'Second message' },
    })

    await sendPromise

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([{ type: 'human', content: 'Second message', id: 100 }])
  })

  test('handleChatUpdated refetches the transcript on a missed terminal status', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_APPLICATION_ID', 42)
    store.commit('agentChat/SET_RUNNING', true)

    mock
      .onGet(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(200, {
        chat: { id: 7, uuid: chatUuid, status: 'idle', source: 'manual' },
        messages: [
          { id: 1, role: 'human', content: 'Hello', artifacts: null },
          { id: 2, role: 'ai', content: 'Missed answer', artifacts: null },
        ],
      })

    await store.dispatch('agentChat/handleChatUpdated', {
      chat: { id: 7, status: 'idle' },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'human', id: 1, content: 'Hello' },
      { type: 'ai/message', content: 'Missed answer' },
    ])
    expect(store.getters['agentChat/isRunning']).toBe(false)

    // A late final event with the same content must not duplicate the answer.
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/message', content: 'Missed answer', sources: [] },
    })
    expect(store.getters['agentChat/getEvents'].length).toBe(2)
  })

  test('openConversation populates tool approvals and places a card after the AI message', async () => {
    mock.onGet('agent_application/42/chats/uuid-9/messages/').replyOnce(200, {
      chat: {
        id: 9,
        uuid: 'uuid-9',
        status: 'awaiting_approval',
        source: 'manual',
      },
      messages: [
        { id: 1, role: 'human', content: 'Delete it', artifacts: null },
        { id: 2, role: 'ai', content: '', artifacts: null },
      ],
      tool_approvals: [
        {
          id: 5,
          chat_id: 9,
          message_id: 2,
          tool_call_id: 'call-1',
          tool_name: 'delete_row',
          tool_args: { row_id: 1 },
          status: 'pending',
          reason: '',
        },
      ],
    })

    await store.dispatch('agentChat/openConversation', {
      applicationId: 42,
      chatUuid: 'uuid-9',
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      { type: 'human', id: 1, content: 'Delete it' },
      { type: 'approval_set', ids: [5] },
    ])
    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getToolApprovals']))
    ).toStrictEqual([
      {
        id: 5,
        chat_id: 9,
        message_id: 2,
        tool_call_id: 'call-1',
        tool_name: 'delete_row',
        tool_args: { row_id: 1 },
        status: 'pending',
        reason: '',
      },
    ])
    expect(store.getters['agentChat/isAwaitingApproval']).toBe(true)
    expect(store.getters['agentChat/isRunning']).toBe(false)
  })

  test('an approval_request event adds the approvals and pauses the run', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_RUNNING', true)

    const approvals = [
      {
        id: 1,
        tool_call_id: 'call-1',
        tool_name: 'update_row',
        tool_args: { row_id: 1 },
        status: 'pending',
      },
      {
        id: 2,
        tool_call_id: 'call-2',
        tool_name: 'delete_row',
        tool_args: { row_id: 2 },
        status: 'pending',
      },
    ]
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'approval_request', approvals },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([{ type: 'approval_set', ids: [1, 2] }])
    expect(store.getters['agentChat/getPendingToolApprovals'].length).toBe(2)
    expect(store.getters['agentChat/isAwaitingApproval']).toBe(true)
    expect(store.getters['agentChat/isRunning']).toBe(false)

    // A duplicate of the event (e.g. after an `agent_chat_updated` refetch
    // already placed the card) must not add a second card.
    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'approval_request', approvals },
    })
    expect(store.getters['agentChat/getEvents'].length).toBe(1)
    expect(store.getters['agentChat/getToolApprovals'].length).toBe(2)
  })

  test('an approval_decided event updates the approval in place', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_TOOL_APPROVALS', [
      {
        id: 1,
        tool_call_id: 'call-1',
        tool_name: 'update_row',
        tool_args: {},
        status: 'pending',
        reason: '',
      },
    ])

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: {
        type: 'approval_decided',
        id: 1,
        status: 'rejected',
        reason: 'Wrong row',
      },
    })

    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getToolApprovals']))
    ).toStrictEqual([
      {
        id: 1,
        tool_call_id: 'call-1',
        tool_name: 'update_row',
        tool_args: {},
        status: 'rejected',
        reason: 'Wrong row',
      },
    ])
    expect(store.getters['agentChat/getPendingToolApprovals']).toStrictEqual([])
  })

  test('ai/started after the approvals were decided resumes the run', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_AWAITING_APPROVAL', true)

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 7,
      event: { type: 'ai/started', message_id: 5 },
    })

    expect(store.getters['agentChat/isAwaitingApproval']).toBe(false)
    expect(store.getters['agentChat/isRunning']).toBe(true)
  })

  test('decideApprovals posts the decisions and applies the response', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_TOOL_APPROVALS', [
      {
        id: 1,
        tool_call_id: 'call-1',
        tool_name: 'update_row',
        tool_args: {},
        status: 'pending',
        reason: '',
      },
    ])

    mock
      .onPost(`agent_application/chats/${chatUuid}/approvals/`)
      .replyOnce(200, [
        {
          id: 1,
          tool_call_id: 'call-1',
          tool_name: 'update_row',
          tool_args: {},
          status: 'approved',
          reason: '',
        },
      ])

    await store.dispatch('agentChat/decideApprovals', {
      decisions: [{ id: 1, approved: true }],
    })

    expect(JSON.parse(mock.history.post[0].data)).toStrictEqual({
      decisions: [{ id: 1, approved: true }],
    })
    expect(store.getters['agentChat/getToolApprovals'][0].status).toBe(
      'approved'
    )
  })

  test('handleChatUpdated refetches when a missed pause is detected', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_APPLICATION_ID', 42)

    mock
      .onGet(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(200, {
        chat: {
          id: 7,
          uuid: chatUuid,
          status: 'awaiting_approval',
          source: 'manual',
        },
        messages: [{ id: 2, role: 'ai', content: '', artifacts: null }],
        tool_approvals: [
          {
            id: 5,
            chat_id: 7,
            message_id: 2,
            tool_call_id: 'call-1',
            tool_name: 'delete_row',
            tool_args: {},
            status: 'pending',
            reason: '',
          },
        ],
      })

    await store.dispatch('agentChat/handleChatUpdated', {
      chat: { id: 7, status: 'awaiting_approval' },
    })

    expect(store.getters['agentChat/isAwaitingApproval']).toBe(true)
    expect(store.getters['agentChat/getToolApprovals'].length).toBe(1)
    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([{ type: 'approval_set', ids: [5] }])
  })

  test('sendMessage sends the attached user files and renders them optimistically', async () => {
    const chatUuid = store.getters['agentChat/getCurrentChatUuid']
    const userFile = {
      name: 'abc123.txt',
      original_name: 'notes.txt',
      size: 10,
      mime_type: 'text/plain',
      is_image: false,
    }

    mock
      .onPost(`agent_application/42/chats/${chatUuid}/messages/`)
      .replyOnce(202, {
        id: 7,
        uuid: chatUuid,
        status: 'in_progress',
        source: 'manual',
        updated_on: '2026-08-27T10:00:00Z',
        prompt_message_id: 100,
      })

    await store.dispatch('agentChat/sendMessage', {
      application: { id: 42 },
      content: 'See the attached file',
      userFiles: [userFile],
    })

    expect(JSON.parse(mock.history.post[0].data)).toStrictEqual({
      content: 'See the attached file',
      user_files: [{ name: 'abc123.txt' }],
    })
    expect(
      JSON.parse(JSON.stringify(store.getters['agentChat/getEvents']))
    ).toStrictEqual([
      {
        type: 'human',
        id: 100,
        content: 'See the attached file',
        attachments: [userFile],
      },
    ])
  })

  test('handleRealtimeEvent ignores events for another chat', async () => {
    store.commit('agentChat/SET_CHAT_ID', 7)
    store.commit('agentChat/SET_RUNNING', true)

    await store.dispatch('agentChat/handleRealtimeEvent', {
      chatId: 8,
      event: {
        type: 'ai/message',
        content: 'A different conversation',
        sources: [],
      },
    })

    expect(store.getters['agentChat/getEvents']).toStrictEqual([])
    expect(store.getters['agentChat/isRunning']).toBe(true)
  })
})
