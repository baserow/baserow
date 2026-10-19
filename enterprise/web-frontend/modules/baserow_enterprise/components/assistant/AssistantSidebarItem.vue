<template>
  <div v-if="isAvailable">
    <li class="tree__item">
      <div class="tree__action">
        <a href="#" class="tree__link" @click.prevent="toggleRightSidebar()">
          <i class="tree__icon iconoir-sparks"></i>
          <span class="tree__link-text">{{
            $t('assistantSidebarItem.title')
          }}</span>
          <i
            v-show="rightSidebarOpen"
            class="tree__icon-right iconoir-view-columns-3"
          ></i>
        </a>
      </div>
    </li>
  </div>
</template>

<script>
import { isAssistantAvailable } from '@baserow_enterprise/utils/assistant'
import {
  getStoredPanelOpen,
  storePanelOpen,
} from '@baserow_enterprise/utils/assistantTabStorage'

export default {
  name: 'AssistantSidebarItem',
  emits: ['toggle-right-sidebar'],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    rightSidebarOpen: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    isAvailable() {
      return isAssistantAvailable(this, this.workspace)
    },
  },
  watch: {
    isAvailable(available) {
      if (!available && this.rightSidebarOpen) {
        this.toggleRightSidebar(false)
      }
    },
    rightSidebarOpen(open) {
      storePanelOpen(open)
    },
  },
  mounted() {
    if (this.isAvailable && this.opensOnLoad()) {
      this.$nextTick(() => this.toggleRightSidebar(true))
    }
  },
  methods: {
    toggleRightSidebar(value) {
      this.$bus.$emit('toggle-right-sidebar', value)
    },
    /**
     * The tab's own state wins, so a reload reopens what this tab showed even
     * when another tab closed the assistant since.
     */
    opensOnLoad() {
      const openInThisTab = getStoredPanelOpen()
      return (
        openInThisTab ??
        localStorage.getItem('baserow.rightSidebarOpen') !== 'false'
      )
    },
  },
}
</script>
