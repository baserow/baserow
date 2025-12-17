import SegmentControl from '@baserow/modules/core/components/SegmentControl'

export default {
  title: 'Baserow/Form Elements/SegmentControl',
  component: SegmentControl,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
    },
    options: {
      control: 'object',
      description: 'Array of objects with label and value',
    },
    disabled: {
      control: 'boolean',
    },
  },
  args: {
    modelValue: 'daily',
    options: [
      { label: 'Daily', value: 'daily' },
      { label: 'Weekly', value: 'weekly' },
      { label: 'Monthly', value: 'monthly' },
    ],
    disabled: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { SegmentControl },
    setup() {
      return { args }
    },
    template: '<SegmentControl v-bind="args" />',
  }),
}
