<template>
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{
        'active active--purple': view.group_bys.length > 0,
      }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-book-stack"></i>
      <span class="header__filter-name">{{
        $tc('viewGroupBy.groupBy', view.group_bys.length, {
          count: view.group_bys.length,
        })
      }}</span>
    </a>
    <ViewGroupByContext
      ref="context"
      :view="view"
      :fields="fields"
      :read-only="readOnly"
      :disable-group-by="disableGroupBy"
      @changed="$emit('changed')"
    ></ViewGroupByContext>
  </div>
</template>

<script>
import ViewGroupByContext from '@baserow/modules/database/components/view/ViewGroupByContext'

export default {
  name: 'ViewGroupBy',
  components: { ViewGroupByContext },
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
    disableGroupBy: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
