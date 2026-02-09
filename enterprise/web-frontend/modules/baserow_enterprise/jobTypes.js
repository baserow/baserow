import { JobType } from '@baserow/modules/core/jobTypes'

export class AuditLogExportJobType extends JobType {
  static getType() {
    return 'audit_log_export'
  }

  getName() {
    return 'audit_log_export'
  }
}
