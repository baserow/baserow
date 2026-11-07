/**
 * Whether the template is one of the user's own templates, as told by the server.
 */
export function isOwnTemplate(template) {
  return template.is_own === true
}

/**
 * Whether the owner can make the template public, as told by the server, see
 * `can_make_public`.
 */
export function canMakePublic(template) {
  return Boolean(template?.can_make_public)
}

/**
 * Whether making the template public submits it for review again, rather than
 * making it public: it's listed already, and its latest edit goes to review.
 */
export function makePublicResubmits(template) {
  return (
    canMakePublic(template) &&
    Boolean(template?.make_public_needs_review) &&
    Boolean(template?.listed)
  )
}

/**
 * Whether the owner can make the template private. Making private a template in
 * review or rejected withdraws it from the review.
 */
export function canMakePrivate(template) {
  return ['public', 'in_review', 'rejected'].includes(template?.state)
}

/**
 * Whether Edit details offers public/private. A template in review or rejected
 * is resubmitted or withdrawn from its menu instead.
 */
export function canChangeVisibilityInDetails(template) {
  return ['private', 'public'].includes(template?.state)
}
