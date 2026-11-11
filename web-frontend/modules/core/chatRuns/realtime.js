import {
  CHAT_RUN_CHANGED_MESSAGE,
  CHAT_RUNS_PAGE,
} from '@baserow/modules/core/chatRuns/constants'

/** Announce identity/status only; websocket messages never contain run output. */
export function registerChatRunRealtimeEvents(realtime) {
  realtime.registerEvent(
    CHAT_RUN_CHANGED_MESSAGE,
    ({ store }, { run_id: runId, run_type: runType, chat_id: chatId }) =>
      store.dispatch('chatRuns/handleChanged', { runId, runType, chatId })
  )
  realtime.registerEvent('page_add', ({ store }, { page, parameters }) => {
    if (page === CHAT_RUNS_PAGE)
      store.dispatch('chatRuns/handlePageAdd', parameters)
  })
}
