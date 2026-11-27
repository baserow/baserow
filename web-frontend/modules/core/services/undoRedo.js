export default (client) => {
  return {
    undoGroup(groupId) {
      return client.patch(`/user/undo/${groupId}/`)
    },
    undo(scopes) {
      return client.patch('/user/undo/', {
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
