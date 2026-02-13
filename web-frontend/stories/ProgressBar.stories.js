import ProgressBar from '@baserow/modules/core/components/ProgressBar'

export default {
  title: 'Baserow/ProgressBar',
  component: ProgressBar,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'number',
      description: 'Progress value (0-100)',
    },
    showValue: {
      control: 'boolean',
      description: 'Show percentage text',
    },
    status: {
      control: 'select',
      options: ['success', 'warning', 'error', null],
      description: 'Status color',
    },
  },
  args: {
    value: 50,
    showValue: true,
    status: null,
  },
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

export const Success = {
  args: {
    value: 100,
    status: 'success',
  },
  render: (args) => ({
    components: { ProgressBar },
    setup() {
      return { args }
    },
    template: '<ProgressBar v-bind="args" />',
  }),
}

export const Error = {
  args: {
    value: 45,
    status: 'error',
  },
  render: (args) => ({
    components: { ProgressBar },
    setup() {
      return { args }
    },
    template: '<ProgressBar v-bind="args" />',
  }),
}
