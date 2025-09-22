export const DependencyLinkRowRoles = {
  PREDECESSORS: 'predecessors',
  SUCCESSORS: 'successors',

  items() {
    return [
      DependencyLinkRowRoles.PREDECESSORS,
      DependencyLinkRowRoles.SUCCESSORS,
    ]
  },

  toLabels() {
    return [{ label: this.PREDECESSORS }, { label: this.SUCCESSORS }]
  },
  getIndex(label) {
    const items = DependencyLinkRowRoles.items()
    const idx = items.indexOf(label)
    return idx > -1 ? idx : 0
  },
}

export const DependencyConnectionTypes = {
  END_TO_START: 'end-to-start',
  END_TO_END: 'end-to-end',
  START_TO_END: 'start-to-end',
  START_TO_START: 'start-to-start',

  toLabels() {
    return [
      { label: this.END_TO_START },
      { label: this.END_TO_END },
      { label: this.START_TO_END },
      { label: this.START_TO_START },
    ]
  },
  toFields() {
    return [
      { name: this.END_TO_START, id: this.END_TO_START, description: '' },
      { name: this.END_TO_END, id: this.END_TO_END, description: '' },
      { name: this.START_TO_END, id: this.START_TO_END, description: '' },
      { name: this.START_TO_START, id: this.START_TO_START, description: '' },
    ]
  },
}

export const DependencyBufferType = {
  FLEXIBLE: 'flexible',
  FIXED: 'fixed',
  NONE: 'none',

  toLabels() {
    return [
      { label: this.FLEXIBLE },
      { label: this.FIXED },
      { label: this.NONE },
    ]
  },
  toFields() {
    return [
      { id: this.FLEXIBLE, name: this.FLEXIBLE, description: '' },
      { id: this.FIXED, name: this.FIXED, description: '' },
      { id: this.NONE, name: this.NONE, description: '' },
    ]
  },
}
