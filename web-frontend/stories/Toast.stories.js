import Toast from '@baserow/modules/core/components/toasts/Toast'

export default {
  title: 'Baserow/Toast',
  component: Toast,
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: 'select',
      options: ['info-primary', 'info-neutral', 'success', 'warning', 'error'],
      description: 'The semantic type of the toast',
    },
    icon: {
      control: 'text',
      description: 'Icon class name',
    },
    loading: {
      control: 'boolean',
      description: 'Show loading spinner',
    },
    closeButton: {
      control: 'boolean',
      description: 'Show close button',
    },
    // Slots content controls
    titleSlot: {
      control: 'text',
      description: 'Content for the title slot',
      table: { category: 'Slots' },
    },
    defaultSlot: {
      control: 'text',
      description: 'Content for the default (message) slot',
      table: { category: 'Slots' },
    },
  },
  args: {
    type: 'info-primary',
    loading: false,
    closeButton: true,
    titleSlot: 'Notification',
    defaultSlot: 'This is a toast message.',
    icon: 'iconoir-info-empty',
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=...&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: `
      <Toast v-bind="args">
        <template v-if="args.titleSlot" #title>{{ args.titleSlot }}</template>
        {{ args.defaultSlot }}
      </Toast>
    `,
  }),
}

export const Success = {
  args: {
    type: 'success',
    titleSlot: 'Saved',
    defaultSlot: 'Changes saved successfully.',
    icon: 'iconoir-check-circle',
  },
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: `
      <Toast v-bind="args">
        <template #title>{{ args.titleSlot }}</template>
        {{ args.defaultSlot }}
      </Toast>
    `,
  }),
}

export const Error = {
  args: {
    type: 'error',
    titleSlot: 'Error',
    defaultSlot: 'Something went wrong.',
    icon: 'iconoir-warning-circle',
  },
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: `
      <Toast v-bind="args">
        <template #title>{{ args.titleSlot }}</template>
        {{ args.defaultSlot }}
      </Toast>
    `,
  }),
}

export const WithActions = {
  args: {
    type: 'warning',
    titleSlot: 'Warning',
    defaultSlot: 'Are you sure you want to proceed?',
    icon: 'iconoir-warning-triangle',
  },
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: `
      <Toast v-bind="args">
        <template #title>{{ args.titleSlot }}</template>
        {{ args.defaultSlot }}
        <template #actions>
          <button class="button button--secondary button--tiny">Cancel</button>
          <button class="button button--primary button--tiny">Confirm</button>
        </template>
      </Toast>
    `,
  }),
}
