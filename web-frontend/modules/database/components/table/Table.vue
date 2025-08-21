<template>
  <div>
    <header
      ref="header"
      class="layout__col-2-1 header"
      :class="[
        { 'header--overflow': headerOverflow },
        getViewHeaderClassNames(view),
      ]"
    >
      <div v-show="tableLoading" class="header__loading"></div>
      <ul v-if="!tableLoading" class="header__filter">
        <li v-if="showLogo" class="header__filter-item">
          <ExternalLinkBaserowLogo class="header__filter-logo" />
        </li>
        <li class="header__filter-item header__filter-item--grids">
          <a
            ref="viewsSelectToggle"
            class="header__filter-link active"
            :class="{ 'header__filter-link--disabled': views === null }"
            data-highlight="views"
            @click="views !== null && openTableViewsContext()"
          >
            <template v-if="hasSelectedView">
              <i
                class="header__filter-icon header-filter-icon--view"
                :class="`${view._.type.colorClass} ${view._.type.iconClass}`"
              ></i>
              <span class="header__filter-name header__filter-name--forced">
                <EditableViewName ref="rename" :view="view"></EditableViewName>
              </span>
              <i
                v-if="views !== null"
                class="header__sub-icon iconoir-nav-arrow-down"
              ></i>
            </template>
            <template v-else-if="view !== null">
              {{ $t('table.chooseView') }}
              <i class="header__sub-icon iconoir-nav-arrow-down"></i>
            </template>
          </a>
          <ViewsContext
            v-if="views !== null"
            ref="viewsContext"
            :database="database"
            :table="table"
            :views="views"
            :read-only="readOnly"
            :header-overflow="headerOverflow"
            @selected-view="$emit('selected-view', $event)"
          ></ViewsContext>
        </li>
        <li
          v-if="hasSelectedView && !readOnly && showViewContext"
          class="header__filter-item header__filter-item--no-margin-left"
        >
          <a
            ref="viewSelectToggle"
            class="header__filter-link"
            data-highlight="view-options"
            @click="openTableViewContext"
          >
            <i class="header__filter-icon baserow-icon-more-vertical"></i>
          </a>
          <ViewContext
            ref="viewContext"
            :database="database"
            :view="view"
            :table="table"
            :views="views"
            @enable-rename="$refs.rename.edit()"
          >
          </ViewContext>
        </li>
        <component
          :is="component"
          v-for="(component, index) in getAdditionalTableHeaderComponents(
            view,
            isPublic
          )"
          :key="index"
          :database="database"
          :table="table"
          :view="view"
          :fields="fields"
          :is-public-view="isPublic"
          :store-prefix="storePrefix"
        >
        </component>
        <li
          v-if="
            hasSelectedView &&
            view._.type.canFilter &&
            (adhocFiltering ||
              $hasPermission(
                'database.table.view.create_filter',
                view,
                database.workspace.id
              ))
          "
          class="header__filter-item"
          data-highlight="view-filters"
        >
          <ViewFilter
            :view="view"
            :is-public-view="isPublic"
            :fields="fields"
            :read-only="adhocFiltering"
            :disable-filter="disableFilter"
            @changed="refresh()"
          ></ViewFilter>
        </li>
        <li
          v-if="
            hasSelectedView &&
            view._.type.canSort &&
            (adhocSorting ||
              $hasPermission(
                'database.table.view.create_sort',
                view,
                database.workspace.id
              ))
          "
          class="header__filter-item"
          data-highlight="view-sorts"
        >
          <ViewSort
            :view="view"
            :fields="fields"
            :read-only="adhocSorting"
            :disable-sort="disableSort"
            @changed="refresh()"
          ></ViewSort>
        </li>
        <li
          v-if="
            hasSelectedView &&
            view._.type.canGroupBy &&
            (readOnly ||
              $hasPermission(
                'database.table.view.create_group_by',
                view,
                database.workspace.id
              ))
          "
          class="header__filter-item"
          data-highlight="view-group-by"
        >
          <ViewGroupBy
            :view="view"
            :fields="fields"
            :read-only="readOnly"
            :disable-group-by="disableGroupBy"
            @changed="refresh()"
          ></ViewGroupBy>
        </li>
        <li
          v-if="
            hasSelectedView &&
            view._.type.canShare &&
            !readOnly &&
            $hasPermission(
              'database.table.view.update_slug',
              view,
              database.workspace.id
            )
          "
          class="header__filter-item"
        >
          <ShareViewLink :view="view" :read-only="readOnly"></ShareViewLink>
        </li>
        <li
          v-if="
            hasSelectedView &&
            hasCompatibleDecorator &&
            (adhocDecorations ||
              $hasPermission(
                'database.table.view.create_decoration',
                view,
                database.workspace.id
              ))
          "
          class="header__filter-item"
        >
          <ViewDecoratorMenu
            :database="database"
            :view="view"
            :table="table"
            :fields="fields"
            :read-only="adhocDecorations"
            :disable-sort="disableSort"
            @changed="refresh()"
          ></ViewDecoratorMenu>
        </li>
      </ul>
      <component
        :is="getViewHeaderComponent(view)"
        v-if="!tableLoading && hasSelectedView"
        :database="database"
        :table="table"
        :view="view"
        :fields="fields"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @refresh="refresh"
      />
    </header>
    <div class="layout__col-2-2 content">
      <DefaultErrorPage v-if="viewError" :error="viewError" />
      <component
        :is="getViewComponent(view)"
        v-if="hasSelectedView && !tableLoading && !viewError"
        ref="view"
        :database="database"
        :table="table"
        :view="view"
        :loading="viewLoading"
        :fields="fields"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @refresh="refresh"
        @selected-row="$emit('selected-row', $event)"
        @navigate-previous="
          (row, activeSearchTerm) =>
            $emit('navigate-previous', row, activeSearchTerm)
        "
        @navigate-next="
          (row, activeSearchTerm) =>
            $emit('navigate-next', row, activeSearchTerm)
        "
      />
      <div v-if="viewLoading" class="loading-overlay"></div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import ResizeObserver from 'resize-observer-polyfill'

