import { AllowIfTemplateOperationPermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

describe('AllowIfTemplateOperationPermissionManagerType', () => {
  const manager = new AllowIfTemplateOperationPermissionManagerType({})
  const permissions = {
    allowed_operations_on_templates: [
      'agent_application.read_configuration',
      'agent_application.read_conversations',
    ],
    official_template_only_operations: ['agent_application.read_conversations'],
    workspace_template_ids: [1, 2],
    user_template_workspace_ids: [2],
  }

  test('allows the template operations on an official template', () => {
    expect(
      manager.hasPermission(
        permissions,
        'agent_application.read_conversations',
        {},
        1
      )
    ).toBe(true)
  })

  test('leaves official-only operations on a user template to the next managers', () => {
    expect(
      manager.hasPermission(
        permissions,
        'agent_application.read_conversations',
        {},
        2
      )
    ).toBeUndefined()
    expect(
      manager.hasPermission(
        permissions,
        'agent_application.read_configuration',
        {},
        2
      )
    ).toBe(true)
  })
})
