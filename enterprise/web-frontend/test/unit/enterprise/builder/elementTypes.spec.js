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
