<template>
  <GridViewRowExpandButton
    v-if="
      !row ||
      !rowCommentCount ||
      !$hasPermission('database.table.list_comments', table, workspaceId)
    "
    :row="row"
    v-bind="$attrs"
    @edit-modal="$emit('edit-modal')"
  />
  <a
    v-else
    class="row-comments-expand-button"
    :title="rowCommentCount + ' comments'"
    @click="onEditModalClick"
  >
    <template v-if="rowCommentCount < 100">
      {{ rowCommentCount }}
    </template>
    <i v-else class="row-comments-expand-button__icon iconoir-multi-bubble"></i>
  </a>
</template>
<script>
import GridViewRowExpandButton from '@baserow/modules/database/components/view/grid/GridViewRowExpandButton'

export default {
  name: 'GridViewRowExpandButtonWithCommentCount',
  emits: ['edit-modal'],
  components: { GridViewRowExpandButton },
  inject: { $hasPermission: '$hasPermission' },
  props: {
    row: {
      type: Object,
      required: false,
      default: null,
    },
    table: {
      type: Object,
      required: false,
      default: null,
    },
    workspaceId: {
      type: [Number, String],
      required: false,
      default: null,
    },
  },
  computed: {
    rowCommentCount() {
      if (!this.row || !this.row._ || !this.row._.metadata) {
        return null
      }
      return this.row._.metadata.row_comment_count
    },
  },
  methods: {
    onEditModalClick() {
      this.$emit('edit-modal')
    },
  },
}
</script>
