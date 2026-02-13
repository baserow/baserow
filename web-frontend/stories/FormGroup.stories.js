import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'

export default {
  title: 'Baserow/Form Elements/FormGroup',
  component: FormGroup,
  tags: ['autodocs'],
  argTypes: {
    label: {
      control: 'text',
      description: 'Label text',
    },
    smallLabel: {
      control: 'boolean',
      description: 'Make label smaller',
    },
    required: {
      control: 'boolean',
      description: 'Show required asterisk',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
    errorMessage: {
      control: 'text',
      description: 'Error message to display',
    },
    helperText: {
      control: 'text',
      description: 'Helper text below the input',
    },
    horizontal: {
      control: 'boolean',
      description: 'Layout label and input horizontally',
    },
  },
  args: {
    label: 'Email Address',
    smallLabel: false,
    required: false,
    error: false,
    errorMessage: '',
    helperText: '',
    horizontal: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { FormGroup, FormInput },
    setup() {
      return { args }
    },
    template: `
      <FormGroup v-bind="args">
        <FormInput placeholder="user@example.com" />
      </FormGroup>
    `,
  }),
}

export const RequiredWithError = {
  args: {
    required: true,
    error: true,
    errorMessage: 'This field is required.',
  },
  render: (args) => ({
    components: { FormGroup, FormInput },
    setup() {
      return { args }
    },
    template: `
      <FormGroup v-bind="args">
        <FormInput error placeholder="user@example.com" />
      </FormGroup>
    `,
  }),
}

export const WithHelperText = {
  args: {
    helperText: 'We will never share your email with anyone else.',
  },
  render: (args) => ({
    components: { FormGroup, FormInput },
    setup() {
      return { args }
    },
    template: `
      <FormGroup v-bind="args">
        <FormInput placeholder="user@example.com" />
      </FormGroup>
    `,
  }),
}

export const Horizontal = {
  args: {
    horizontal: true,
    label: 'Username',
  },
  render: (args) => ({
    components: { FormGroup, FormInput },
    setup() {
      return { args }
    },
    template: `
      <FormGroup v-bind="args">
        <FormInput placeholder="johndoe" />
      </FormGroup>
    `,
  }),
}
