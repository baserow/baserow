import Paginator from '@baserow/modules/core/components/Paginator'

export default {
  title: 'Baserow/Paginator',
  component: Paginator,
  tags: ['autodocs'],
  argTypes: {
    page: {
      control: 'number',
    },
    totalPages: {
      control: 'number',
    },
  },
  args: {
    page: 3,
    totalPages: 10,
  },
  parameters: {
    backgrounds: {
      default: 'white',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1204%3A4132&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Paginator },
    setup() {
      return { args }
    },
    template: '<Paginator v-bind="args" />',
  }),
}


