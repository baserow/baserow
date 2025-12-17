import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'

const mockNodesHierarchy = [
  {
    name: 'Fields',
    type: 'field',
    nodes: [
      {
        name: 'Name',
        identifier: 'field_1',
        type: 'field',
        icon: 'iconoir-text',
      },
      {
        name: 'Age',
        identifier: 'field_2',
        type: 'field',
        icon: 'iconoir-hashtag',
      },
    ],
  },
  {
    name: 'Functions',
    type: 'function',
    nodes: [
      {
        name: 'concat',
        description: 'Concatenate strings',
        type: 'function',
        icon: 'iconoir-text',
      },
      {
        name: 'upper',
        description: 'Convert to uppercase',
        type: 'function',
        icon: 'iconoir-text',
      },
    ],
  },
]

export default {
  title: 'Baserow/Form Elements/FormulaInputField',
  component: FormulaInputField,
  tags: ['autodocs'],
  argTypes: {
    value: {
      control: 'text',
      description: 'Formula value',
    },
    placeholder: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
  },
  args: {
    value: "concat('Hello', ' ', field('Name'))",
    placeholder: 'Enter formula...',
    disabled: false,
    loading: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/design/pARSkP8ldSqMVxV1t2gYYT/Application-builder?node-id=1314-35740&m=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { FormulaInputField },
    setup() {
      return { args, mockNodesHierarchy }
    },
    template: `
      <div style="padding: 20px; max-width: 600px; height: 300px;">
        <FormulaInputField
          v-bind="args"
          :nodes-hierarchy="mockNodesHierarchy"
        />
      </div>
    `,
  }),
}
