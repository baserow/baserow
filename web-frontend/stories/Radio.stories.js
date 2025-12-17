import Radio from '@baserow/modules/core/components/Radio'
import { ref } from 'vue'

export default {
  title: 'Baserow/Form Elements/Radio/Radio',
  component: Radio,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
      description: 'Currently selected value',
    },
    value: {
      control: 'text',
      description: 'Value of this radio option',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable this option',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
  },
  args: {
    modelValue: '1',
    value: '1',
    disabled: false,
    error: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=53%3A1852&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Radio },
    setup() {
      return { args }
    },
    template: '<Radio v-bind="args">Option Label</Radio>',
  }),
}

export const GroupExample = {
  render: () => ({
    components: { Radio },
    setup() {
      const selected = ref('a')
      return { selected }
    },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <Radio :model-value="selected" @input="val => selected = val" value="a">Option A</Radio>
        <Radio :model-value="selected" @input="val => selected = val" value="b">Option B</Radio>
        <Radio :model-value="selected" @input="val => selected = val" value="c">Option C</Radio>
        <div style="margin-top: 10px; color: #666;">Selected: {{ selected }}</div>
      </div>
    `,
  }),
}

export const States = {
  render: () => ({
    components: { Radio },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <Radio :model-value="'1'" value="1">Selected</Radio>
        <Radio :model-value="'2'" value="1">Unselected</Radio>
        <Radio disabled>Disabled</Radio>
        <Radio error :model-value="'1'" value="1">Error</Radio>
      </div>
    `,
  }),
}
