import RadioGroup from '@baserow/modules/core/components/RadioGroup'

export default {
  title: 'Baserow/Form Elements/Radio/RadioGroup',
  component: RadioGroup,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
    },
    options: {
      control: 'object',
    },
    vertical: {
      control: 'boolean',
    },
  },
  args: {
    modelValue: '1',
    options: [
      { label: 'Option 1', value: '1' },
      { label: 'Option 2', value: '2' },
      { label: 'Option 3', value: '3' },
    ],
    vertical: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { RadioGroup },
    setup() {
      return { args }
    },
    template: '<RadioGroup v-bind="args" />',
  }),
}

export const Vertical = {
  args: {
    vertical: true,
  },
  render: (args) => ({
    components: { RadioGroup },
    setup() {
      return { args }
    },
    template: '<RadioGroup v-bind="args" />',
  }),
}
