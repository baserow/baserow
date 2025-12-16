import Chips from '@baserow/modules/core/components/Chips'

export default {
  title: 'Baserow/Chips',
  component: Chips,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Chips },
    setup() {
      return { args }
    },
    template: '<Chips v-bind="args" />',
  }),
}


