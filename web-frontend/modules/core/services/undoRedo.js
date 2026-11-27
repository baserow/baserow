export default (client) => {
  return {
    undo(scopes, expectedActionGroupId) {
      const url = expectedActionGroupId
        ? `/user/undo/${expectedActionGroupId}/`
        : '/user/undo/'
      return client.patch(url, {
        scopes,
      })
    },
    redo(scopes) {
      return client.patch(`/user/redo/`, {
        scopes,
      })
    },
  }
}
