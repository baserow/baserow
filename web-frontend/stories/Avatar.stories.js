import Avatar from '@baserow/modules/core/components/Avatar'

export default {
  title: 'Baserow/Avatar',
  component: Avatar,
  tags: ['autodocs'],
  argTypes: {
    icon: {
      control: 'text',
      description: 'The icon classname to display',
    },
    image: {
      control: 'text',
      description: 'The URL of the image to display',
    },
    rounded: {
      control: 'boolean',
      description: 'If true the avatar will be rounded',
    },
    initials: {
      control: 'text',
      description: 'The initials to display if no image is provided',
    },
    color: {
      control: 'select',
      options: [
        'blue',
        'cyan',
        'green',
        'yellow',
        'red',
        'magenta',
        'purple',
        'neutral',
        'transparent',
      ],
      description: 'The background color of the avatar',
    },
    size: {
      control: 'select',
      options: ['small', 'medium', 'large', 'x-large'],
      description: 'The size of the avatar',
    },
  },
  args: {
    icon: '',
    image: '',
    rounded: false,
    initials: 'JD',
    color: 'blue',
    size: 'medium',
  },
}

export const Default = {
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}

export const WithInitials = {
  args: {
    initials: 'AB',
    color: 'green',
  },
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}

export const WithIcon = {
  args: {
    icon: 'iconoir-user',
    color: 'purple',
    initials: null,
  },
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}

export const WithImage = {
  args: {
    icon: '',
    image:
      'https://upload.wikimedia.org/wikipedia/commons/1/11/Roger_Federer_2015_%28cropped%29.jpg',
    initials: '',
  },
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}

export const Rounded = {
  args: {
    rounded: true,
    initials: 'R',
    color: 'magenta',
  },
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}

export const AllSizes = {
  render: () => ({
    components: { Avatar },
    template: `
      <div style="display: flex; align-items: center; gap: 16px;">
        <Avatar size="small" initials="SM" color="blue" />
        <Avatar size="medium" initials="MD" color="cyan" />
        <Avatar size="large" initials="LG" color="green" />
        <Avatar size="x-large" initials="XL" color="yellow" />
      </div>
    `,
  }),
}

export const AllColors = {
  render: () => ({
    components: { Avatar },
    template: `
      <div style="display: flex; flex-wrap: wrap; gap: 10px;">
        <Avatar initials="Bl" color="blue" />
        <Avatar initials="Cy" color="cyan" />
        <Avatar initials="Gr" color="green" />
        <Avatar initials="Ye" color="yellow" />
        <Avatar initials="Re" color="red" />
        <Avatar initials="Ma" color="magenta" />
        <Avatar initials="Pu" color="purple" />
        <Avatar initials="Ne" color="neutral" />
        <Avatar initials="Tr" color="transparent" style="border: 1px solid #ccc;" />
      </div>
    `,
  }),
}
