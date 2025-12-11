import type { Meta, StoryObj } from '@storybook/vue3'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'

// Simplified mock data for demonstration
const mockNodesHierarchy = [
  {
    name: 'Data',
    type: 'data',
    identifier: null,
    icon: null,
    order: null,
    description: null,
    example: null,
    highlightingColor: null,
    nodes: [
      {
        name: 'User',
        type: 'data',
        identifier: 'user',
        icon: 'iconoir-question-mark',
        order: null,
        description: null,
        example: null,
        highlightingColor: null,
        signature: null,
        nodes: [
          {
            name: 'Email',
            type: 'data',
            identifier: 'email',
            description: null,
            icon: 'iconoir-text',
            highlightingColor: null,
            order: null,
            signature: null,
          },
        ],
      },
    ],
  },
  {
    name: 'Functions',
    type: 'function',
    identifier: null,
    order: null,
    signature: null,
    description: null,
    example: null,
    highlightingColor: null,
    icon: null,
    nodes: [
      {
        name: 'Text',
        identifier: null,
        order: null,
        signature: null,
        description: null,
        example: null,
        highlightingColor: null,
        icon: null,
        nodes: [
          {
            name: 'concat',
            type: 'function',
            description: 'Concatenates multiple text values together',
            example: "concat('Hello', ' ', 'World')",
            highlightingColor: 'blue',
            icon: 'iconoir-text',
            identifier: null,
            order: null,
            signature: {
              parameters: [
                {
                  type: 'string',
                  required: true,
                },
              ],
              variadic: true,
              minArgs: 1,
              maxArgs: null,
            },
          },
        ],
      },
    ],
  },
]

const meta = {
  title: 'Baserow/Form Elements/FormulaInputField',
  component: FormulaInputField,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'text',
    },
    placeholder: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    small: {
      control: 'boolean',
    },
    mode: {
      control: 'select',
      options: ['advanced', 'simple', 'raw'],
    },
    loading: {
      control: 'boolean',
    },
    contextPosition: {
      control: 'select',
      options: ['bottom', 'left', 'right'],
    },
    readOnly: {
      control: 'boolean',
    },
  },
  args: {
    value: '',
    placeholder: 'Enter a formula...',
    disabled: false,
    small: false,
    mode: 'advanced',
    loading: false,
    contextPosition: 'bottom',
    readOnly: false,
  },
  parameters: {
    backgrounds: {
      default: 'light',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/design/pARSkP8ldSqMVxV1t2gYYT/Application-builder?node-id=1314-35740&m=dev',
    },
  },
} satisfies Meta<typeof FormulaInputField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { FormulaInputField },
    setup() {
      return { args, mockNodesHierarchy }
    },
    template: `
      <div style="padding: 20px; max-width: 600px;">
        <FormulaInputField
          v-bind="args"
          :nodes-hierarchy="mockNodesHierarchy"
        />
      </div>
    `,
  }),
}
