<template>
  <Context
    ref="viewsContext"
    class="select"
    max-height-if-outside-viewport
    @shown="shown"
  >
    <div class="select__search">
      <i class="select__search-icon iconoir-search"></i>
      <input
        v-model="query"
        type="text"
        class="select__search-input"
        :placeholder="$t('viewsContext.searchView')"
      />
    </div>
    <div v-if="isLoading" class="context--loading">
      <div class="loading"></div>
    </div>
    <ul
      ref="dropdown"
      v-auto-overflow-scroll
      class="select__items select__items--no-max-height"
    >
      <li
        v-for="type in activeViewOwnershipTypes"
        :key="type.getType() + 'group'"
      >
        <div
          v-if="viewsByOwnership(views, type.getType()).length > 0"
          :key="type.getType()"
          class="select__item-label"
        >
          {{ type.getName() }}
        </div>
        <ul>
          <ViewsContextItem
            v-for="view in viewsByOwnership(views, type.getType())"
            :ref="'view-' + view.id"
            :key="view.id"
            v-sortable="{
              enabled:
                !readOnly &&
                $hasPermission(
                  'database.table.order_views',
                  table,
                  database.workspace.id
                ),
              id: view.id,
              update: createOrderCall(view.ownership_type),
              marginTop: -1.5,
            }"
            :database="database"
            :view="view"
            :table="table"
            :read-only="readOnly"
            @selected="selectedView"
          ></ViewsContextItem>
        </ul>
      </li>
    </ul>
    <div v-if="!isLoading && views.length == 0" class="context__description">
      {{ $t('viewsContext.noViews') }}
    </div>
    <div
      v-if="!readOnly && availableViewOwnershipTypesForCreation.length > 0"
      class="select__footer"
    >
      <div class="select__footer-create">
        <CreateViewLink
          v-for="(viewType, type) in viewTypes"
          :key="type"
          :database="database"
          :table="table"
          :view-type="viewType"
          @created="selectedView"
        ></CreateViewLink>
      </div>
    </div>
  </Context>
</template>

<script>
import { mapState } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import { escapeRegExp } from '@baserow/modules/core/utils/string'
import context from '@baserow/modules/core/mixins/context'
import dropdownHelpers from '@baserow/modules/core/mixins/dropdownHelpers'
import ViewsContextItem from '@baserow/modules/database/components/view/ViewsContextItem'
import CreateViewLink from '@baserow/modules/database/components/view/CreateViewLink'

export default {
  name: 'ViewsContext',
  components: {
    ViewsContextItem,
    CreateViewLink,
  },
  mixins: [context, dropdownHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    views: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  data() {
    return {
      query: '',
      firstShow: true,
    }
  },
  computed: {
    viewTypes() {
      return this.$registry.getAll('view')
    },
    selectedViews() {
      return this.views.filter((item) => item._.selected)
    },
    ...mapState({
      isLoading: (state) => state.view.loading,
      isLoaded: (state) => state.view.loaded,
    }),
    viewOwnershipTypes() {
      return this.$registry.getAll('viewOwnershipType')
    },
    availableViewOwnershipTypesForCreation() {
      return this.activeViewOwnershipTypes.filter((t) =>
        t.userCanTryCreate(this.table, this.database.workspace.id)
      )
    },
    activeViewOwnershipTypes() {
      return Object.values(this.viewOwnershipTypes).sort(
        (a, b) => a.getListViewTypeSort() - b.getListViewTypeSort()
      )
    },
  },
  methods: {
    shown() {
      if (this.firstShow) {
        this.$nextTick(() => {
          this.scrollViewDropdownIfNeeded()
        })
        this.firstShow = false
      }
    },
    selectedView(view) {
      this.hide()
      this.$emit('selected-view', view)
    },
    /*
      If the currently selected view is not visible inside the dropdown we need to
      scroll just enough so that the selected view is visible as the last element
      in the dropdown.
      In case there are no views, we don't need to do anything and can simply return.
    */
    scrollViewDropdownIfNeeded() {
      if (this.selectedViews.length === 0) {
        return
      }
      const dropdownElement = this.$refs.dropdown
      const selectedViewItem = this.getSelectedViewItem()
      const dropdownHeight = dropdownElement.clientHeight
      if (
        this.isSelectedViewOutOfDropdownView(selectedViewItem, dropdownHeight)
      ) {
        dropdownElement.scrollTop = this.calculateOffsetToSelectedViewItem(
          dropdownElement,
          selectedViewItem
        )
      }
    },
    /**
     * This method filters the view elements and returns the currently selected
     * view dom item based on whether or not it is selected.
     */
    getSelectedViewItem() {
      const selectedViewItemID = this.selectedViews[0].id
      return this.$refs[`view-${selectedViewItemID}`][0].$el
    },
    /**
     * This method calculates whether or not the selectedViewItem is fully visible
     * inside the ViewContext dropdown or not
     */
    isSelectedViewOutOfDropdownView(selectedViewItem, dropdownHeight) {
      const selectedOffsetPlusHeight =
        selectedViewItem.offsetTop + selectedViewItem.clientHeight
      return selectedOffsetPlusHeight > dropdownHeight
    },
    /**
     * This method calculates the necessary offsetTop of the dropdown element so that
     * the selected view item is the bottom element.
     */
    calculateOffsetToSelectedViewItem(dropdownElement, selectedViewItem) {
      const {
        parentContainerBeforeHeight,
        itemHeightWithMargins,
        itemsInView,
      } = this.getStyleProperties(dropdownElement, selectedViewItem)

      const viewItemsBeforeSelectedViewItemHeight =
        (itemsInView - 1) * itemHeightWithMargins

      return (
        selectedViewItem.offsetTop -
        viewItemsBeforeSelectedViewItemHeight -
        parentContainerBeforeHeight
      )
    },
    searchAndOrder(views) {
      const query = this.query

      return views
        .filter(function (view) {
          const regex = new RegExp('(' + escapeRegExp(query) + ')', 'i')
          return view.name.match(regex)
        })
        .sort((a, b) => a.order - b.order)
    },
    viewsByOwnership(views, ownershipType) {
      return this.searchAndOrder(views).filter(
        (view) => view.ownership_type === ownershipType
      )
    },
    async order(ownershipType, order, oldOrder) {
      try {
        await this.$store.dispatch('view/order', {
          table: this.table,
          ownershipType,
          order,
          oldOrder,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    createOrderCall(ownershipType) {
      return (...lastArgs) => {
        return this.order(ownershipType, ...lastArgs)
      }
    },
  },
}
</script>
