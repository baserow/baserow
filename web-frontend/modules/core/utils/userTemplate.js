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

export function canInstall(template, isStaff) {
  return !(template?.state === 'blocked' && isOwnTemplate(template) && !isStaff)
}

/**
 * The private link of the user's template, or null without one. The link of a
 * blocked template can't be used.
 *
 * @param {object} template The template as listed in the user's templates, whose
 *   `private_link_token` is only shown to them.
 * @param {object} router The router of the app.
 * @param {string} baseUrl The URL of the web frontend.
 */
export function getPrivateLinkUrl(template, router, baseUrl) {
  if (!template.private_link_token || template.state === 'blocked') {
    return null
  }
  const { href } = router.resolve({
    name: 'template-private-link',
    params: { slug: template.slug, token: template.private_link_token },
  })
  return new URL(href, baseUrl).toString()
}
