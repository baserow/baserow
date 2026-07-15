import { ref, watch } from 'vue'

import MenuSearch from '@baserow/modules/core/components/MenuSearch'

const renderMenuSearch = (args) => ({
  components: { MenuSearch },
  setup() {
    const value = ref(args.modelValue)

    watch(
      () => args.modelValue,
      (newValue) => {
        value.value = newValue
      }
    )

    return { args, value }
  },
  template: `
    <div style="width: 380px; overflow: hidden; border: 1px solid #d9dbde; border-radius: 8px; background: #fff;">
      <MenuSearch v-bind="args" v-model="value" />
    </div>
  `,
})

export default {
  title: 'Baserow/MenuSearch',
  component: MenuSearch,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    modelValue: {
      control: 'text',
      description: 'Current search query.',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder displayed in the search input.',
    },
  },
  args: {
    modelValue: '',
    placeholder: 'Search actions',
  },
}

export const Default = {
  render: renderMenuSearch,
}

export const WithValue = {
  args: {
    modelValue: 'row',
  },
  render: renderMenuSearch,
}
