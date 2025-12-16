import BadgeCollaborator from '@baserow/modules/core/components/BadgeCollaborator'

export default {
  title: 'Baserow/BadgeCollaborator',
  component: BadgeCollaborator,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { BadgeCollaborator },
    setup() {
      return { args }
    },
    template: '<BadgeCollaborator v-bind="args" />',
  }),
}


