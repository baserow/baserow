import RadioCard from '@baserow/modules/core/components/RadioCard'

export default {
  title: 'Baserow/Form Elements/Radio/RadioCard',
  component: RadioCard,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
    },
    value: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
  },
  args: {
    modelValue: 'basic',
    value: 'basic',
    disabled: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { RadioCard },
    setup() {
      return { args }
    },
    template: `
      <RadioCard v-bind="args">
        <div style="font-weight: bold; margin-bottom: 4px;">Basic Plan</div>
        <div style="color: #666;">Standard features for personal use.</div>
      </RadioCard>
    `,
  }),
}

export const Group = {
  render: () => ({
    components: { RadioCard },
    data() {
      return { selected: 'pro' }
    },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px; max-width: 400px;">
        <RadioCard v-model="selected" value="basic">
          <strong>Basic</strong> - Free forever
        </RadioCard>
        <RadioCard v-model="selected" value="pro">
          <strong>Pro</strong> - $10/month
        </RadioCard>
        <RadioCard v-model="selected" value="enterprise" disabled>
          <strong>Enterprise</strong> - Contact us (Unavailable)
        </RadioCard>
      </div>
    `,
  }),
}
