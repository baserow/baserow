import Alert from '@baserow/modules/core/components/Alert'

export default {
  title: 'Baserow/Alert',
  component: Alert,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: '<Alert v-bind="args" />',
  }),
}
