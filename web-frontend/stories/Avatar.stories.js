import Avatar from '@baserow/modules/core/components/Avatar'

export default {
  title: 'Baserow/Avatar',
  component: Avatar,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}


