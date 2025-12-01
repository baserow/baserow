import { Registerable } from '@baserow/modules/core/registry'
import ViewForm from '@baserow/modules/database/components/view/ViewForm'
import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewHeader from '@baserow/modules/database/components/view/grid/GridViewHeader'
import GalleryView from '@baserow/modules/database/components/view/gallery/GalleryView'
import GalleryViewHeader from '@baserow/modules/database/components/view/gallery/GalleryViewHeader'
import FormView from '@baserow/modules/database/components/view/form/FormView'
import FormViewHeader from '@baserow/modules/database/components/view/form/FormViewHeader'
import { FileFieldType } from '@baserow/modules/database/fieldTypes'
import {
  filterVisibleFieldsFunction,
  isAdhocFiltering,
  isAdhocSorting,
  newFieldMatchesActiveSearchTerm,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'
import { clone } from '@baserow/modules/core/utils/object'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'
import { GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING } from '@baserow/modules/database/constants'
import { waitFor } from '@baserow/modules/core/utils/queue'

export const maxPossibleOrderValue = 32767

export class ViewType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize certain view types. If you for example want the database
   * icon, you must return 'database' here. This will result in the classname
   * 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * The color class that is added to the icon.
   */
  getColorClass() {
    return 'color-primary'
  }

  /**
   * A human readable name of the view type.
   */
  getName() {
    return null
  }

  /**
   * Indicates whether it is possible to filter the rows. If true the filter context
   * menu is added to the header.
   */
  canFilter() {
    return true
  }

  /**
   * Indicates whether it is possible to sort the rows. If true the sort context menu
   * is added to the header.
   */
  canSort() {
    return true
  }

  /**
   * Indicates whether it is possible to group the rows. If true the group by context
   * menu is added to the header.
   */
  canGroupBy() {
    return false
  }

  /**
   * Indicates whether it is possible to share this view via an url publically.
   */
  canShare() {
    return false
  }

  /**
   * Indicates whether it is possible to show a modal when clicking on a row.
   */
  canShowRowModal() {
    return false
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()
    this.colorClass = this.getColorClass()
    this.canFilter = this.canFilter()
    this.canSort = this.canSort()
    this.canGroupBy = this.canGroupBy()
    this.canShare = this.canShare()

    if (this.type === null) {
      throw new Error('The type name of a view type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of a view type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a view type must be set.')
    }
  }

  /**
   * The form component that will be rendered when creating a new instance of
   * this view type. By default the ViewForm component is returned, but this
   * only contains a name field. If custom fields are required upon creating
   * they can be added by replacing this component with a custom oone.
   */
  getViewFormComponent() {
    return ViewForm
  }

  /**
   * Should return the component that will actually display the view.
   */
  getComponent() {
    throw new Error(
      'Not implemented error. This view should return a component.'
    )
  }

  /**
   * Should return a route name that will display the view when it has been
   * publicly shared.
   */
  getPublicRoute() {
    throw new Error(
      'Not implemented error. This method should be implemented to return a route' +
        ' name to a public page where the view can be seen.'
    )
  }

  /**
   * A human readable name of the view type to be used in the ShareViewLink and
   * related components. For example the link to share to view will have the text:
   * `Share {this.getSharingLinkName()}`
   */
  getSharingLinkName() {
    const { i18n } = this.app
    return i18n.t('viewType.sharing.linkName')
  }

  /**
   * Should return the component that will be displayed in the header when the
   * view is selected. Extra options like filters and sorting could be added
   * here.
   */
  getHeaderComponent(view) {
    return null
  }

  /**
   * Optionally add additional class names to the header element.
   */
  getHeaderClassNames() {
    return ''
  }

  /**
   * Every time a fresh view object is fetched from the backend, it will be
   * populated, this is the moment to update some values. Because each view type
   * can have unique properties, they might need to be populated. This method
   * can be overwritten in order the populate the correct values.
   */
  populate(view) {
    return view
  }

  /**
   * Indicates whether of nor the provided table id has this current view type
   * selected. Because every view type has it's own store, this check can be used to
   * check if the state of that store has to be updated.
   */
  isCurrentView(store, tableId) {
    const table = store.getters['table/getSelected']
    const view = store.getters['view/getSelected']
    return (
      table.id === tableId &&
      Object.prototype.hasOwnProperty.call(view, 'type') &&
      view.type === this.getType()
    )
  }

  /**
   * Returns true if view is already configured to be shared. This may be just
   * a public flag state or more complex per-view calculation
   */
  isShared(view) {
    return !!view.public
  }

  /**
   * The fetch method is called inside the asyncData function when the table page
   * loads with a selected view. It is possible to fill some stores serverside here.
   */
  fetch() {}

  /**
   * Should refresh the data inside a view. This is method could be called when a filter
   * or sort has been changed or when a field is updated or deleted. It should keep the
   * state as much the same as it was before. So for example the scroll offset should
   * stay the same if possible. Can throw a RefreshCancelledException when the view
   * wishes to cancel the current refresh call due to a new refresh call.
   */
  refresh(
    context,
    database,
    view,
    fields,
    storePrefix = '',
    includeFieldOptions = false,
    sourceEvent = null
  ) {}

  /**
   * Should return true if the view must be refreshed when a new field has been
   * created. This could for example be used to check whether the empty value matches
   * the active search term.
   */
  shouldRefreshWhenFieldCreated(registry, store, field, storePrefix) {
    return false
  }

  /**
   * Method that is called when a field has been created. This can be useful to
   * maintain data integrity for example to add the field to the grid view store.
   */
  afterFieldCreated(context, table, field, fieldType, storePrefix) {}

  /**
   * Method that is called when a field has been restored . This can be useful to
   * maintain data integrity for example to add the field to the grid view store.
   */
  fieldRestored(context, table, selectedView, field, fieldType, storePrefix) {}

  /**
   * Method that is called when a field has been deleted. This can be useful to
   * maintain data integrity.
   */
  afterFieldDeleted(context, field, fieldType, storePrefix) {}

  /**
   * Method that is called when a field has been changed. This can be useful to
   * maintain data integrity by updating the values.
   */
  afterFieldUpdated(context, field, oldField, fieldType, storePrefix) {}

  /**
   * Method that is called when the field options of a view are updated.
   */
  fieldOptionsUpdated(context, view, fieldOptions, storePrefix) {}

  /**
   * Method that is called when the selected view is updated.
   *
   * @return  Indicates whether the page should be refreshed. The view is already
   *          refreshed automatically when the filter type or disabled is updated.
   */
  updated(context, view, oldView, storePrefix) {
    return false
  }

  /**
   * Event that is called when a row is created from an outside source, so for example
   * via a real time event by another user. It can be used to check if data in an store
   * needs to be updated.
   */
  rowCreated(context, tableId, fields, values, metadata, storePrefix) {}

  /**
   * Event that is called when a row is updated from an outside source, so for example
   * via a real time event by another user. It can be used to check if data in an store
   * needs to be updated.
   */
  rowUpdated(
    context,
    tableId,
    fields,
    row,
    values,
    metadata,
    updatedFieldIds,
    storePrefix
  ) {}

  /**
   * Event that is called when something went wrong while generating AI values
   * for a field. This can be used to show an error message to the user.
   */
  AIValuesGenerationError(context, tableId, fieldId, rowIds, error) {}

  /**
   * Event that is called when a row is deleted from an outside source, so for example
   * via a real time event by another user. It can be used to check if data in an store
   * needs to be updated.
   */
  rowDeleted(context, tableId, fields, row, storePrefix) {}

  /**
   * Event that is called when a piece of metadata is updated for a particular row.
   * A function which takes the current metadata value and applies the update is
   * provided and should be used to calculate and store the new metadata value for the
   * specified metadata type and row.
   */
  async rowMetadataUpdated(
    { store },
    tableId,
    rowId,
    rowMetadataType,
    updateFunction,
    storePrefix = ''
  ) {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(
        storePrefix + 'view/' + this.getType() + '/updateRowMetadata',
        {
          tableId,
          rowId,
          rowMetadataType,
          updateFunction,
        }
      )
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      colorClass: this.colorClass,
      name: this.getName(),
      canFilter: this.canFilter,
      canSort: this.canSort,
      canShare: this.canShare,
      canGroupBy: this.canGroupBy,
    }
  }

  /**
   * If the view type is disabled, this text will be visible explaining why.
   */
  getDeactivatedText() {}

  /**
   * When the disabled view type is clicked, this modal will be shown.
   */
  getDeactivatedClickModal() {
    return null
  }

  /**
   * Indicates if the view type is disabled.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * Helper function to set a field value to null for all
   * views of the same type
   * Used when fields are converted or deleted and should no
   * longer be set
   */
  _setFieldToNull({ rootGetters, dispatch }, field, fieldName) {
    rootGetters['view/getAll']
      .filter((view) => view.type === this.type)
      .forEach((view) => {
        if (view[fieldName] === field.id) {
          dispatch(
            'view/forceUpdate',
            {
              view,
              values: { [fieldName]: null },
            },
            { root: true }
          )
        }
      })
  }

  /**
   * Helper function to call after the field is created in the table
   * to set the default field options for the view where the field was created.
   * This is useful for example when creating a new field in a publicly shared grid
   * view to make the new field visible, otherwise by default the new field will be
   * hidden if the view is shared. The default implementation returns null, which
   * mean that is not necessary to update the field options. Return an object with
   * the field options to update if necessary.
   */
  getInitialFieldOptionsForView(view) {
    return {
      hidden: false,
    }
  }

  /**
    ShareView component allows for customization which requires a bit of explaination.
    ViewType may provide additional components through specific methods which are
    injected into specific places in ShareViewLink component.

    Below is a draft of placement of those additional components

    # shareview create state #

     +---------------------------------------------------------------------+
     |                                                                     |
     |    ${ getSharedViewText() }                                         |
     |   [share view button] [..getAdditionalCreateShareLinkOptions()]     |
     |                                                                     |
     +---------------------------------------------------------------------+

    # shareview shared state #

     +-----------------------------------------------------------------------+
     |                                                                       |
     |   this view is currently shared via a private link                    |
     |  [ share URL                    ]  [ copy ] [ rotate url ]            |
     |  [ restrict access with password]                                     |
     |  [ ..getAdditionalShareLinkOPptions()]                                |
     |                                                                       |
     [-----------------------------------------------------------------------]
     [                                                                       ]
     [    ..getAdditionalSharingSections() shoudl provide                    ]
     [      whole component. It should be in sync with footer link options   ]
     [                                                                       ]
     +-----------------------------------------------------------------------+
     | [disalbe/enable sharing]  [..getAdditionalDisableSharedLinkOptions()] |
     +-----------------------------------------------------------------------+
   */

  /**
   * Every registered view can display multiple additional public share link options
   * which will be visible on the share public view context. Those options are added
   * to a default share link component only.
   *
   * Additional sharing sections (which may be visible even if default share link is not)
   * can be returned from getAdditionalSharingSections
   */
  getAdditionalShareLinkOptions() {
    return []
  }

  /**
   * A view type can show additional options (links) in a create shared view
   * modal. This should return a list of components to display.
   *
   * @returns {*[]}
   */
  getAdditionalCreateShareLinkOptions() {
    return []
  }

  /**
   * Once a view is shared, additional disable shared link buttons may
   * be presented in the footer
   */
  getAdditionalDisableSharedLinkOptions() {
    return []
  }

  /**
   * Additional share link sections that are added after a default one. This method should
   * return a list of Vue components. Each component will receive `view` and
   * should be responsible for checking its visibility.
   *
   * In most cases state of components returned from  here should be in sync with state
   * of components returned by getAdditionalDisableSharedLinkOptions() visible in footer.
   */
  getAdditionalSharingSections() {
    return []
  }

  /**
   * Custom translation text to return for Shared View text.
   *
   * @returns {null|String}
   */
  getSharedViewText() {
    return this.app.i18n.t('shareViewLink.shareViewText')
  }

  /**
   * Indicates whether the view is compatible with a data sync.
   */
  isCompatibleWithDataSync(dataSync) {
    return true
  }

  getVisibleFieldsInOrder({ $store: store }, fields, view, storePrefix = '') {
    const fieldOptions =
      store.getters[
        storePrefix + 'view/' + this.getType() + '/getAllFieldOptions'
      ]
    return fields
      .filter(filterVisibleFieldsFunction(fieldOptions))
      .sort(sortFieldsByOrderAndIdFunction(fieldOptions, true))
  }
}

