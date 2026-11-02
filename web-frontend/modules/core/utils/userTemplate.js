/**
 * Whether the template is one of the user's own templates, as told by the server.
 */
export function isOwnTemplate(template) {
  return template.is_own === true
}

/**
 * The visibility change the author can make to their template: `make-public` for
 * a private template, `make-private` for a public one, or else null, for example
 * for a rejected or blocked template.
 */
export function getVisibilityAction(template) {
  return VISIBILITY_ACTIONS[template?.state] ?? null
}

const VISIBILITY_ACTIONS = {
  private: 'make-public',
  public: 'make-private',
}
