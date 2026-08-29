<template>
  <div class="workflow-editor__trigger-selector" @scroll.stop>
    <GroupedMenu
      ref="groupedMenu"
      :items="items"
      :search-placeholder="searchPlaceholder"
      :empty-text="emptyText"
      @select="$emit('select', $event)"
      @close="$emit('close')"
    />
  </div>
</template>

<script>
import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'

/**
 * The agent equivalent of the automation node picker: the same visual box and
 * grouped menu, but fed plain menu items so it doesn't depend on the
 * automation editor's injected context.
 */
export default {
  name: 'AgentGroupedAddMenu',
  components: { GroupedMenu },
  props: {
    items: {
      type: Array,
      required: true,
    },
    searchPlaceholder: {
      type: String,
      required: false,
      default: '',
    },
    emptyText: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['select', 'close'],
  methods: {
    focus() {
      return this.$refs.groupedMenu?.focus()
    },
  },
}
</script>