export class GridViewType extends ViewType {
  static getType() {
    return 'grid'
  }

  getIconClass() {
    return 'iconoir-menu'
  }

  canGroupBy() {
    return true
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewType.grid')
  }

  getHeaderComponent() {
    return GridViewHeader
  }

  getHeaderClassNames() {
    return 'header--dark-border'
  }

  getComponent() {
    return GridView
  }

  canShare() {
    return true
  }

  canShowRowModal() {
    return true
  }

  getPublicRoute() {
    return 'database-public-grid-view'
  }

  async fetch({ store }, database, view, fields, storePrefix = '') {
    const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
    const adhocFiltering = isAdhocFiltering(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    const adhocSorting = isAdhocSorting(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    await store.dispatch(
      storePrefix + 'view/grid/setRowHeight',
      GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING[view.row_height_size]
    )
    await store.dispatch(storePrefix + 'view/grid/fetchInitial', {
      gridId: view.id,
      fields,
      adhocFiltering,
      adhocSorting,
    })
    // The grid view store keeps a copy of the group bys that must only be updated
    // after the refresh of the page. This is because the group by depends on the rows
    // being sorted, and this will only be the case after a refresh.
    await store.dispatch(
      storePrefix + 'view/grid/updateActiveGroupBys',
      clone(view.group_bys)
    )

    if (
      !isPublic &&
      this.app.$hasPermission(
        'database.table.field_rules.read_field_rules',
        view.table,
        database.workspace.id
      ) &&
      !store.getters['fieldRules/hasRules']({ tableId: view.table_id })
    ) {
      await store.dispatch('fieldRules/fetchInitial', {
        tableId: view.table_id,
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
    const adhocSorting = isAdhocSorting(
      this.app,
      database.workspace,
      view,
      isPublic
    )
    await store.dispatch(storePrefix + 'view/grid/refresh', {
      view,
      fields,
      includeFieldOptions,
      adhocFiltering,
      adhocSorting,
    })
  }

  async fieldRestored(
    { dispatch, rootGetters },
    table,
    selectedView,
    field,
    fieldType,
    storePrefix = ''
  ) {
    // There might be new filters and sorts associated with the restored field,
    // ensure we create them. They will be included on the field data object if present.
    await dispatch(
      'view/fieldRestored',
      { field, fieldType, view: selectedView },
      { root: true }
    )
  }

  shouldRefreshWhenFieldCreated(registry, store, field, storePrefix) {
    const searchTerm =
      store.getters[storePrefix + 'view/grid/getActiveSearchTerm']
    const searchMode = getDefaultSearchModeFromEnv(this.app.$config)
    return newFieldMatchesActiveSearchTerm(
      searchMode,
      registry,
      field,
      searchTerm
    )
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
      storePrefix + 'view/grid/addField',
      { field, value },
      { root: true }
    )
    await dispatch(
      storePrefix + 'view/grid/setFieldOptionsOfField',
      {
        field,
        // The default values should be the same as in the `GridViewFieldOptions`
        // model in the backend to stay consistent.
        values: {
          width: 200,
          hidden: false,
          order: maxPossibleOrderValue,
          aggregation_type: '',
          aggregation_raw_type: '',
        },
      },
      { root: true }
    )
  }

  async afterFieldDeleted({ dispatch }, field, fieldType, storePrefix = '') {
    await dispatch(
      storePrefix + 'view/grid/forceDeleteFieldOptions',
      field.id,
      {
        root: true,
      }
    )
  }

  async afterFieldUpdated(
    { dispatch, rootGetters },
    field,
    oldField,
    fieldType,
    storePrefix
  ) {
    // The field changing may change which cells in the field should be highlighted so
    // we refresh them to ensure that they still correctly match. E.g. changing a date
    // fields date_format needs a search update as search string might no longer
    // match the new format.
    await dispatch(
      storePrefix + 'view/grid/updateSearch',
      {
        fields: rootGetters['field/getAll'],
      },
      {
        root: true,
      }
    )
    // If a field is updated, it can happen that the group by was deleted because
    // it's not compatible anymore. This will make sure that's also reflected in the
    // active group bys.
    await dispatch(
      storePrefix + 'view/grid/updateActiveGroupBys',
      clone(rootGetters['view/getSelected'].group_bys),
      {
        root: true,
      }
    )
  }

  async fieldOptionsUpdated({ store }, view, fieldOptions, storePrefix) {
    await store.dispatch(
      storePrefix + 'view/grid/forceUpdateAllFieldOptions',
      fieldOptions,
      {
        root: true,
      }
    )
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
      await store.dispatch(storePrefix + 'view/grid/createdNewRow', {
        view: store.getters['view/getSelected'],
        fields,
        values,
        metadata,
      })
      await store.dispatch(storePrefix + 'view/grid/fetchByScrollTopDelayed', {
        scrollTop: store.getters[storePrefix + 'view/grid/getScrollTop'],
        fields,
      })
      store.dispatch(storePrefix + 'view/grid/fetchAllFieldAggregationData', {
        view: store.getters['view/getSelected'],
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
        await waitFor(() =>
          store.getters[storePrefix + 'view/grid/getRows'].every(
            (row) => !row._.loading
          )
        )
      } catch (error) {
        // If the timeout is reached, then just continue with the update because the
        // realtime update must come through eventually, otherwise the page is not
        // up to date.
      }
      await store.dispatch(storePrefix + 'view/grid/updatedExistingRow', {
        view: store.getters['view/getSelected'],
        fields,
        row,
        values,
        metadata,
        updatedFieldIds,
      })
      await store.dispatch(storePrefix + 'view/grid/fetchByScrollTopDelayed', {
        scrollTop: store.getters[storePrefix + 'view/grid/getScrollTop'],
        fields,
      })
      store.dispatch(storePrefix + 'view/grid/fetchAllFieldAggregationData', {
        view: store.getters['view/getSelected'],
      })
    }
  }

  async rowDeleted({ store }, tableId, fields, row, storePrefix = '') {
    if (this.isCurrentView(store, tableId)) {
      await store.dispatch(storePrefix + 'view/grid/deletedExistingRow', {
        view: store.getters['view/getSelected'],
        fields,
        row,
      })
      await store.dispatch(storePrefix + 'view/grid/fetchByScrollTopDelayed', {
        scrollTop: store.getters[storePrefix + 'view/grid/getScrollTop'],
        fields,
      })
      store.dispatch(storePrefix + 'view/grid/fetchAllFieldAggregationData', {
        view: store.getters['view/getSelected'],
      })
    }
  }

  AIValuesGenerationError(
    context,
    tableId,
    fieldId,
    rowIds,
    error,
    storePrefix = ''
  ) {
    if (this.isCurrentView(context.store, tableId)) {
      context.store.dispatch(
        storePrefix + 'view/grid/AIValuesGenerationError',
        {
          fieldId,
          rowIds,
          error,
        },
        { root: true }
      )
    }
  }
}

/**
 * This class can be used if the view store uses the `bufferedRows` mixin. It will
 * enable real time collaboration and will make sure that the rows are in the store
 * are updated properly.
 */
export const BaseBufferedRowViewTypeMixin = (Base) =>
  class extends Base {
    getDefaultFieldOptionValues() {
      return {}
    }

    /**
     * If the view settings are not correct, this function will prevent fetching the
     * rows, to prevent unnecessary requests that are going to fail anyway.
     */
    canFetch(context, database, view, fields) {
      return true
    }

    async fetch(context, database, view, fields, storePrefix = '') {
      const { store } = context
      if (!this.canFetch(context, database, view, fields)) {
        // Set the viewId so the refresh will work when the view can fetch rows.
        await store.dispatch(`${storePrefix}view/${this.getType()}/setViewId`, {
          viewId: view.id,
        })
        return
      }
      const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
      const adhocFiltering = isAdhocFiltering(
        this.app,
        database.workspace,
        view,
        isPublic
      )
      const adhocSorting = isAdhocSorting(
        this.app,
        database.workspace,
        view,
        isPublic
      )
      await store.dispatch(
        `${storePrefix}view/${this.getType()}/fetchInitial`,
        {
          viewId: view.id,
          fields,
          adhocFiltering,
          adhocSorting,
        }
      )

      if (
        !isPublic &&
        this.app.$hasPermission(
          'database.table.field_rules.read_field_rules',
          view.table,
          database.workspace.id
        ) &&
        !store.getters['fieldRules/hasRules']({ tableId: view.table_id })
      ) {
        await store.dispatch('fieldRules/fetchInitial', {
          tableId: view.table_id,
        })
      }
    }

    async refresh(
      context,
      database,
      view,
      fields,
      storePrefix = '',
      includeFieldOptions = false,
      sourceEvent = null
    ) {
      const { store } = context
      if (!this.canFetch(context, database, view, fields)) {
        return
      }
      const isPublic = store.getters[storePrefix + 'view/public/getIsPublic']
      const adhocFiltering = isAdhocFiltering(
        this.app,
        database.workspace,
        view,
        isPublic
      )
      const adhocSorting = isAdhocSorting(
        this.app,
        database.workspace,
        view,
        isPublic
      )
      await store.dispatch(
        storePrefix + 'view/' + this.getType() + '/refresh',
        {
          fields,
          includeFieldOptions,
          adhocFiltering,
          adhocSorting,
        }
      )
    }

    async fieldRestored(
      { dispatch },
      table,
      selectedView,
      field,
      fieldType,
      storePrefix = ''
    ) {
      // There might be new filters and sorts associated with the restored field,
      // ensure we create them. They will be included on the field data object if present.
      await dispatch(
        'view/fieldRestored',
        { field, fieldType, view: selectedView },
        { root: true }
      )
    }

    shouldRefreshWhenFieldCreated(registry, store, field, storePrefix) {
      const searchTerm =
        store.getters[
          storePrefix + 'view/' + this.getType() + '/getActiveSearchTerm'
        ]
      const searchMode = getDefaultSearchModeFromEnv(this.app.$config)
      return newFieldMatchesActiveSearchTerm(
        searchMode,
        registry,
        field,
        searchTerm
      )
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
        storePrefix + 'view/' + this.getType() + '/addField',
        { field, value },
        { root: true }
      )
      await dispatch(
        storePrefix + 'view/' + this.getType() + '/setFieldOptionsOfField',
        {
          field,
          values: this.getDefaultFieldOptionValues(),
        },
        { root: true }
      )
    }

    async afterFieldDeleted({ dispatch }, field, fieldType, storePrefix = '') {
      await dispatch(
        storePrefix + 'view/' + this.getType() + '/forceDeleteFieldOptions',
        field.id,
        {
          root: true,
        }
      )
    }

    async fieldOptionsUpdated({ store }, view, fieldOptions, storePrefix) {
      await store.dispatch(
        storePrefix + 'view/' + this.getType() + '/forceUpdateAllFieldOptions',
        fieldOptions,
        {
          root: true,
        }
      )
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
        await store.dispatch(
          storePrefix + 'view/' + this.getType() + '/afterNewRowCreated',
          {
            view: store.getters['view/getSelected'],
            fields,
            values,
          }
        )
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
            () =>
              !store.getters[
                storePrefix + 'view/' + this.getType() + '/getCreating'
              ]
          )
        } catch (error) {
          // If the timeout is reached, then just continue with the update because the
          // realtime update must come through eventually, otherwise the page is not
          // up to date.
        }
        await store.dispatch(
          storePrefix + 'view/' + this.getType() + '/afterExistingRowUpdated',
          {
            view: store.getters['view/getSelected'],
            fields,
            row,
            values,
          }
        )
      }
    }

