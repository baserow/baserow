export const isDashboardRequestCurrent = (state, request) =>
  state.dashboardId === request.dashboardId &&
  state.dashboardGeneration === request.dashboardGeneration

export const isFetchRequestCurrent = (state, request, generationKey) =>
  isDashboardRequestCurrent(state, request) &&
  state[generationKey] === request.generation

/**
 * Superseded collection readers share the newest result, including its failure.
 * Each collection owns a tracker; promises stay outside serializable store state.
 * The fetch callback must check isLatest before applying its response.
 */
export function createLatestCollectionFetch() {
  const requests = new WeakMap()
  return (state, { isCurrent, isLatest, fetch }) => {
    const request = {}
    request.promise = (async () => {
      let result
      try {
        result = await fetch()
      } catch (error) {
        if (isCurrent() && isLatest()) throw error
      }
      if (!isCurrent()) return
      if (isLatest()) return result
      const latest = requests.get(state)
      if (latest !== request) return latest.promise
    })()
    requests.set(state, request)
    return request.promise
  }
}
