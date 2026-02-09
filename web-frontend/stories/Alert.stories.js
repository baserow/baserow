import Alert from '@baserow/modules/core/components/Alert'

export default {
  title: 'Baserow/Alert',
  component: Alert,
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: 'select',
      options: [
        'info-neutral',
        'info-primary',
        'warning',
        'error',
        'success',
        'blank',
      ],
    },
    position: {
      control: 'select',
      options: [null, 'top', 'bottom'],
    },
    loading: {
      control: 'boolean',
    },
    closeButton: {
      control: 'boolean',
    },
    width: {
      control: 'number',
    },
  },
  args: {
    type: 'info-primary',
    position: null,
    loading: false,
    closeButton: false,
    width: null,
  },
}

export const Default = {
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Alert Title</template>
        This is an alert message with some important information.
      </Alert>
    `,
  }),
}

export const InfoPrimary = {
  args: {
    type: 'info-primary',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Information</template>
        This is a primary info alert for important notices.
      </Alert>
    `,
  }),
}

export const InfoNeutral = {
  args: {
    type: 'info-neutral',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Note</template>
        This is a neutral info alert for general information.
      </Alert>
    `,
  }),
}

export const Warning = {
  args: {
    type: 'warning',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Warning</template>
        Please be careful, this action may have consequences.
      </Alert>
    `,
  }),
}

export const Error = {
  args: {
    type: 'error',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Error</template>
        Something went wrong. Please try again later.
      </Alert>
    `,
  }),
}

export const Success = {
  args: {
    type: 'success',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Success</template>
        Your changes have been saved successfully!
      </Alert>
    `,
  }),
}

export const WithCloseButton = {
  args: {
    type: 'info-primary',
    closeButton: true,
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      const onClose = () => alert('Close button clicked!')
      return { args, onClose }
    },
    template: `
      <Alert v-bind="args" @close="onClose">
        <template #title>Dismissible Alert</template>
        Click the close button to dismiss this alert.
      </Alert>
    `,
  }),
}

export const WithLoading = {
  args: {
    type: 'info-primary',
    loading: true,
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Loading...</template>
        Please wait while we process your request.
      </Alert>
    `,
  }),
}

export const WithActions = {
  args: {
    type: 'warning',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Confirm Action</template>
        Are you sure you want to proceed with this action?
        <template #actions>
          <button class="button button--secondary button--small">Cancel</button>
          <button class="button button--primary button--small">Confirm</button>
        </template>
      </Alert>
    `,
  }),
}

export const WithCustomWidth = {
  args: {
    type: 'info-primary',
    width: 400,
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        <template #title>Custom Width</template>
        This alert has a custom width of 400px.
      </Alert>
    `,
  }),
}

export const MessageOnly = {
  args: {
    type: 'info-neutral',
  },
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: `
      <Alert v-bind="args">
        This is an alert with only a message, no title.
      </Alert>
    `,
  }),
}

export const AllTypes = {
  render: () => ({
    components: { Alert },
    template: `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <Alert type="info-primary">
          <template #title>Info Primary</template>
          Primary information alert style.
        </Alert>
        <Alert type="info-neutral">
          <template #title>Info Neutral</template>
          Neutral information alert style.
        </Alert>
        <Alert type="success">
          <template #title>Success</template>
          Success alert style.
        </Alert>
        <Alert type="warning">
          <template #title>Warning</template>
          Warning alert style.
        </Alert>
        <Alert type="error">
          <template #title>Error</template>
          Error alert style.
        </Alert>
        <Alert type="blank">
          <template #title>Blank</template>
          Blank alert style without icon.
        </Alert>
      </div>
    `,
  }),
}
