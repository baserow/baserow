import SwitchInput from '@baserow/modules/core/components/SwitchInput'

export default {
  title: 'Baserow/Form Elements/Switch',
  component: SwitchInput,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'radio',
      options: ['intermediate state', true, false],
    },
    disabled: {
      control: 'boolean',
    },
    small: {
      control: 'boolean',
    },
    color: {
      control: 'select',
      options: ['green', 'neutral'],
    },
  },
  args: {
    value: false,
    disabled: false,
    small: false,
    color: 'green',
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
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1%3A89&mode=dev',
    },
  },
}

export const Switch = {
  render: (args) => ({
    components: { SwitchInput },
    setup() {
      return { args }
    },
    template: '<SwitchInput v-bind="args">Label</SwitchInput>',
  }),
}


