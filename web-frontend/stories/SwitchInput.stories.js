import SwitchInput from '@baserow/modules/core/components/SwitchInput'
import { ref } from 'vue'

export default {
  title: 'Baserow/Form Elements/Switch',
  component: SwitchInput,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'radio',
      options: ['intermediate state', true, false],
      description: 'Switch state (v-model)',
    },
    disabled: {
      control: 'boolean',
    },
    small: {
      control: 'boolean',
      description: 'Small size',
    },
    color: {
      control: 'select',
      options: ['green', 'neutral', 'red'],
    },
  },
  args: {
    value: false,
    disabled: false,
    small: false,
    color: 'green',
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1%3A89&mode=dev',
    },
  },
}

export const Interactive = {
  render: (args) => ({
    components: { SwitchInput },
    setup() {
      const checked = ref(false)
      // Exclude value from args to avoid conflict with v-model
      const { value, ...otherArgs } = args
      return { otherArgs, checked }
    },
    template: `
      <div>
        <SwitchInput v-model="checked" v-bind="otherArgs">
         Label
        </SwitchInput>
      </div>
    `,
  }),
}

export const States = {
  render: () => ({
    components: { SwitchInput },
    template: `
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <SwitchInput :value="false">Off</SwitchInput>
        <SwitchInput :value="true">On</SwitchInput>
        <SwitchInput disabled :value="true">Disabled On</SwitchInput>
        <SwitchInput disabled :value="false">Disabled Off</SwitchInput>
      </div>
    `,
  }),
}
