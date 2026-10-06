/** Icons shared by the management tables and workspace role selector. */
export function getRoleIcon(uid) {
  return (
    {
      ADMIN: 'iconoir-crown',
      MEMBER: 'iconoir-group',
      BUILDER: 'iconoir-tools',
      EDITOR: 'iconoir-edit-pencil',
      COMMENTER: 'iconoir-chat-bubble',
      VIEWER: 'iconoir-eye-empty',
      NO_ACCESS: 'iconoir-eye-off',
      NO_ROLE: 'iconoir-minus',
    }[uid] || 'iconoir-shield'
  )
}
