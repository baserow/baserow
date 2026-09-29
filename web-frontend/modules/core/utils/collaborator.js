/**
 * Returns the display name of a collaborator value, preferring the name in the
 * workspace store so a rename shows without a reload.
 */
export function getCollaboratorName(collaboratorValue, store) {
  // Workaround for field conversion not to produce console errors
  if (
    !collaboratorValue ||
    typeof collaboratorValue !== 'object' ||
    (!collaboratorValue.id && !collaboratorValue.name)
  ) {
    return ''
  }

  // If workspaces are unavailable, public views are served
  const workspaces = store.getters['workspace/getAll']
  if (workspaces.length === 0) {
    return collaboratorValue.name
  }

  // Otherwise, get name from the store to reflect real-time updates
  const user = store.getters['workspace/getUserById'](collaboratorValue.id)
  if (user) {
    return user.name
  }

  // Fallback if for some reason the user is missing from the store
  return collaboratorValue.name
}
