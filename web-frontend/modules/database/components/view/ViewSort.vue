<template>
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{
        'active active--warning': view.sortings.length > 0,
      }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-sort"></i>
      <span class="header__filter-name">{{
        $tc('viewSort.sort', view.sortings.length, {
          count: view.sortings.length,
        })
      }}</span>
    </a>
    <ViewSortContext
      ref="context"
      :view="view"
      :fields="fields"
      :read-only="readOnly"
      :disable-sort="disableSort"
      @changed="$emit('changed')"
    ></ViewSortContext>
  </div>
</template>

<script>
import ViewSortContext from '@baserow/modules/database/components/view/ViewSortContext'

export default {
  name: 'ViewSort',
  components: { ViewSortContext },
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    disableSort: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
