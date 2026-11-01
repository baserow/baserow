import {
  PROGRESS,
  RUN_BASELINE,
  RUN_CANCEL_REQUESTED,
  RUN_FINISHED,
  RUN_STARTED,
  RUN_STATUS,
  TEXT_DELTA,
} from '@baserow/modules/core/chatRuns/constants'

/**
 * The view every run starts from, whatever its type: its status, whether a
 * stop was asked for, the text of its latest segment, its latest progress and,
 * once it ended, how and with which saved message.
 *
 * @returns {object} A new view.
 */
export function initialRunView() {
  return {
    status: RUN_STATUS.QUEUED,
    errorCode: '',
    cancelRequested: false,
    segment: -1,
    text: '',
    progress: '',
    message: null,
  }
}

/**
 * Applies one event to a run's view without side effects, so catching up on
 * saved events and following them live give the same view. Unknown kinds
 * leave the view as it is, so a tab keeps working while a deploy adds kinds.
 *
 * @param {object} view The view before the event.
 * @param {{kind: string, data: object}} event The event.
 * @returns {object} The view after the event.
 */
export function foldRunEvent(view, event) {
  const { data } = event
  switch (event.kind) {
    case RUN_STARTED:
      return { ...view, status: RUN_STATUS.RUNNING }
    case TEXT_DELTA:
      return data.segment === view.segment
        ? { ...view, text: view.text + data.text }
        : { ...view, segment: data.segment, text: data.text }
    case PROGRESS:
      return { ...view, progress: data.text }
    case RUN_CANCEL_REQUESTED:
      return { ...view, cancelRequested: true }
    case RUN_FINISHED:
      return {
        ...view,
        status: data.status,
        errorCode: data.error_code || '',
        message: data.message ?? null,
        text: data.message?.content ?? view.text,
        progress: '',
      }
    case RUN_BASELINE:
      return {
        ...view,
        segment: data.segment ?? -1,
        text: data.text || '',
        progress: data.progress?.text || '',
      }
    default:
      return view
  }
}
