import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'

export default {
  title: 'Baserow/Buttons/ButtonIcon',
  component: ButtonIcon,
  tags: ['autodocs'],
  argTypes: {
    icon: {
      control: 'text',
      description: 'The icon class name',
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
      description: 'Show loading state',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable interaction',
    },
    active: {
      control: 'boolean',
      description: 'Active state',
    },
    tag: {
      control: 'select',
      options: ['button', 'a', 'nuxt-link'],
      description: 'Root HTML tag',
    },
  },
  args: {
    icon: 'iconoir-more-horiz',
    type: 'primary',
    size: 'regular',
    loading: false,
    disabled: false,
    active: false,
    tag: 'button',
  },
}

export const Default = {
  render: (args) => ({
    components: { ButtonIcon },
    setup() {
      return { args }
    },
    template: '<ButtonIcon v-bind="args" />',
  }),
}

export const Secondary = {
  args: {
    type: 'secondary',
    icon: 'iconoir-cancel',
  },
  render: (args) => ({
    components: { ButtonIcon },
    setup() {
      return { args }
    },
    template: '<ButtonIcon v-bind="args" />',
  }),
}

export const Small = {
  args: {
    size: 'small',
    icon: 'iconoir-search',
  },
  render: (args) => ({
    components: { ButtonIcon },
    setup() {
      return { args }
    },
    template: '<ButtonIcon v-bind="args" />',
  }),
}

export const AllStates = {
  render: () => ({
    components: { ButtonIcon },
    template: `
      <div style="display: flex; gap: 10px;">
        <ButtonIcon icon="iconoir-settings" />
        <ButtonIcon icon="iconoir-settings" active />
        <ButtonIcon icon="iconoir-settings" disabled />
        <ButtonIcon icon="iconoir-settings" loading />
      </div>
    `,
  }),
}
