<template>
  <div class="sidebar-expandable__wrapper">
    <Expandable class="sidebar-expandable" v-bind="$attrs" v-on="$listeners">
      <template #header="{ expanded }">
        <div class="sidebar-expandable__header">
          <div class="sidebar-expandable__handle" data-sortable-handle />
          <div class="sidebar-expandable__header-title">
            <slot name="title"></slot>
          </div>

          <i
            :class="
              expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
            "
          />
        </div>
      </template>
      <template #default>
        <div v-if="hasContentSlot" class="sidebar-expandable__content">
          <slot name="default"></slot>
        </div>
        <div v-if="hasFooterSlot" class="sidebar-expandable__footer">
          <slot name="footer"></slot>
        </div>
      </template>
    </Expandable>
  </div>
</template>

<script>
export default {
  name: 'SidebarExpandable',
  computed: {
    hasFooterSlot() {
      return Boolean(this.$slots.footer)
    },
    hasContentSlot() {
      return Boolean(this.$slots.default)
    },
  },
}
</script>
