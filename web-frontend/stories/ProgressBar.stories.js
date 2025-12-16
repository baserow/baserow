import ProgressBar from '@baserow/modules/core/components/ProgressBar'

export default {
  title: 'Baserow/ProgressBar',
  component: ProgressBar,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { ProgressBar },
    setup() {
      return { args }
    },
    template: '<ProgressBar v-bind="args" />',
  }),
}


