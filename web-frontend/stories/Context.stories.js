import Context from '@baserow/modules/core/components/Context'

export default {
  title: 'Baserow/Context',
  component: Context,
  tags: ['autodocs'],
  argTypes: {
    overflowScroll: {
      control: 'boolean',
      description: 'Enable scroll if content overflows',
    },
    maxHeight: {
      control: 'boolean',
      description: 'Limit max height',
    },
  },
  args: {
    overflowScroll: false,
    maxHeight: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { Context },
    setup() {
      return { args }
    },
    template: `
      <div style="position: relative; height: 200px; border: 1px dashed #ccc; padding: 20px;">
        <Context v-bind="args">
          <ul style="list-style: none; padding: 10px; margin: 0;">
            <li style="padding: 5px 0;">Menu Item 1</li>
            <li style="padding: 5px 0;">Menu Item 2</li>
            <li style="padding: 5px 0;">Menu Item 3</li>
          </ul>
        </Context>
      </div>
    `,
  }),
}
