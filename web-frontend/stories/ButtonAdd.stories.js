import ButtonAdd from '@baserow/modules/core/components/ButtonAdd'

export default {
  title: 'Baserow/Buttons/ButtonAdd',
  component: ButtonAdd,
  tags: ['autodocs'],
  argTypes: {
    disabled: {
      control: 'boolean',
      description: 'If true the button will be disabled',
    },
  },
  args: {
    disabled: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { ButtonAdd },
    setup() {
      return { args }
    },
    template: '<ButtonAdd v-bind="args" />',
  }),
}

export const Disabled = {
  args: {
    disabled: true,
  },
  render: (args) => ({
    components: { ButtonAdd },
    setup() {
      return { args }
    },
    template: '<ButtonAdd v-bind="args" />',
  }),
}
