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

export function getState(state, t) {
  const known = STATES[state]
  return known
    ? { color: known.color, icon: known.icon, label: t(known.label) }
    : { color: 'neutral', icon: null, label: state }
}

export function showsListed(template) {
  return Boolean(
    template.listed && ['in_review', 'rejected'].includes(template.state)
  )
}
