// `replay_events` cursor sentinels. Must match the constants in
// backend/src/baserow/ws/realtime_events.py.
//
// FIRST_CONNECT_CURSOR: first connect of a session, ask for a baseline only.
// NO_REPLAY_AVAILABLE:  reconnect with no usable high-water mark, force refresh.
export const FIRST_CONNECT_CURSOR = -1
export const NO_REPLAY_AVAILABLE = -2

export const REALTIME_RECOVERY_HEADER = 'X-Baserow-Realtime-Recovery'

export const getRealtimeRecoveryRequestConfig = () => ({
  headers: { [REALTIME_RECOVERY_HEADER]: 'true' },
})

/**
 * Runs a realtime marker recovery and retries it once after a short delay.
 * Marker events contain no usable snapshot, so a transient request failure must not
 * leave the client stale until the next provider mutation.
 */
export const retryRealtimeRecovery = async (callback) => {
  try {
    return await callback()
  } catch {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    try {
      return await callback()
    } catch {
      return undefined
    }
  }
}
