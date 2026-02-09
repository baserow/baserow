import Checkbox from '@baserow/modules/core/components/Checkbox'
import { ref } from 'vue'

export default {
  title: 'Baserow/Form Elements/Checkbox',
  component: Checkbox,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'boolean',
      description: 'The checked state (v-model)',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable interaction',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
    indeterminate: {
      control: 'boolean',
      description: 'Show indeterminate state (-)',
    },
  },
  args: {
    modelValue: false,
    disabled: false,
    error: false,
    indeterminate: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=54%3A919&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Checkbox },
    setup() {
      const checked = ref(false)

      // Filter out modelValue from args to avoid conflict with v-model
      const { modelValue, ...otherArgs } = args

      return { otherArgs, checked }
    },
    template: `
      <div>
        <Checkbox v-model="checked" v-bind="otherArgs">
          Label
        </Checkbox>
      </div>
    `,
  }),
}

export const States = {
  render: () => ({
    components: { Checkbox },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <Checkbox :model-value="false">Unchecked</Checkbox>
        <Checkbox :model-value="true">Checked</Checkbox>
        <Checkbox indeterminate>Indeterminate</Checkbox>
        <Checkbox disabled>Disabled Unchecked</Checkbox>
        <Checkbox disabled :model-value="true">Disabled Checked</Checkbox>
        <Checkbox error>Error State</Checkbox>
      </div>
    `,
  }),
}
