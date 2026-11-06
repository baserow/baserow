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
 * Returns the badge of a user template state; an unknown one is shown as is.
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
 * Whether a template in review or rejected still lists an approved version.
 *
 * @param {object} template A user template with its `state` and `listed`.
 * @returns {boolean} Whether the template shows that it's still listed.
 */
export function showsListed(template) {
  return Boolean(
    template.listed && ['in_review', 'rejected'].includes(template.state)
  )
}
