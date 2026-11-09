const ROUTE_PARAM_KEY_RE = /^(?:params|url\.path\.parameter)\./

const withoutRouteParams = (data) =>
  data &&
  Object.fromEntries(
    Object.entries(data).filter(([key]) => !ROUTE_PARAM_KEY_RE.test(key))
  )

export const dropRouteParams = (event) => {
  const trace = event.contexts?.trace
  if (trace?.data) {
    trace.data = withoutRouteParams(trace.data)
  }
  event.spans?.forEach((span) => {
    if (span.data) {
      span.data = withoutRouteParams(span.data)
    }
  })
  return event
}
