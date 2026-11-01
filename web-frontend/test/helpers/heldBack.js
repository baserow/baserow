/**
 * A mock server reply that is sent only when the test calls `send`, with the
 * `[status, data]` the reply would return.
 */
export const heldBack = () => {
  let send = null
  const reply = () =>
    new Promise((resolve) => {
      send = resolve
    })
  return { reply, send: (value) => send(value) }
}
