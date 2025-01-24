<template>
  <ul v-if="!tableLoading" class="header__filter header__filter--full-width">
    <li class="header__filter-item">
      <GridViewHide
        :database="database"
        :view="view"
        :fields="fieldsAllowedToBeHidden"
        :read-only="readOnly"
        :store-prefix="storePrefix"
      ></GridViewHide>
    </li>
    <li class="header__filter-item">
      <GridViewRowHeight
        :database="database"
        :view="view"
        :store-prefix="storePrefix"
        :read-only="readOnly"
      ></GridViewRowHeight>
    </li>
    <li class="header__filter-item header__filter-item--full-width">
      <ViewSearch
        :view="view"
        :fields="fields"
        :store-prefix="storePrefix"
        @refresh="$emit('refresh', $event)"
      ></ViewSearch>
    </li>
  </ul>
</template>

<script>
import { mapState } from 'vuex'

import GridViewRowHeight from '@baserow/modules/database/components/view/grid/GridViewRowHeight'
import GridViewHide from '@baserow/modules/database/components/view/grid/GridViewHide'
import ViewSearch from '@baserow/modules/database/components/view/ViewSearch'

export default {
  name: 'GridViewHeader',
  components: { GridViewRowHeight, GridViewHide, ViewSearch },
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapState({
      tableLoading: (state) => state.table.loading,
    }),
    fieldsAllowedToBeHidden() {
      return this.fields.filter((field) => !field.primary)
    },
  },
}
</script>