    async rowDeleted({ store }, tableId, fields, row, storePrefix = '') {
      if (this.isCurrentView(store, tableId)) {
        await store.dispatch(
          storePrefix + 'view/' + this.getType() + '/afterExistingRowDeleted',
          {
            view: store.getters['view/getSelected'],
            fields,
            row,
          }
        )
      }
    }
  }

export class GalleryViewType extends BaseBufferedRowViewTypeMixin(ViewType) {
  static getType() {
    return 'gallery'
  }

  getIconClass() {
    return 'baserow-icon-gallery'
  }

  getColorClass() {
    return 'color-error'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewType.gallery')
  }

  getHeaderComponent() {
    return GalleryViewHeader
  }

  getComponent() {
    return GalleryView
  }

  canShare() {
    return true
  }

  canShowRowModal() {
    return true
  }

  getPublicRoute() {
    return 'database-public-gallery-view'
  }

  getDefaultFieldOptionValues() {
    // The default values should be the same as in the `GalleryViewFieldOptions`
    // model in the backend to stay consistent.
    return {
      hidden: true,
      order: maxPossibleOrderValue,
    }
  }

  async afterFieldUpdated(
    { dispatch, rootGetters },
    field,
    oldField,
    fieldType,
    storePrefix
  ) {
    // If the field type has changed from a file field to something else, it could
    // be that there are gallery views that depending on that field. So we need to
    // change to type to null if that's the case.
    const type = FileFieldType.getType()
    if (oldField.type === type && field.type !== type) {
      this._setFieldToNull(
        { dispatch, rootGetters },
        field,
        'card_cover_image_field'
      )
    }
    // The field changing may change which cells in the field should be highlighted so
    // we refresh them to ensure that they still correctly match. E.g. changing a date
    // fields date_format needs a search update as search string might no longer
    // match the new format.
    await dispatch(
      storePrefix + 'view/gallery/updateSearch',
      {
        fields: rootGetters['field/getAll'],
      },
      {
        root: true,
      }
    )
  }

