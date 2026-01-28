import FormInput from '@baserow/modules/core/components/FormInput'

export default {
  title: 'Baserow/Form Elements/Input',
  component: FormInput,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
      description: 'Input value (v-model)',
    },
    label: {
      control: 'text',
      description: 'Floating label text',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text',
    },
    type: {
      control: 'select',
      options: ['text', 'number', 'password', 'email', 'url'],
      description: 'Input type',
    },
    size: {
      control: 'select',
      options: ['small', 'regular', 'large', 'xlarge'],
      description: 'Size of the input',
    },
    iconLeft: {
      control: 'text',
      description: 'Icon class for left side',
    },
    iconRight: {
      control: 'text',
      description: 'Icon class for right side',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the input',
    },
    loading: {
      control: 'boolean',
      description: 'Show loading spinner',
    },
    required: {
      control: 'boolean',
      description: 'Mark as required',
    },
    monospace: {
      control: 'boolean',
      description: 'Use monospace font',
    },
  },
  args: {
    modelValue: '',
    label: '',
    placeholder: 'Type here...',
    type: 'text',
    size: 'regular',
    iconLeft: '',
    iconRight: '',
    error: false,
    disabled: false,
    loading: false,
    required: false,
    monospace: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1%3A87&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { FormInput },
    setup() {
      return { args }
    },
    template: '<FormInput v-bind="args" />',
  }),
}

export const WithIcons = {
  args: {
    iconLeft: 'iconoir-user',
    iconRight: 'iconoir-check',
    placeholder: 'Username',
  },
  render: (args) => ({
    components: { FormInput },
    setup() {
      return { args }
    },
    template: '<FormInput v-bind="args" />',
  }),
}

export const Password = {
  args: {
    type: 'password',
    placeholder: 'Password',
  },
  render: (args) => ({
    components: { FormInput },
    setup() {
      return { args }
    },
    template: '<FormInput v-bind="args" />',
  }),
}

export const States = {
  render: () => ({
    components: { FormInput },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px; max-width: 300px;">
        <FormInput placeholder="Normal" />
        <FormInput placeholder="Error" error />
        <FormInput placeholder="Disabled" disabled />
        <FormInput placeholder="Loading" loading />
      </div>
    `,
  }),
}

export const Sizes = {
  render: () => ({
    components: { FormInput },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px; max-width: 300px;">
        <FormInput size="small" placeholder="Small" />
        <FormInput size="regular" placeholder="Regular" />
        <FormInput size="large" placeholder="Large" />
        <FormInput size="xlarge" placeholder="Extra Large" />
      </div>
    `,
  }),
}
