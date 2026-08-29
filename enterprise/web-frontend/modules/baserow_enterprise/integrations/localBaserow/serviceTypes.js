import { LocalBaserowCreateRowWorkflowServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'

/**
 * The backend exposes creating and updating rows as one
 * `local_baserow_upsert_row` service type, but the core frontend only
 * registers the specialised `local_baserow_create_row` /
 * `local_baserow_update_row` service types on top of it. Agent action tools
 * store the backend service type name, so the upsert type needs a frontend
 * registration of its own. The create row workflow service type already uses
 * the upsert row form, which includes the optional row id.
 */
export class LocalBaserowUpsertRowServiceType extends LocalBaserowCreateRowWorkflowServiceType {
  static getType() {
    return 'local_baserow_upsert_row'
  }

  get name() {
    return this.app.$i18n.t('serviceType.localBaserowUpsertRow')
  }

  get description() {
    return this.app.$i18n.t('serviceType.localBaserowUpsertRowDescription')
  }
}