  async afterFieldDeleted(context, field, fieldType, storePrefix = '') {
    // We want to loop over all gallery views that we have in the store and check if
    // they were depending on this deleted field. If that's case, we can set it to null
    // because it doesn't exist anymore.
    this._setFieldToNull(context, field, 'card_cover_image_field')
    await context.dispatch(
      storePrefix + 'view/' + this.getType() + '/forceDeleteFieldOptions',
      field.id,
      {
        root: true,
      }
    )
  }
}

export class FormViewType extends ViewType {
  static getType() {
    return 'form'
  }

  getIconClass() {
    return 'baserow-icon-form'
  }

  getColorClass() {
    return 'color-warning'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewType.form')
  }

  canFilter() {
    return false
  }

  canSort() {
    return false
  }

  canShare() {
    return true
  }

  getPublicRoute() {
    return 'database-table-form'
  }

  getSharingLinkName() {
    const { i18n } = this.app
    return i18n.t('viewType.sharing.formLinkName')
  }

  getHeaderComponent() {
    return FormViewHeader
  }

  getComponent() {
    return FormView
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
    await store.dispatch(storePrefix + 'view/form/fetchInitial', {
      formId: view.id,
    })
  }

  async afterFieldCreated(
    { dispatch },
    table,
    field,
    fieldType,
    storePrefix = ''
  ) {
    await dispatch(
      storePrefix + 'view/form/setFieldOptionsOfField',
      {
        field,
        // The default values should be the same as in the `FormViewFieldOptions`
        // model in the backend to stay consistent.
        values: {
          name: '',
          description: '',
          enabled: false,
          required: true,
          order: maxPossibleOrderValue,
          show_when_matching_conditions: false,
          condition_type: 'AND',
          conditions: [],
          field_component: 'default',
        },
      },
      { root: true }
    )
  }

  async afterFieldDeleted({ dispatch }, field, fieldType, storePrefix = '') {
    await dispatch(
      storePrefix + 'view/form/forceDeleteFieldOptions',
      field.id,
      { root: true }
    )
  }

  async fetch({ store }, database, view, fields, storePrefix = '') {
    await store.dispatch(storePrefix + 'view/form/fetchInitial', {
      formId: view.id,
    })
  }

  async fieldOptionsUpdated({ store }, view, fieldOptions, storePrefix) {
    await store.dispatch(
      storePrefix + 'view/form/forceUpdateAllFieldOptions',
      fieldOptions
    )
  }

  getInitialFieldOptionsForView(view) {
    return null
  }

  /**
   * It's not possible to create rows in a data sync table, so there is no point in
   * letting the user create one.
   */
  isCompatibleWithDataSync(dataSync) {
    return !dataSync || dataSync.two_way_sync
  }
}
