import FormTextarea from '@baserow/modules/core/components/FormTextarea'

export default {
  title: 'Baserow/Form Elements/Textarea',
  component: FormTextarea,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
      description: 'Input value (v-model)',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text',
    },
    rows: {
      control: 'number',
      description: 'Number of rows',
    },
    minRows: {
      control: 'number',
      description: 'Minimum rows (if auto-expandable)',
    },
    maxRows: {
      control: 'number',
      description: 'Maximum rows (if auto-expandable)',
    },
    autoExpandable: {
      control: 'boolean',
      description: 'Automatically adjust height to content',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the textarea',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
  },
  args: {
    modelValue: '',
    placeholder: 'Type your message...',
    rows: 3,
    minRows: 3,
    maxRows: 10,
    autoExpandable: false,
    disabled: false,
    error: false,
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
    components: { FormTextarea },
    setup() {
      return { args }
    },
    template: '<FormTextarea v-bind="args" />',
  }),
}

export const AutoExpandable = {
  args: {
    autoExpandable: true,
    placeholder: 'Type to expand...',
    minRows: 2,
    maxRows: 6,
  },
  render: (args) => ({
    components: { FormTextarea },
    setup() {
      return { args }
    },
    template: '<FormTextarea v-bind="args" />',
  }),
}

export const States = {
  render: () => ({
    components: { FormTextarea },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px; max-width: 400px;">
        <FormTextarea placeholder="Normal" />
        <FormTextarea placeholder="Error" error />
        <FormTextarea placeholder="Disabled" disabled />
      </div>
    `,
  }),
}
