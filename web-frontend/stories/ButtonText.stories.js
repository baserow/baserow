import ButtonText from '@baserow/modules/core/components/ButtonText'

export default {
  title: 'Baserow/Buttons/ButtonText',
  component: ButtonText,
  tags: ['autodocs'],
  argTypes: {
    icon: {
      control: 'text',
      description: 'Icon class name',
    },
    image: {
      control: 'text',
      description: 'Image URL (if no icon)',
    },
    type: {
      control: 'select',
      options: ['primary', 'secondary'],
      description: 'Color variant',
    },
    size: {
      control: 'select',
      options: ['regular', 'small'],
      description: 'Size of the button',
    },
    loading: {
      control: 'boolean',
      description: 'Show loading spinner',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable interaction',
    },
    tag: {
      control: 'select',
      options: ['button', 'a'],
      description: 'Root HTML tag',
    },
  },
  args: {
    icon: '',
    image: '',
    type: 'primary',
    size: 'regular',
    loading: false,
    disabled: false,
    tag: 'button',
  },
}

export const Default = {
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args">Click me</ButtonText>',
  }),
}

export const WithIcon = {
  args: {
    icon: 'iconoir-plus',
  },
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args">Add Item</ButtonText>',
  }),
}

export const Secondary = {
  args: {
    type: 'secondary',
    icon: 'iconoir-cancel',
  },
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args">Cancel</ButtonText>',
  }),
}

export const Small = {
  args: {
    size: 'small',
  },
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args">Small Button</ButtonText>',
  }),
}

export const States = {
  render: () => ({
    components: { ButtonText },
    template: `
      <div style="display: flex; gap: 10px;">
        <ButtonText>Normal</ButtonText>
        <ButtonText loading>Loading</ButtonText>
        <ButtonText disabled>Disabled</ButtonText>
      </div>
    `,
  }),
}
