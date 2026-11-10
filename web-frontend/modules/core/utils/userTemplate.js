/**
 * Whether the template is one of the user's own templates, as told by the server.
 */
export function isOwnTemplate(template) {
  return template.is_own === true
}

export function canMakePublic(template) {
  return Boolean(template?.can_make_public)
}

export function makePublicResubmits(template) {
  return (
    canMakePublic(template) &&
    Boolean(template?.make_public_needs_review) &&
    Boolean(template?.listed)
  )
}

export function canMakePrivate(template) {
  if (template?.state === 'rejected') {
    return Boolean(template.listed)
  }
  return ['public', 'in_review'].includes(template?.state)
}

export function canChangeVisibilityInDetails(template) {
  return ['private', 'public'].includes(template?.state)
}
