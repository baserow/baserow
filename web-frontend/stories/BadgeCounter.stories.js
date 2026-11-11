import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

export default {
  title: 'Baserow/BadgeCounter',
  component: BadgeCounter,
  tags: ['autodocs'],
  argTypes: {
    count: {
      control: 'number',
      description: 'The number to display in the badge',
    },
    limit: {
      control: 'number',
      description:
        'The maximum number to display. If count >= limit, displays (limit-1)+',
    },
  },
  args: {
    count: 5,
    limit: 100,
  },
}

export const Default = {
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}

export const SingleDigit = {
  args: {
    count: 3,
  },
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}

export const DoubleDigit = {
  args: {
    count: 42,
  },
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}

export const WithLimit = {
  args: {
    count: 150,
    limit: 100,
  },
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}

export const AllVariations = {
  render: () => ({
    components: { BadgeCounter },
    template: `
      <div style="display: flex; gap: 16px; align-items: center;">
        <div>
          <p>Single Digit:</p>
          <BadgeCounter :count="5" />
        </div>
        <div>
          <p>Double Digit:</p>
          <BadgeCounter :count="12" />
        </div>
        <div>
          <p>Over Limit (limit=10):</p>
          <BadgeCounter :count="15" :limit="10" />
        </div>
        <div>
          <p>Over Limit (limit=100):</p>
          <BadgeCounter :count="250" :limit="100" />
        </div>
      </div>
    `,
  }),
}
