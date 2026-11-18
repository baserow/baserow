<template>
  <div class="sidebar-expandable__wrapper">
    <Expandable
      class="sidebar-expandable"
      v-bind="$attrs"
      @toggle="$emit('toggle')"
    >
      <template #header="{ expanded }">
        <div class="sidebar-expandable__header">
          <div
            v-if="showHandle"
            class="sidebar-expandable__handle"
            data-sortable-handle
          />
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
        <div v-if="$slots.default" class="sidebar-expandable__content">
          <slot name="default"></slot>
        </div>
        <div v-if="$slots.footer" class="sidebar-expandable__footer">
          <slot name="footer"></slot>
        </div>
      </template>
    </Expandable>
  </div>
</template>

<script>
export default {
  name: 'SidebarExpandable',
  props: {
    showHandle: { type: Boolean, default: true },
  },
  emits: ['toggle'],
}
</script>
