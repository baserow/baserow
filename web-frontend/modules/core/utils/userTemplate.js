/**
 * Whether the template is one of the user's own templates, as told by the server.
 */
export function isOwnTemplate(template) {
  return template.is_own === true
}

/**
 * Whether Make public is offered, also when it sends the template to review.
 */
export function canMakePublic(template) {
  return Boolean(template?.can_make_public)
}

/**
 * Whether making the template public submits its listed edit for review.
 */
export function makePublicResubmits(template) {
  return (
    canMakePublic(template) &&
    Boolean(template?.make_public_needs_review) &&
    Boolean(template?.listed)
  )
}

/**
 * Whether the owner can make the template private, or withdraw its review.
 */
export function canMakePrivate(template) {
  return ['public', 'in_review', 'rejected'].includes(template?.state)
}

export function canChangeVisibilityInDetails(template) {
  return ['private', 'public'].includes(template?.state)
}
