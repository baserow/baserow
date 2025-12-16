import Toast from '@baserow/modules/core/components/Toast'

export default {
  title: 'Baserow/Toast',
  component: Toast,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: '<Toast v-bind="args" />',
  }),
}

