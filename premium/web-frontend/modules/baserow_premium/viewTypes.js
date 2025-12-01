import {
  BaseBufferedRowViewTypeMixin,
  maxPossibleOrderValue,
  ViewType,
} from '@baserow/modules/database/viewTypes'
import { SingleSelectFieldType } from '@baserow/modules/database/fieldTypes'
import KanbanView from '@baserow_premium/components/views/kanban/KanbanView'
import CalendarView from '@baserow_premium/components/views/calendar/CalendarView'
import TimelineView from '@baserow_premium/components/views/timeline/TimelineView'
import KanbanViewHeader from '@baserow_premium/components/views/kanban/KanbanViewHeader'
import CalendarViewHeader from '@baserow_premium/components/views/calendar/CalendarViewHeader'
import TimelineViewHeader from '@baserow_premium/components/views/timeline/TimelineViewHeader'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { isAdhocFiltering } from '@baserow/modules/database/utils/view'
import CalendarCreateIcalSharedViewLink from '@baserow_premium/components/views/calendar/CalendarCreateIcalSharedViewLink'
import CalendarSharingIcalSlugSection from '@baserow_premium/components/views/calendar/CalendarSharingIcalSlugSection'
import {
  getDateField,
  dateSettinsAreValid,
} from '@baserow_premium/utils/timeline'
import {
  CalendarViewPaidFeature,
  KanbanViewPaidFeature,
  TimelineViewPaidFeature,
} from '@baserow_premium/paidFeatures'
import { waitFor } from '@baserow/modules/core/utils/queue'

class PremiumViewType extends ViewType {
  getDeactivatedText() {
    return this.app.i18n.t('premium.deactivated')
  }

  getDeactivatedClickModal() {
    return [PaidFeaturesModal, {}]
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(PremiumFeatures.PREMIUM, workspaceId)
  }

  getAdditionalShareLinkOptions() {
    return []
  }
}

export class KanbanViewType extends PremiumViewType {
  static getType() {
    return 'kanban'
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': KanbanViewPaidFeature.getType() },
    ]
  }

  getIconClass() {
    return 'baserow-icon-kanban'
  }

  getColorClass() {
    return 'color-success'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('premium.viewType.kanban')
  }

  canFilter() {
    return true
  }

  canSort() {
    return false
  }

  canShare() {
    return true
  }

  canShowRowModal() {
    return true
  }

  getPublicRoute() {
    return 'database-public-kanban-view'
  }

  getHeaderComponent() {
    return KanbanViewHeader
  }

  getComponent() {
    return KanbanView
  }

  async fetch({ store }, database, view, fields, storePrefix = '') {
    const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
    const adhocFiltering = isAdhocFiltering(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    // If the single select field is `null` we can't fetch the initial data anyway,
    // we don't have to do anything. The KanbanView component will handle it by
    // showing a form to choose or create a single select field.
    if (view.single_select_field === null) {
      await store.dispatch(storePrefix + 'view/kanban/reset')
    } else {
      await store.dispatch(storePrefix + 'view/kanban/fetchInitial', {
        kanbanId: view.id,
        singleSelectFieldId: view.single_select_field,
        adhocFiltering,
      })
    }
  }

  async refresh(
    { store },
    database,
    view,
    fields,
    storePrefix = '',
    includeFieldOptions = false,
    sourceEvent = null
  ) {
    const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
    const adhocFiltering = isAdhocFiltering(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    try {
      await store.dispatch(storePrefix + 'view/kanban/fetchInitial', {
        kanbanId: view.id,
        singleSelectFieldId: view.single_select_field,
        includeFieldOptions,
        adhocFiltering,
      })
    } catch (error) {
      if (
        error.handler.code === 'ERROR_KANBAN_VIEW_HAS_NO_SINGLE_SELECT_FIELD'
      ) {
        store.dispatch(storePrefix + 'view/kanban/reset')
      } else {
        throw error
      }
    }
  }

  async fieldOptionsUpdated({ store }, view, fieldOptions, storePrefix) {
    await store.dispatch(
      storePrefix + 'view/kanban/forceUpdateAllFieldOptions',
      fieldOptions,
      {
        root: true,
      }
    )
  }

  updated(context, view, oldView, storePrefix) {
    // If the single select field has changed, we want to trigger a refresh of the
    // page by returning true.
    return view.single_select_field !== oldView.single_select_field
  }

  async rowCreated(
    { store },
    tableId,
    fields,
    values,
    metadata,
    storePrefix = ''
  ) {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(storePrefix + 'view/kanban/createdNewRow', {
        view: store.getters['view/getSelected'],
        values,
        fields,
      })
    }
  }

  async rowUpdated(
    { store },
    tableId,
    fields,
    row,
    values,
    metadata,
    updatedFieldIds,
    storePrefix = ''
  ) {
    if (this.isCurrentView(store, tableId)) {
      try {
        // A realtime row update signal can be received before the rows are created.
        // In that case, there is a race condition because the row doesn't have the
        // ID yet, so it can't be updated. This can be resolved by waiting all rows
        // to be created.
        await waitFor(
          () => !store.getters[storePrefix + 'view/kanban/getCreating']
        )
      } catch (error) {
        // If the timeout is reached, then just continue with the update because the
        // realtime update must come through eventually, otherwise the page is not
        // up to date.
      }
      await store.dispatch(storePrefix + 'view/kanban/updatedExistingRow', {
        view: store.getters['view/getSelected'],
        fields,
        row,
        values,
      })
    }
  }

  async rowDeleted({ store }, tableId, fields, row, storePrefix = '') {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(storePrefix + 'view/kanban/deletedExistingRow', {
        view: store.getters['view/getSelected'],
        row,
        fields,
      })
    }
  }

  async afterFieldCreated(
    { dispatch },
    table,
    field,
    fieldType,
    storePrefix = ''
  ) {
    const value = fieldType.getDefaultValue(field)
    await dispatch(
      storePrefix + 'view/kanban/addField',
      { field, value },
      { root: true }
    )
    await dispatch(
      storePrefix + 'view/kanban/setFieldOptionsOfField',
      {
        field,
        // The default values should be the same as in the `KanbanViewFieldOptions`
        // model in the backend to stay consistent.
        values: {
          hidden: true,
          order: maxPossibleOrderValue,
        },
      },
      { root: true }
    )
  }

  afterFieldUpdated(context, field, oldField, fieldType, storePrefix) {
    // Make sure that all Kanban views don't depend on fields that
    // have been converted to another type
    const type = SingleSelectFieldType.getType()
    if (oldField.type === type && field.type !== type) {
      this._setFieldToNull(context, field, 'single_select_field')
      this._setFieldToNull(context, field, 'card_cover_image_field')
    }
  }

  afterFieldDeleted(context, field, fieldType, storePrefix = '') {
    // Make sure that all Kanban views don't depend on fields that
    // have been deleted
    this._setFieldToNull(context, field, 'single_select_field')
    this._setFieldToNull(context, field, 'card_cover_image_field')
  }
}

