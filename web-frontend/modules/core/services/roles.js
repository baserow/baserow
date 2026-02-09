export default (client, $hasFeature, $registry) => {
  return {
    // TODO implement once endpoint exists
    get(workspace) {
      return {
        data: Object.values($registry.getAll('roles')).map((role) => ({
          uid: role.getUid(),
          description: role.getDescription(),
          showIsBillable: role.showIsBillable(workspace.id),
          isBillable: role.getIsBillable(),
          isVisible: role.isVisible(workspace.id),
          isDeactivated: role.isDeactivated(workspace.id),
          allowedScopeTypes: role.allowedScopeTypes,
          allowedSubjectTypes: role.allowedSubjectTypes,
        })),
      }
    },
  }
}
