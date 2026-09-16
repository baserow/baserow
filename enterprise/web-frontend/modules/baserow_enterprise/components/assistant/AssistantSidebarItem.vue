<template>
  <div v-if="isAvailable">
    <li class="tree__item">
      <div class="tree__action">
        <a href="#" class="tree__link" @click.prevent="toggleRightSidebar">
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
        this.$bus.$emit('toggle-right-sidebar', false)
      }
    },
  },
  mounted() {
    if (
      this.isAvailable &&
      localStorage.getItem('baserow.rightSidebarOpen') !== 'false'
    ) {
      // open the right sidebar if the feature is available
      this.$nextTick(this.toggleRightSidebar)
    }
  },
  methods: {
    toggleRightSidebar() {
      this.$bus.$emit('toggle-right-sidebar')
    },
  },
}
</script>
