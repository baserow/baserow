import Tabs from '@baserow/modules/core/components/Tabs'

export default {
  title: 'Baserow/Tabs',
  component: Tabs,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Tabs },
    setup() {
      return { args }
    },
    template: '<Tabs v-bind="args" />',
  }),
}


