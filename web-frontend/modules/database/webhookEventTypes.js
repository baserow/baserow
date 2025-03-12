import { Registerable } from '@baserow/modules/core/registry'

export class WebhookEventType extends Registerable {
  getName() {
    throw new Error('The name of an exporter type must be set.')
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type name of an webhook event type must be set.')
    }
  }

  serialize() {
    return {
      type: this.type,
    }
  }

  /**
   * Should return an object containing an example of the webhook event type payload.
   */
  getExamplePayload(database, table, rowExample) {
    return {
      table_id: table.id,
      database_id: table.database_id,
      workspace_id: database.workspace.id,
      event_id: '00000000-0000-0000-0000-000000000000',
      event_type: this.getType(),
    }
  }

  /**
   * If `true`, then a dropdown will be shown next to the field type allowing the user
   * to choose related fields. This can for example for an event that's restricted to
   * certain field updates.
   */
  getHasRelatedFields() {
    return false
  }

  getRelatedFieldsPlaceholder() {
    return null
  }

  getRelatedFieldsHelpText() {
    return null
  }

  /**
   * If `true`, then a dropdown will be shown next to the webhook type allowing the user
   * to choose related views. This can for example for an event that's restricted to
   * certain view updates.
   */
  getHasRelatedView() {
    return false
  }

  getRelatedViewPlaceholder() {
    return null
  }

  getRelatedViewHelpText() {
    return null
  }

  getDeactivatedText() {
    return ''
  }

  getDeactivatedClickModal() {
    return null
  }

  isDeactivated(workspaceId) {
    return false
  }

  getFeatureName() {
    return ''
  }
}

export class RowsCreatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'rows.created'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.rowsCreated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.items = [rowExample]
    return payload
  }
}

export class RowsUpdatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'rows.updated'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.rowsUpdated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.items = [rowExample]
    payload.old_items = [rowExample]
    return payload
  }

  getHasRelatedFields() {
    return true
  }

  getRelatedFieldsPlaceholder() {
    const { i18n } = this.app
    return i18n.t('webhookForm.triggerWhenFieldsHaveChanged')
  }

  getRelatedFieldsHelpText() {
    const { i18n } = this.app
    return i18n.t('webhookForm.helpTriggerWhenFieldsHaveChanged')
  }
}

export class RowsDeletedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'rows.deleted'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.rowsDeleted')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.row_ids = [rowExample.id]
    return payload
  }
}

// Unfortunately, we don't have an example of the field object in the web-frontend, so
// we would need to hardcode it here.
const fieldExample = {
  id: 1,
  table_id: 1,
  name: 'Field',
  order: 0,
  type: 'text',
  primary: false,
  read_only: false,
  description: '',
}

export class FieldCreatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'field.created'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.fieldCreated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.field = fieldExample
    return payload
  }
}

export class FieldUpdatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'field.updated'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.fieldUpdated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.field = fieldExample
    return payload
  }
}

export class FieldDeletedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'field.deleted'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.fieldDeleted')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.field_id = 1
    return payload
  }
}

// Unfortunately, we don't have an example of the field object in the web-frontend, so
// we would need to hardcode it here.
export const viewExample = {
  id: 0,
  table_id: 0,
  name: 'View',
  order: 1,
  type: 'grid',
  table: {
    id: 0,
    order: 1,
    name: 'Table',
    database_id: 0,
  },
  filter_type: 'AND',
  filters_disabled: false,
  public_view_has_password: false,
  show_logo: true,
  ownership_type: 'collaborative',
  owned_by_id: null,
  row_identifier_type: 'id',
  public: false,
}

export class ViewCreatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'view.created'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.viewCreated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.view = viewExample
    return payload
  }
}

export class ViewUpdatedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'view.updated'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.viewUpdated')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.view = viewExample
    return payload
  }
}

export class ViewDeletedWebhookEventType extends WebhookEventType {
  static getType() {
    return 'view.deleted'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.eventType.viewDeleted')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.view_id = 1
    return payload
  }
}