export class CalendarViewType extends PremiumViewType {
  static getType() {
    return 'calendar'
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': CalendarViewPaidFeature.getType() },
    ]
  }

  getIconClass() {
    return 'baserow-icon-calendar'
  }

  getColorClass() {
    return 'color-success'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('premium.viewType.calendar')
  }

  canFilter() {
    return true
  }

  canSort() {
    return false
  }

  canShare() {
    return true
  }

  canShowRowModal() {
    return true
  }

  getPublicRoute() {
    return 'database-public-calendar-view'
  }

  getHeaderComponent() {
    return CalendarViewHeader
  }

  getComponent() {
    return CalendarView
  }

  async fetch({ store }, database, view, fields, storePrefix = '') {
    const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
    const adhocFiltering = isAdhocFiltering(
      this.app,
      database.workspace,
      view,
      isPublic
    )

    await store.dispatch(storePrefix + 'view/calendar/resetAndFetchInitial', {
      calendarId: view.id,
      dateFieldId: view.date_field,
      fields,
      adhocFiltering,
    })
  }

  async refresh(
    { store },
    database,
    view,
    fields,
    storePrefix = '',
    includeFieldOptions = false,
    sourceEvent = null
  ) {
    // We need to prevent multiple requests as updates and deletes regarding
    // the date field are handled inside afterFieldUpdated and afterFieldDeleted
    const dateFieldId =
      store.getters[storePrefix + 'view/calendar/getDateFieldIdIfNotTrashed'](
        fields
      )
    if (
      ['field_deleted', 'field_updated'].includes(sourceEvent?.type) &&
      sourceEvent?.data?.field_id === dateFieldId
    ) {
      return
    }
    const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
    const adhocFiltering = isAdhocFiltering(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    await store.dispatch(storePrefix + 'view/calendar/refreshAndFetchInitial', {
      calendarId: view.id,
      dateFieldId: view.date_field,
      fields,
      includeFieldOptions,
      adhocFiltering,
    })
  }

  async fieldOptionsUpdated({ store }, view, fieldOptions, storePrefix) {
    await store.dispatch(
      storePrefix + 'view/calendar/forceUpdateAllFieldOptions',
      fieldOptions,
      {
        root: true,
      }
    )
  }

  updated(context, view, oldView, storePrefix) {
    return view.date_field !== oldView.date_field
  }

  async rowCreated(
    { store },
    tableId,
    fields,
    values,
    metadata,
    storePrefix = ''
  ) {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(storePrefix + 'view/calendar/createdNewRow', {
        view: store.getters['view/getSelected'],
        values,
        fields,
      })
    }
  }

  async rowUpdated(
    { store },
    tableId,
    fields,
    row,
    values,
    metadata,
    updatedFieldIds,
    storePrefix = ''
  ) {
    if (this.isCurrentView(store, tableId)) {
      try {
        // A realtime row update signal can be received before the rows are created.
        // In that case, there is a race condition because the row doesn't have the
        // ID yet, so it can't be updated. This can be resolved by waiting all rows
        // to be created.
        await waitFor(
          () => !store.getters[storePrefix + 'view/calendar/getCreating']
        )
      } catch (error) {
        // If the timeout is reached, then just continue with the update because the
        // realtime update must come through eventually, otherwise the page is not
        // up to date.
      }
      await store.dispatch(storePrefix + 'view/calendar/updatedExistingRow', {
        view: store.getters['view/getSelected'],
        fields,
        row,
        values,
      })
    }
  }

  async rowDeleted({ store }, tableId, fields, row, storePrefix = '') {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(storePrefix + 'view/calendar/deletedExistingRow', {
        view: store.getters['view/getSelected'],
        row,
        fields,
      })
    }
  }

  async afterFieldCreated(
    { dispatch },
    table,
    field,
    fieldType,
    storePrefix = ''
  ) {
    const value = fieldType.getDefaultValue(field)
    await dispatch(
      storePrefix + 'view/calendar/addField',
      { field, value },
      { root: true }
    )
    await dispatch(
      storePrefix + 'view/calendar/setFieldOptionsOfField',
      {
        field,
        // The default values should be the same as in the `CalendarViewFieldOptions`
        // model in the backend to stay consistent.
        values: {
          hidden: true,
          order: maxPossibleOrderValue,
        },
      },
      { root: true }
    )
  }

  async afterFieldUpdated(context, field, oldField, fieldType, storePrefix) {
    const fields = [field]
    const dateFieldId =
      context.rootGetters[
        storePrefix + 'view/calendar/getDateFieldIdIfNotTrashed'
      ](fields)

    if (dateFieldId === field.id) {
      const type = this.app.$registry.get('field', field.type)
      if (!type.canRepresentDate(field)) {
        this._setFieldToNull(context, field, 'date_field')
        await context.dispatch(
          storePrefix + 'view/calendar/reset',
          {},
          { root: true }
        )
      } else {
        await context.dispatch(
          storePrefix + 'view/calendar/fetchInitial',
          {
            includeFieldOptions: false,
            fields,
          },
          { root: true }
        )
      }
    }
  }

  async afterFieldDeleted(context, field, fieldType, storePrefix = '') {
    const fields = [field]
    this._setFieldToNull(context, field, 'date_field')
    const dateFieldId =
      context.rootGetters[
        storePrefix + 'view/calendar/getDateFieldIdIfNotTrashed'
      ](fields)
    if (dateFieldId === field.id) {
      await context.dispatch(
        storePrefix + 'view/calendar/reset',
        {},
        { root: true }
      )
    }
  }

  getAdditionalCreateShareLinkOptions() {
    return [CalendarCreateIcalSharedViewLink]
  }

  getAdditionalDisableSharedLinkOptions() {
    return [CalendarCreateIcalSharedViewLink]
  }

  getAdditionalSharingSections() {
    return [CalendarSharingIcalSlugSection]
  }

  getSharedViewText() {
    return this.app.i18n.t('calendarViewType.sharedViewText')
  }

  isShared(view) {
    return !!view.public || !!view.ical_public
  }

  populate(view) {
    Object.assign(view, {
      createShareViewText: this.getSharedViewText(),
    })

    return view
  }
}

export class TimelineViewType extends BaseBufferedRowViewTypeMixin(
  PremiumViewType
) {
  static getType() {
    return 'timeline'
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': TimelineViewPaidFeature.getType() },
    ]
  }

  canFetch({ app }, databse, view, fields) {
    const startFieldId = view.start_date_field
    const endFieldId = view.end_date_field
    const startField = getDateField(app.$registry, fields, startFieldId)
    const endField = getDateField(app.$registry, fields, endFieldId)
    return dateSettinsAreValid(startField, endField)
  }

  getIconClass() {
    return 'baserow-icon-timeline'
  }

  getColorClass() {
    return 'color-error'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('premium.viewType.timeline')
  }

  canFilter() {
    return true
  }

  canSort() {
    return true
  }

  canShare() {
    return true
  }

  canShowRowModal() {
    return true
  }

  getPublicRoute() {
    return 'database-public-timeline-view'
  }

  getHeaderComponent() {
    return TimelineViewHeader
  }

  getComponent() {
    return TimelineView
  }
}

Object.assign(TimelineViewType.prototype, PremiumViewType)
