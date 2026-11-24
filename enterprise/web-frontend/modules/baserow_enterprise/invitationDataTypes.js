import { InvitationDataType } from '@baserow/modules/core/invitationDataTypes'

const SCOPE_TYPE_LABELS = {
  application: 'invitationDataType.scopeTypeApplication',
  database_table: 'invitationDataType.scopeTypeTable',
  database_view: 'invitationDataType.scopeTypeView',
}

/**
 * The applications, tables and views a pending invitation grants a role on.
 */
export class ScopesInvitationDataType extends InvitationDataType {
  static getType() {
    return 'scopes'
  }

  getOrder() {
    return 10
  }

  getTargets(workspace, invitation) {
    return (invitation[this.type] || []).map((scope) => ({
      name: scope.name,
      description: this.$t('invitationDataType.scopeTarget', {
        name: scope.name,
        type: this.$t(
          SCOPE_TYPE_LABELS[scope.scope_type] ??
            'invitationDataType.scopeTypeOther'
        ),
        role:
          workspace._.roles.find(({ uid }) => uid === scope.role)?.name ??
          scope.role,
      }),
    }))
  }
}

/**
 * The teams a pending invitation adds the person to.
 */
export class TeamsInvitationDataType extends InvitationDataType {
  static getType() {
    return 'teams'
  }

  getOrder() {
    return 20
  }

  getTargets(workspace, invitation) {
    return (invitation[this.type] || []).map((team) => ({
      name: team.name,
      description: this.$t('invitationDataType.teamTarget', {
        name: team.name,
      }),
    }))
  }
}
