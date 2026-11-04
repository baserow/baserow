/**
 * Whether the template is one of the user's own templates, as told by the server.
 */
export function isOwnTemplate(template) {
  return template.is_own === true
}

/**
 * Whether the owner can make the template public. Making public a template that
 * an admin rejected submits it for review again, also when an earlier version is
 * still listed, see `make_public_needs_review`.
 */
export function canMakePublic(template) {
  return (
    Boolean(template?.make_public_needs_review) || template?.state === 'private'
  )
}

/**
 * Whether making the template public submits it for review again, rather than
 * making it public: it's listed already, with its latest change rejected.
 */
export function makePublicResubmits(template) {
  return canMakePublic(template) && Boolean(template?.listed)
}

/**
 * Whether the owner can make the template private. Making private a template in
 * review or rejected withdraws it from the review.
 */
export function canMakePrivate(template) {
  return ['public', 'in_review', 'rejected'].includes(template?.state)
}

/**
 * Whether Edit details offers to make the template public or private. A template
 * in review or rejected is sent to review again or withdrawn from its menu, see
 * `canMakePublic` and `canMakePrivate`.
 */
export function canChangeVisibilityInDetails(template) {
  return ['private', 'public'].includes(template?.state)
}
