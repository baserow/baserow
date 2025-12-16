import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'

export default {
  title: 'Baserow/Form Elements/Dropdown',
  component: Dropdown,
  tags: ['autodocs'],
  argTypes: {
    searchText: {
      control: 'text',
    },
    placeholder: {
      control: 'text',
    },
    showSearch: {
      control: 'boolean',
    },
    showInput: {
      control: 'boolean',
    },
    showFooter: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    size: {
      control: 'select',
      options: ['regular', 'large'],
    },
    tabindex: {
      control: 'number',
    },
    fixedItems: {
      control: 'boolean',
    },
    maxWidth: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
  },
  args: {
    searchText: '',
    placeholder: '',
    showSearch: false,
    showInput: true,
    showFooter: false,
    disabled: false,
    size: 'regular',
    tabindex: 0,
    fixedItems: false,
    maxWidth: false,
    error: false,
  },
  parameters: {
    backgrounds: {
      default: 'white',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <Dropdown v-bind="args">
        <DropdownItem name="France" value="france"></DropdownItem>
        <DropdownItem name="Italy" value="italy"></DropdownItem>
        <DropdownItem name="Netherlands" value="netherlands"></DropdownItem>
        <DropdownItem name="Belgium" value="belgium"></DropdownItem>
      </Dropdown>
    `,
  }),
}

export const MultipleSelection = {
  args: {
    multiple: true,
    value: [],
  },
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <Dropdown v-bind="args">
        <DropdownItem name="France" value="france"></DropdownItem>
        <DropdownItem name="Italy" value="italy"></DropdownItem>
        <DropdownItem name="Netherlands" value="netherlands"></DropdownItem>
        <DropdownItem name="Belgium" value="belgium"></DropdownItem>
      </Dropdown>
    `,
  }),
}


