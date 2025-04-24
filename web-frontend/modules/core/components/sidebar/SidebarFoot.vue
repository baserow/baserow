<template>
  <div class="sidebar__section sidebar__section--bottom">
    <div class="sidebar__foot">
      <div class="sidebar__logo">
        <ExternalLinkBaserowLogo />
      </div>
      <div class="sidebar__foot-links">
        <a
          class="sidebar__foot-link"
          :class="{
            'sidebar__foot-link--loading': undoLoading,
          }"
          @click="undo(false)"
        >
          <i class="sidebar__foot-link-icon iconoir-undo"></i>
        </a>
        <a
          class="sidebar__foot-link"
          :class="{
            'sidebar__foot-link--loading': redoLoading,
          }"
          @click="redo(false)"
        >
          <i class="sidebar__foot-link-icon iconoir-redo"></i>
        </a>
        <template v-if="!collapsed && width > 224">
          <div class="sidebar__foot-separator"></div>
          <a class="sidebar__foot-link" @click="$emit('set-col1-width', 52)">
            <i class="sidebar__foot-link-icon baserow-icon-sidebar"></i>
          </a>
        </template>
        <template v-if="collapsed">
          <div class="sidebar__foot-separator"></div>
          <a class="sidebar__foot-link" @click="$emit('set-col1-width', 240)">
            <i class="sidebar__foot-link-icon baserow-icon-sidebar"></i>
          </a>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import undoRedo from '@baserow/modules/core/mixins/undoRedo'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'

export default {
  name: 'SidebarFoot',
  components: { ExternalLinkBaserowLogo },
  mixins: [undoRedo],
  props: {
    collapsed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    width: {
      type: Number,
      required: true,
    },
  },
}
</script>
