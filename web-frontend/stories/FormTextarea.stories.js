import FormTextarea from '@baserow/modules/core/components/FormTextarea'

export default {
  title: 'Baserow/Form Elements/Textarea',
  component: FormTextarea,
  tags: ['autodocs'],
  argTypes: {
    rows: {
      control: 'number',
    },
    placeholder: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    autoExpandable: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
    minRows: {
      control: 'number',
    },
    maxRows: {
      control: 'number',
    },
    maxlength: {
      control: 'number',
    },
    size: {
      control: 'select',
      options: ['small', 'regular'],
    },
  },
  args: {
    rows: 4,
    placeholder: 'Type something...',
    disabled: false,
    autoExpandable: false,
    error: false,
    minRows: null,
    maxRows: null,
    maxlength: null,
    size: 'regular',
  },
  parameters: {
    backgrounds: {
      default: 'light',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1%3A87&mode=dev',
    },
  },
}

export const Textarea = {
  render: (args) => ({
    components: { FormTextarea },
    setup() {
      return { args }
    },
    template: '<FormTextarea v-bind="args" />',
  }),
}


