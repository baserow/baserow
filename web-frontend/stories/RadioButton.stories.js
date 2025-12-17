import RadioButton from '@baserow/modules/core/components/RadioButton'
import { ref } from 'vue'

export default {
  title: 'Baserow/Form Elements/Radio/RadioButton',
  component: RadioButton,
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
    icon: {
      control: 'text',
    },
  },
  args: {
    modelValue: '1',
    value: '1',
    disabled: false,
    icon: '',
  },
}

export const Default = {
  render: () => ({
    components: { RadioButton },
    setup() {
      const selected = ref('day')
      return { selected }
    },
    template: `
      <div style="display: flex; gap: 10px;">
        <RadioButton 
          :model-value="selected" 
          @input="val => selected = val" 
          value="day" 
          icon="iconoir-sun-light"
        >
          Day
        </RadioButton>
        <RadioButton 
          :model-value="selected" 
          @input="val => selected = val" 
          value="night" 
          icon="iconoir-half-moon"
        >
          Night
        </RadioButton>
        <div style="margin-left: 20px; align-self: center;">Selected: {{ selected }}</div>
      </div>
    `,
  }),
}
