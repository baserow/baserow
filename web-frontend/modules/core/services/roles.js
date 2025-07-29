export default (client, $hasFeature, $registry) => {
  return {
    // TODO implement once endpoint exists
    get(workspace) {
      return {
        data: Object.values($registry.getAll('roles')).map((role) =>
          role.getUid() === 'NO_ROLE_LOW_PRIORITY'
            ? {
                uid: role.getUid(),
                description: role.getDescription(),
                showIsBillable: role.showIsBillable(workspace.id),
                isBillable: role.getIsBillable(),
                isVisible: role.isVisible(workspace.id),
                isDeactivated: role.isDeactivated(workspace.id),
                allowed_scope_types: ['workspace'],
                allowed_subject_types: ['auth.User'],
              }
            : {
                uid: role.getUid(),
                description: role.getDescription(),
                showIsBillable: role.showIsBillable(workspace.id),
                isBillable: role.getIsBillable(),
                isVisible: role.isVisible(workspace.id),
                isDeactivated: role.isDeactivated(workspace.id),
              }
        ),
      }
    },
  }
}
