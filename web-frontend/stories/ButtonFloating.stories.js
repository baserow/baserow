import ButtonFloating from '@baserow/modules/core/components/ButtonFloating'

export default {
  title: 'Baserow/Buttons/ButtonFloating',
  component: ButtonFloating,
  tags: ['autodocs'],
  argTypes: {
    icon: {
      control: 'text',
      description: 'The icon class name to display',
    },
    type: {
      control: 'select',
      options: ['primary', 'secondary'],
      description: 'The color variant',
    },
    size: {
      control: 'select',
      options: ['regular', 'small'],
      description: 'The size of the button',
    },
    position: {
      control: 'select',
      options: ['relative', 'fixed'],
      description: 'Positioning strategy',
    },
    loading: {
      control: 'boolean',
      description: 'Show loading spinner',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the button',
    },
  },
  args: {
    icon: 'iconoir-plus',
    type: 'primary',
    size: 'regular',
    position: 'relative',
    loading: false,
    disabled: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { ButtonFloating },
    setup() {
      return { args }
    },
    template: '<ButtonFloating v-bind="args" />',
  }),
}

export const Secondary = {
  args: {
    type: 'secondary',
    icon: 'iconoir-edit-pencil',
  },
  render: (args) => ({
    components: { ButtonFloating },
    setup() {
      return { args }
    },
    template: '<ButtonFloating v-bind="args" />',
  }),
}

export const Small = {
  args: {
    size: 'small',
    icon: 'iconoir-search',
  },
  render: (args) => ({
    components: { ButtonFloating },
    setup() {
      return { args }
    },
    template: '<ButtonFloating v-bind="args" />',
  }),
}

export const States = {
  render: () => ({
    components: { ButtonFloating },
    template: `
      <div style="display: flex; gap: 10px;">
        <ButtonFloating icon="iconoir-plus" />
        <ButtonFloating icon="iconoir-plus" loading />
        <ButtonFloating icon="iconoir-plus" disabled />
      </div>
    `,
  }),
}
