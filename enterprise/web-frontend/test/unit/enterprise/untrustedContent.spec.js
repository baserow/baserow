import { CoreCodeActionNodeType } from '@baserow_enterprise/automation/nodeTypes'
import { CoreCodeWorkflowActionType } from '@baserow_enterprise/builder/workflowActionTypes'
import { NodeType } from '@baserow/modules/automation/nodeTypes'
import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'

test('code nodes show a trust error only for their own workflow', () => {
  const type = new CoreCodeActionNodeType({ app: useNuxtApp() })
  const valid = vi.spyOn(NodeType.prototype, 'isInError').mockReturnValue(false)
  const message = vi
    .spyOn(NodeType.prototype, 'getErrorMessage')
    .mockReturnValue(null)
  const workflow = { untrusted_content: true }
  expect(type.isInError({ workflow })).toBe(true)
  expect(type.getErrorMessage({ workflow })).toBe(
    'automationHeader.untrustedContentWarning'
  )
  expect(type.isInError({ workflow: { untrusted_content: false } })).toBe(false)
  workflow.untrusted_content = false
  expect(type.isInError({ workflow })).toBe(false)
  expect(type.getErrorMessage({ workflow })).toBeNull()
  valid.mockRestore()
  message.mockRestore()
})

test('Builder code actions clear their trust error after confirmation', () => {
  const type = new CoreCodeWorkflowActionType({ app: useNuxtApp() })
  const valid = vi
    .spyOn(WorkflowActionServiceType.prototype, 'getErrorMessage')
    .mockReturnValue(null)
  const context = { builder: { untrusted_content: true } }
  expect(type.isInError({}, context)).toBe(true)
  expect(type.getErrorMessage({}, context)).toBe(
    'builderUntrustedContent.warning'
  )
  context.builder.untrusted_content = false
  expect(type.isInError({}, context)).toBe(false)
  valid.mockRestore()
})
