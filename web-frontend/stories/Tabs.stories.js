import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'

export default {
  title: 'Baserow/Tabs',
  component: Tabs,
  tags: ['autodocs'],
  argTypes: {
    selectedIndex: {
      control: 'number',
      description: 'Index of the selected tab',
    },
    fullHeight: {
      control: 'boolean',
    },
    large: {
      control: 'boolean',
    },
    largeOffset: {
      control: 'boolean',
    },
  },
  args: {
    selectedIndex: 0,
    fullHeight: false,
    large: false,
    largeOffset: false,
  },
}

export const Default = {
  render: (args) => ({
    components: { Tabs, Tab },
    setup() {
      return { args }
    },
    template: `
      <Tabs v-bind="args">
        <Tab title="Account">
          <div style="padding: 20px;">Account Settings Content</div>
        </Tab>
        <Tab title="Security">
          <div style="padding: 20px;">Security Settings Content</div>
        </Tab>
        <Tab title="Notifications">
          <div style="padding: 20px;">Notification Preferences</div>
        </Tab>
        <Tab title="Disabled" disabled>
          <div style="padding: 20px;">This content is disabled</div>
        </Tab>
      </Tabs>
    `,
  }),
}

export const WithIcons = {
  render: (args) => ({
    components: { Tabs, Tab },
    setup() {
      return { args }
    },
    template: `
      <Tabs v-bind="args">
        <Tab title="Home" icon="iconoir-home">
          <div style="padding: 20px;">Home Content</div>
        </Tab>
        <Tab title="Profile" icon="iconoir-user">
          <div style="padding: 20px;">Profile Content</div>
        </Tab>
        <Tab title="Settings" icon="iconoir-settings">
          <div style="padding: 20px;">Settings Content</div>
        </Tab>
      </Tabs>
    `,
  }),
}
