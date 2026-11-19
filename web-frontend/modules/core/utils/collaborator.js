import { collatedStringCompare } from '@baserow/modules/core/utils/string'

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
  const user = store.getters['workspace/getCollaboratorById'](
    collaboratorValue.id
  )
  if (user) {
    return user.name
  }

  // Fallback if for some reason the user is missing from the store
  return collaboratorValue.name
}

/**
 * Returns the collaborators that can be picked: identities only when the field,
 * or the place they are picked in, includes them.
 */
export function getSelectableCollaborators(collaborators, includeIdentities) {
  return includeIdentities
    ? collaborators
    : collaborators.filter(
        (collaborator) => collaborator.user_type !== 'identity'
      )
}

/**
 * Returns the collaborators a field offers, sorted by name: the live members of a
 * loaded workspace, otherwise the field's own list, as in a public view.
 */
export function getFieldCollaborators(store, field, workspaceId) {
  const workspace = store.getters['workspace/get'](workspaceId)
  if (!workspace) {
    return field.available_collaborators || []
  }
  // Fields without the option, like created by, can always hold identities.
  return getSelectableCollaborators(
    store.getters['workspace/getCollaborators'](workspace.id),
    field.include_identities ?? true
  )
    .filter((collaborator) => !collaborator.to_be_deleted)
    .map((collaborator) => ({
      id: collaborator.user_id,
      name: collaborator.name,
      email: collaborator.email,
      user_type: collaborator.user_type || 'human',
    }))
    .sort((a, b) => collatedStringCompare(a.name, b.name, 'ASC'))
}
