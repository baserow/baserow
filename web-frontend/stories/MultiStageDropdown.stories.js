import { expect, fn, waitFor, within } from 'storybook/test'
import { ref, watch } from 'vue'

import MultiStageDropdown from '@baserow/modules/core/components/MultiStageDropdown'

import { multiStageDropdownItems } from './menuListFixtures'

const renderDropdown = (args) => ({
  components: { MultiStageDropdown },
  setup() {
    const selectedValue = ref(args.modelValue)

    watch(
      () => args.modelValue,
      (value) => {
        selectedValue.value = value
      }
    )

    return { args, selectedValue }
  },
  template: `
    <div style="width: 380px; min-height: 260px;">
      <MultiStageDropdown
        v-bind="args"
        :model-value="selectedValue"
        @update:model-value="selectedValue = $event"
      />
      <div
        data-testid="selected-value"
        style="margin-top: 16px; color: #6a6b70; font-size: 12px;"
      >
        Selected value: {{ selectedValue ?? 'None' }}
      </div>
    </div>
  `,
})

export default {
  title: 'Baserow/Form Elements/MultiStageDropdown',
  component: MultiStageDropdown,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    items: {
      control: 'object',
      description: 'Flat or nested dropdown items.',
    },
    modelValue: {
      control: 'select',
      options: [
        null,
        'repeat',
        'create-row',
        'get-row',
        'update-row',
        'delete-row',
        'send-http-request',
        'send-slack-message',
      ],
      description: 'Value of the selected leaf item.',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder displayed when there is no selection.',
    },
    showSearch: {
      control: 'boolean',
      description: 'Displays the global action search input.',
    },
    searchPlaceholder: {
      control: 'text',
      description: 'Placeholder displayed in the search input.',
    },
    emptyText: {
      control: 'text',
      description: 'Message displayed when no items are visible.',
    },
    disabled: {
      control: 'boolean',
      description: 'Prevents the dropdown from opening.',
    },
    error: {
      control: 'boolean',
      description: 'Displays the error state.',
    },
    size: {
      control: 'select',
      options: ['regular', 'large'],
    },
    onChange: {
      control: false,
      table: { category: 'Events' },
    },
    onSelect: {
      control: false,
      table: { category: 'Events' },
    },
    onDisabledClick: {
      control: false,
      table: { category: 'Events' },
    },
    onShow: {
      control: false,
      table: { category: 'Events' },
    },
    onHide: {
      control: false,
      table: { category: 'Events' },
    },
  },
  args: {
    items: multiStageDropdownItems,
    modelValue: null,
    placeholder: 'Choose an action',
    showSearch: true,
    searchPlaceholder: 'Search actions',
    emptyText: 'No actions found',
    disabled: false,
    error: false,
    size: 'regular',
    onChange: fn(),
    onSelect: fn(),
    onDisabledClick: fn(),
    onShow: fn(),
    onHide: fn(),
  },
}

export const Default = {
  render: renderDropdown,
}

export const Selection = {
  args: {
    onChange: fn(),
    onSelect: fn(),
  },
  render: renderDropdown,
  play: async ({ args, canvas, step, userEvent }) => {
    const body = within(document.body)
    const trigger = canvas.getByRole('button', {
      name: /choose an action/i,
    })

    await step('Open the dropdown', async () => {
      await userEvent.click(trigger)
      await waitFor(() => expect(body.getAllByRole('menu')).toHaveLength(2))
    })

    await step('Select an integration', async () => {
      await userEvent.click(
        body.getByRole('menuitem', { name: /local baserow/i })
      )
      await expect(
        await body.findByRole('menuitem', { name: /get row/i })
      ).toBeInTheDocument()
    })

    await step('Select an action', async () => {
      await userEvent.click(
        await body.findByRole('menuitem', { name: /get row/i })
      )
      await expect(args.onChange).toHaveBeenCalledWith('get-row')
      await expect(args.onSelect).toHaveBeenCalledWith(
        expect.objectContaining({ value: 'get-row' })
      )
      await waitFor(() =>
        expect(canvas.getByTestId('selected-value')).toHaveTextContent(
          'Selected value: get-row'
        )
      )
      await waitFor(() =>
        expect(
          canvas.getByRole('button', { name: /get row/i })
        ).toHaveAttribute('aria-expanded', 'false')
      )
    })
  },
}

export const DisabledOption = {
  args: {
    onDisabledClick: fn(),
  },
  render: renderDropdown,
  play: async ({ args, canvas, step, userEvent }) => {
    const body = within(document.body)
    const trigger = canvas.getByRole('button', {
      name: /choose an action/i,
    })

    await step('Keep the dropdown open after a disabled click', async () => {
      await userEvent.click(trigger)
      await userEvent.click(body.getByRole('menuitem', { name: /^other$/i }))
      await userEvent.click(
        body.getByRole('menuitem', { name: /execute code/i })
      )
      await expect(args.onDisabledClick).toHaveBeenCalledWith(
        expect.objectContaining({ value: 'execute-code' })
      )
      await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    })

    await step('Close the menu with Escape', async () => {
      await userEvent.keyboard('{Escape}')
      await waitFor(() =>
        expect(trigger).toHaveAttribute('aria-expanded', 'false')
      )
    })
  },
}

export const Disabled = {
  args: {
    disabled: true,
  },
  render: renderDropdown,
  play: async ({ canvas }) => {
    await expect(
      canvas.getByRole('button', { name: /choose an action/i })
    ).toBeDisabled()
  },
}

export const Error = {
  args: {
    error: true,
  },
  render: renderDropdown,
}

export const Large = {
  args: {
    size: 'large',
  },
  render: renderDropdown,
}
