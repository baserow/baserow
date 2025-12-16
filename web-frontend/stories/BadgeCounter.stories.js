import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

export default {
  title: 'Baserow/BadgeCounter',
  component: BadgeCounter,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}


