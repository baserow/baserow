import Context from '@baserow/modules/core/components/Context'

export default {
  title: 'Baserow/Context',
  component: Context,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Context },
    setup() {
      return { args }
    },
    template: '<Context v-bind="args" />',
  }),
}


