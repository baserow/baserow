<template>
  <li class="tree__item">
    <div class="tree__action sidebar__action sidebar__search">
      <div class="sidebar__search-input" @click="openWorkspaceSearch">
        <i class="sidebar__search-icon iconoir-search"></i>
        <span class="sidebar__search-placeholder">
          {{ $t('workspaceSearch.searchEverything') }}
        </span>
        <div class="sidebar__search-shortcut">
          <kbd>{{ modifierKey }}</kbd
          ><kbd>K</kbd>
        </div>
      </div>
    </div>
  </li>
</template>

<script>
import { isMac } from '@baserow/modules/core/utils/events'

export default {
  name: 'SidebarSearch',

  props: {
    selectedWorkspace: {
      type: Object,
      required: true,
    },
  },

  computed: {
    modifierKey() {
      return isMac() ? '⌘' : 'Ctrl'
    },
  },

  methods: {
    openWorkspaceSearch() {
      this.$emit('open-workspace-search')
    },
  },
}
</script>
