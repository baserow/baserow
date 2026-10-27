import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import Button from '@baserow/modules/core/components/Button'

export default {
  title: 'Baserow/Form Elements/Dropdown',
  component: Dropdown,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'text',
      description: 'Selected value (v-model)',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text when empty',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the dropdown',
    },
    loading: {
      control: 'boolean',
      description: 'Show a spinner and prevent opening the dropdown',
    },
    showSearch: {
      control: 'boolean',
      description: 'Show search input inside dropdown',
    },
    searchText: {
      control: 'text',
      description: 'Search input value',
    },
    showFooter: {
      control: 'boolean',
      description: 'Show footer slot',
    },
    size: {
      control: 'select',
      options: ['regular', 'large', 'small'],
      description: 'Size of the dropdown',
    },
    fixedItems: {
      control: 'boolean',
      description: 'Use fixed positioning for items',
    },
    error: {
      control: 'boolean',
      description: 'Show error state',
    },
  },
  args: {
    value: '',
    placeholder: 'Select an option',
    disabled: false,
    loading: false,
    showSearch: false,
    searchText: '',
    showFooter: false,
    size: 'regular',
    fixedItems: false,
    error: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <div style="height: 250px;">
        <Dropdown v-bind="args">
          <DropdownItem name="Option 1" value="1" />
          <DropdownItem name="Option 2" value="2" />
          <DropdownItem name="Option 3" value="3" />
        </Dropdown>
      </div>
    `,
  }),
}

export const WithSearch = {
  args: {
    showSearch: true,
    placeholder: 'Search country...',
  },
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <div style="height: 300px;">
        <Dropdown v-bind="args">
          <DropdownItem name="France" value="fr" />
          <DropdownItem name="Germany" value="de" />
          <DropdownItem name="Italy" value="it" />
          <DropdownItem name="Spain" value="es" />
          <DropdownItem name="United Kingdom" value="uk" />
        </Dropdown>
      </div>
    `,
  }),
}

export const Disabled = {
  args: {
    disabled: true,
    value: '1',
  },
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <Dropdown v-bind="args">
        <DropdownItem name="Option 1" value="1" />
      </Dropdown>
    `,
  }),
}

export const WithFooter = {
  args: {
    showFooter: true,
  },
  render: (args) => ({
    components: { Dropdown, DropdownItem },
    setup() {
      return { args }
    },
    template: `
      <div style="height: 250px;">
        <Dropdown v-bind="args">
          <DropdownItem name="Option A" value="a" />
          <DropdownItem name="Option B" value="b" />
          <template #footer>
              Custom Footer Content
          </template>
        </Dropdown>
      </div>
    `,
  }),
}

export const CustomContent = {
  args: {
    placeholder: 'Open custom content',
  },
  argTypes: {
    size: { options: ['regular', 'large'] },
  },
  parameters: {
    controls: {
      include: ['placeholder', 'disabled', 'loading', 'size', 'error'],
    },
    docs: {
      description: {
        story:
          'The content slot replaces the item list with arbitrary content. Its scoped close function closes the panel and restores focus to the trigger. Dropdown handles positioning, outside clicks and Escape; the caller owns the content and its behavior.',
      },
    },
  },
  render: (args) => ({
    components: { Dropdown, Button },
    setup() {
      return { args }
    },
    template: `
      <div style="max-width: 360px; min-height: 300px;">
        <Dropdown v-bind="args">
          <template #content="{ close }">
            <div class="context__form">
              <div class="context__form-container">
                <h3>Custom content</h3>
                <p>Use this slot to compose any content inside the dropdown.</p>
                <div class="context__form-footer-actions">
                  <Button button-type="button" @click="close">Close</Button>
                </div>
              </div>
            </div>
          </template>
        </Dropdown>
      </div>
    `,
  }),
}
