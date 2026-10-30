/**
 * The states of a user template as the server reports them, with the color and
 * icon of their badge and the locale key of their label.
 */
export const STATES = {
  private: {
    color: 'neutral',
    icon: 'iconoir-eye-off',
    label: 'userTemplateList.statePrivate',
  },
  in_review: {
    color: 'yellow',
    icon: 'iconoir-clock',
    label: 'userTemplateList.stateInReview',
  },
  rejected: {
    color: 'red',
    icon: 'iconoir-eye-off',
    label: 'userTemplateList.stateRejected',
  },
  blocked: {
    color: 'red',
    icon: 'iconoir-warning-triangle',
    label: 'userTemplateList.stateBlocked',
  },
  public: {
    color: 'green',
    icon: 'iconoir-eye-empty',
    label: 'userTemplateList.statePublic',
  },
}

/**
 * A state that this version doesn't know is shown as it is, so that a list still
 * works when a new state is added.
 *
 * @param {string} state The state of a user template.
 * @param {function} t Translates a locale key.
 * @returns {{color: string, icon: string|null, label: string}} The badge of the
 *   state.
 */
export function getState(state, t) {
  const known = STATES[state]
  return known
    ? { color: known.color, icon: known.icon, label: t(known.label) }
    : { color: 'neutral', icon: null, label: state }
}

/**
 * Whether the owner can make the template public. Making public a template that
 * an admin rejected submits it for review again, also when an earlier version is
 * still listed, see `needs_review`.
 *
 * @param {object} template The template as listed in the user's templates.
 * @returns {boolean}
 */
export function canMakePublic(template) {
  return Boolean(template?.needs_review) || template?.state === 'private'
}

/**
 * Whether the owner can make the template private. Making private a template in
 * review or rejected withdraws it from the review.
 *
 * @param {object} template The template as listed in the user's templates.
 * @returns {boolean}
 */
export function canMakePrivate(template) {
  return ['public', 'in_review', 'rejected'].includes(template?.state)
}

/**
 * A template in review or rejected can still be listed with an earlier approved
 * version, which its badge tells next to the state.
 *
 * @param {object} template A user template with its `state` and `listed`.
 * @returns {boolean} Whether the template shows that it's still listed.
 */
export function showsListed(template) {
  return Boolean(
    template.listed && ['in_review', 'rejected'].includes(template.state)
  )
}