import { RefreshCancelledError } from '@baserow/modules/core/errors'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewsContext from '@baserow/modules/database/components/view/ViewsContext'
import ViewContext from '@baserow/modules/database/components/view/ViewContext'
import ViewFilter from '@baserow/modules/database/components/view/ViewFilter'
import ViewSort from '@baserow/modules/database/components/view/ViewSort'
import ViewDecoratorMenu from '@baserow/modules/database/components/view/ViewDecoratorMenu'
import ViewSearch from '@baserow/modules/database/components/view/ViewSearch'
import EditableViewName from '@baserow/modules/database/components/view/EditableViewName'
import ShareViewLink from '@baserow/modules/database/components/view/ShareViewLink'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'
import ViewGroupBy from '@baserow/modules/database/components/view/ViewGroupBy'
import DefaultErrorPage from '@baserow/modules/core/components/DefaultErrorPage'
import { waitFor } from '@baserow/modules/core/utils/queue'

/**
 * This page component is the skeleton for a table. Depending on the selected view it
 * will load the correct components into the header and body.
 */
export default {
  components: {
    DefaultErrorPage,
    ViewGroupBy,
    ExternalLinkBaserowLogo,
    ShareViewLink,
    EditableViewName,
    ViewsContext,
    ViewDecoratorMenu,
    ViewFilter,
    ViewSort,
    ViewSearch,
    ViewContext,
  },
  /**
   * Because there is no hook that is called before the route changes, we need the
   * tableLoading middleware to change the table loading state. This change will get
   * rendered right away. This allows us to have a custom loading animation when
   * switching views.
   */
  middleware: ['tableLoading'],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    views: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === undefined,
      default: null,
    },
    view: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === undefined,
    },
    viewError: {
      required: false,
      validator: (prop) =>
        typeof prop === 'object' ||
        typeof prop === 'function' ||
        prop === undefined,
      default: null,
    },
    tableLoading: {
      type: Boolean,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    disableFilter: {
      type: Boolean,
      required: false,
      default: false,
    },
    disableSort: {
      type: Boolean,
      required: false,
      default: false,
    },
    disableGroupBy: {
      type: Boolean,
      required: false,
      default: false,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return {
      // Shows a small spinning loading animation when the view is being refreshed.
      viewLoading: false,
      // Indicates if the elements within the header are overflowing. In case of true,
      // we can hide certain values to make sure that it fits within the header.
      headerOverflow: false,
      // Indicates whether the table is currently being refreshed using via the
      // `refresh-table` signal.
      isRefreshing: false,
    }
  },
  computed: {
    /**
     * Indicates if there is a selected view by checking if the view object has been
     * populated.
     */
    hasSelectedView() {
      return (
        this.view !== undefined &&
        Object.prototype.hasOwnProperty.call(this.view, '_')
      )
    },
    hasCompatibleDecorator() {
      return (
        this.view !== undefined &&
        this.$registry
          .getOrderedList('viewDecorator')
          .some((deco) => deco.isCompatible(this.view))
      )
    },
    showLogo() {
      return this.view?.show_logo && this.isPublic
    },
    showViewContext() {
      return (
        this.$hasPermission(
          'database.table.run_export',
          this.table,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.import_rows',
          this.table,
          this.database.workspace.id
        ) ||
        this.someViewHasPermission(
          'database.table.view.duplicate',
          this.table,
          this.database.workspace.id
        ) ||
        this.someViewHasPermission(
          'database.table.view.update',
          this.table,
          this.database.workspace.id
        ) ||
        this.someViewHasPermission(
          'database.table.view.delete',
          this.table,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.create_webhook',
          this.table,
          this.database.workspace.id
        )
      )
    },
    adhocFiltering() {
      if (this.readOnly) {
        return true
      }

      return (
        this.$hasPermission(
          'database.table.view.list_filter',
          this.view,
          this.database.workspace.id
        ) &&
        !this.$hasPermission(
          'database.table.view.create_filter',
          this.view,
          this.database.workspace.id
        )
      )
    },
    adhocSorting() {
      if (this.readOnly) {
        return true
      }

      return (
        this.$hasPermission(
          'database.table.view.list_sort',
          this.view,
          this.database.workspace.id
        ) &&
        !this.$hasPermission(
          'database.table.view.create_sort',
          this.view,
          this.database.workspace.id
        )
      )
    },
    adhocDecorations() {
      if (this.readOnly) {
        return true
      }

      return (
        this.$hasPermission(
          'database.table.view.list_decoration',
          this.view,
          this.database.workspace.id
        ) &&
        !this.$hasPermission(
          'database.table.view.create_decoration',
          this.view,
          this.database.workspace.id
        )
      )
    },
    ...mapGetters({
      isPublic: 'page/view/public/getIsPublic',
    }),
  },
  watch: {
    tableLoading(value) {
      if (!value) {
        this.$nextTick(() => {
          this.checkHeaderOverflow()
        })
      }
    },
  },
  beforeMount() {
    this.$bus.$on('table-refresh', this.refresh)
    this.$bus.$on('open-table-views-context', this.openTableViewsContext)
    this.$bus.$on('close-table-views-context', this.closeTableViewsContext)
  },
  mounted() {
    this.$el.resizeObserver = new ResizeObserver(this.checkHeaderOverflow)
    this.$el.resizeObserver.observe(this.$el)
  },
  beforeDestroy() {
    this.$bus.$off('table-refresh', this.refresh)
    this.$el.resizeObserver.unobserve(this.$el)
    this.$bus.$off('open-table-views-context', this.openTableViewsContext)
    this.$bus.$off('close-table-views-context', this.closeTableViewsContext)
  },
  methods: {
    getViewComponent(view) {
      const type = this.$registry.get('view', view.type)
      return type.getComponent()
    },
    getViewHeaderComponent(view) {
      const type = this.$registry.get('view', view.type)
      return type.getHeaderComponent()
    },
    getViewHeaderClassNames(view) {
      if (!this.hasSelectedView) {
        return ''
      }
      const type = this.$registry.get('view', view.type)
      return type.getHeaderClassNames(view)
    },
    getAdditionalTableHeaderComponents(view, isPublic) {
      const opts = Object.values(this.$registry.getAll('plugin'))
        .reduce((components, plugin) => {
          components = components.concat(
            plugin.getAdditionalTableHeaderComponents(view, isPublic)
          )
          return components
        }, [])
        .filter((component) => component !== null)
      return opts
    },
    /**
     * When the window resizes, we want to check if the content of the header is
     * overflowing. If that is the case, we want to make some space by removing some
     * content. We do this by copying the header content into a new HTMLElement and
     * check if the elements still fit within the header. We copy the html because we
     * want to measure the header in the full width state.
     */
    checkHeaderOverflow() {
      const header = this.$refs.header
      const width = header.getBoundingClientRect().width
      const wrapper = document.createElement('div')
      wrapper.innerHTML = header.outerHTML
      const el = wrapper.childNodes[0]
      el.style = `position: absolute; left: 0; top: 0; width: ${width}px; overflow: auto;`
      el.classList.remove('header--overflow')
      document.body.appendChild(el)
      this.headerOverflow =
        el.clientWidth < el.scrollWidth || el.clientHeight < el.scrollHeight
      document.body.removeChild(el)
    },
    /**
     * Refreshes the whole view. All data will be reloaded and it will visually look
     * the same as seeing the view for the first time.
     */
    async refresh(event) {
      // If could be that the refresh event is for a specific table and in table case
      // we check if the refresh event is related to this table and stop if that is not
      // the case.
      if (
        typeof event === 'object' &&
        Object.prototype.hasOwnProperty.call(event, 'tableId') &&
        event.tableId !== this.table.id
      ) {
        return
      }

      const callCallback = async () => {
        if (event && Object.prototype.hasOwnProperty.call(event, 'callback')) {
          await event.callback()
        }
      }

      if (this.isRefreshing) {
        try {
          // If the table is already refreshing, then we don't have to do anything,
          // apart from waiting for the refresh to complete.
          await waitFor(() => !this.isRefreshing, 5, 30000)
        } catch (error) {
          // If the timeout is reached, then the table has been refreshing for too
          // long
        }
        // Regardless of the refreshing was completed, the callback must be called,
        // otherwise, the state of the table might not be updated correctly.
        await callCallback()
        return
      }

      this.isRefreshing = true

      const includeFieldOptions =
        typeof event === 'object' ? event.includeFieldOptions : false

      const fieldsToRefresh =
        typeof event === 'object' && event.newField
          ? [...this.fields, event.newField]
          : this.fields

      this.viewLoading = true
      const type = this.$registry.get('view', this.view.type)
      try {
        await type.refresh(
          { store: this.$store, app: this },
          this.database,
          this.view,
          fieldsToRefresh,
          this.storePrefix,
          includeFieldOptions,
          event?.sourceEvent
        )
      } catch (error) {
        if (error instanceof RefreshCancelledError) {
          // Multiple refresh calls have been made and the view has indicated that
          // this particular one should be cancelled. However we do not want to
          // set viewLoading back to false as the other non cancelled call/s might
          // still be loading.
          return
        } else {
          notifyIf(error)
        }
      }
      if (
        Object.prototype.hasOwnProperty.call(this.$refs, 'view') &&
        // TODO crash here can't convert undefined to object
        Object.prototype.hasOwnProperty.call(this.$refs.view, 'refresh')
      ) {
        await this.$refs.view.refresh()
      }
      // Before the callback is called, mark the table as not refreshing anymore, so
      // that other callbacks that are waiting can be resolved the moment the table has
      // been refreshed.
      this.isRefreshing = false
      // It might be possible that the event has a callback that needs to be called
      // after the rows are refreshed. This is for example the case when a field has
      // changed. In that case we want to update the field in the store after the rows
      // have been refreshed to prevent incompatible values in field types.
      await callCallback()
      this.$nextTick(() => {
        this.viewLoading = false
      })
    },
    someViewHasPermission(op) {
      return this.views.some((v) =>
        this.$hasPermission(op, v, this.database.workspace.id)
      )
    },
    openTableViewsContext() {
      this.$refs.viewsContext.toggle(
        this.$refs.viewsSelectToggle,
        'bottom',
        'left',
        4
      )
    },
    closeTableViewsContext() {
      this.$refs.viewsContext.hide()
    },
    openTableViewContext() {
      this.$refs.viewContext.toggle(
        this.$refs.viewSelectToggle,
        'bottom',
        'left',
        4
      )
    },
  },
}
</script>
