import BadgeCollaborator from '@baserow/modules/core/components/BadgeCollaborator'

export default {
  title: 'Baserow/BadgeCollaborator',
  component: BadgeCollaborator,
  tags: ['autodocs'],
  argTypes: {
    initials: {
      control: 'text',
      description: 'The initials to display in the avatar',
    },
    removeIcon: {
      control: 'boolean',
      description: 'Display a remove icon on the badge if true',
    },
    size: {
      control: 'select',
      options: ['regular', 'small'],
      description: 'The size of the badge',
    },
    default: {
      control: 'text',
      description: 'The label content (slot)',
    },
  },
  args: {
    initials: 'JD',
    removeIcon: false,
    size: 'regular',
  },
}

export const Default = {
  render: (args) => ({
    components: { BadgeCollaborator },
    setup() {
      return { args }
    },
    template: '<BadgeCollaborator v-bind="args">John Doe</BadgeCollaborator>',
  }),
}

export const WithRemoveIcon = {
  args: {
    removeIcon: true,
  },
  render: (args) => ({
    components: { BadgeCollaborator },
    setup() {
      const onRemove = () => alert('Remove clicked!')
      return { args, onRemove }
    },
    template:
      '<BadgeCollaborator v-bind="args" @remove="onRemove">Jane Smith</BadgeCollaborator>',
  }),
}

export const Small = {
  args: {
    size: 'small',
    initials: 'AB',
  },
  render: (args) => ({
    components: { BadgeCollaborator },
    setup() {
      return { args }
    },
    template: '<BadgeCollaborator v-bind="args">Alice Bob</BadgeCollaborator>',
  }),
}

export const AllVariations = {
  render: () => ({
    components: { BadgeCollaborator },
    template: `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <BadgeCollaborator initials="JD" size="regular">Regular</BadgeCollaborator>
          <BadgeCollaborator initials="SM" size="small">Small</BadgeCollaborator>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <BadgeCollaborator initials="RM" :remove-icon="true">Removable</BadgeCollaborator>
          <BadgeCollaborator initials="SR" size="small" :remove-icon="true">Small Removable</BadgeCollaborator>
        </div>
      </div>
    `,
  }),
}
