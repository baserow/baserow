describe('Enterprise builder element types', () => {
  test('file input deactivation checks tolerate a missing workspace', () => {
    const testApp = useNuxtApp()
    const elementType = testApp.$registry.get('element', 'input_file')

    expect(elementType.isDeactivatedReason({ workspace: undefined })).toBeNull()
    expect(elementType.getDeactivatedClickModal({ workspace: undefined })).toBe(
      null
    )
  })
})

describe('Enterprise automation and workflow action types', () => {
  test('code and xls deactivation modal checks tolerate a missing workspace', () => {
    const testApp = useNuxtApp()
    const codeNodeType = testApp.$registry.get('node', 'code')
    const xlsNodeType = testApp.$registry.get('node', 'xls_file_reader')
    const codeWorkflowActionType = testApp.$registry.get(
      'workflowAction',
      'code'
    )
    const xlsWorkflowActionType = testApp.$registry.get(
      'workflowAction',
      'xls_file_reader'
    )

    for (const type of [
      codeNodeType,
      xlsNodeType,
      codeWorkflowActionType,
      xlsWorkflowActionType,
    ]) {
      expect(type.isDeactivatedReason({ workspace: undefined })).toBeNull()
      expect(type.getDeactivatedClickModal({ workspace: undefined })).toBeNull()
    }
  })
})
