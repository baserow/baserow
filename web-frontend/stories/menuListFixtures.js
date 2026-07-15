export const menuListItems = [
  {
    id: 'repeat',
    label: 'Repeat',
    value: 'repeat',
    icon: 'iconoir-refresh',
    description: 'Run the following actions multiple times.',
    aliases: ['loop'],
    meta: { badge: 'Built-in' },
  },
  {
    id: 'create-row',
    label: 'Create row',
    value: 'create-row',
    icon: 'iconoir-plus',
    description: 'Add a new record to a table.',
    aliases: ['insert'],
    meta: { badge: 'Free' },
  },
  {
    id: 'get-row',
    label: 'Get row',
    value: 'get-row',
    icon: 'iconoir-pin',
    description: 'Retrieve a single record from a table.',
    aliases: ['find', 'read'],
    meta: { badge: 'Free' },
  },
  {
    id: 'update-row',
    label: 'Update row',
    value: 'update-row',
    icon: 'iconoir-edit-pencil',
    description: 'Change the values of an existing record.',
    aliases: ['edit'],
    meta: { badge: 'Free' },
  },
  {
    id: 'delete-row',
    label: 'Delete row',
    value: 'delete-row',
    icon: 'iconoir-bin',
    description: 'Remove a record from a table.',
    aliases: ['remove'],
    meta: { badge: 'Free' },
  },
  {
    id: 'send-email',
    label: 'Send email',
    value: 'send-email',
    icon: 'iconoir-mail',
    description: 'Send a transactional email.',
    aliases: ['message'],
    meta: { badge: 'Premium' },
  },
  {
    id: 'execute-code',
    label: 'Execute code',
    value: 'execute-code',
    icon: 'iconoir-code-brackets',
    description: 'Run custom code as part of the flow.',
    disabled: true,
    disabledReason: 'Available with an Advanced plan.',
    meta: { badge: 'Advanced' },
  },
]

export const compactMenuListItems = [
  {
    id: 'open-page',
    label: 'Open page',
    value: 'open-page',
    icon: 'iconoir-empty-page',
  },
  {
    id: 'refresh-data',
    label: 'Refresh data',
    value: 'refresh-data',
    icon: 'iconoir-refresh',
  },
  {
    id: 'start-workflow',
    label: 'Start workflow',
    value: 'start-workflow',
    icon: 'iconoir-play',
  },
  {
    id: 'delete-record',
    label: 'Delete record',
    value: 'delete-record',
    icon: 'iconoir-bin',
  },
]

export const multiStageDropdownItems = [
  {
    id: 'local-baserow',
    label: 'Local Baserow',
    icon: 'iconoir-database',
    children: menuListItems.filter(({ id }) =>
      ['create-row', 'get-row', 'update-row', 'delete-row'].includes(id)
    ),
  },
  {
    id: 'external-baserow',
    label: 'External Baserow (API)',
    icon: 'iconoir-globe',
    children: [
      {
        id: 'send-http-request',
        label: 'Send HTTP request',
        value: 'send-http-request',
        icon: 'iconoir-globe',
        description: 'Send a request to an external Baserow API.',
      },
    ],
  },
  {
    id: 'slack',
    label: 'Slack',
    icon: 'iconoir-mail',
    children: [
      {
        id: 'send-slack-message',
        label: 'Send Slack message',
        value: 'send-slack-message',
        icon: 'iconoir-mail',
        description: 'Send a message to a Slack channel.',
      },
    ],
  },
  {
    id: 'other',
    label: 'Other',
    icon: 'iconoir-plus',
    children: menuListItems.filter(({ id }) =>
      ['repeat', 'execute-code'].includes(id)
    ),
  },
]
