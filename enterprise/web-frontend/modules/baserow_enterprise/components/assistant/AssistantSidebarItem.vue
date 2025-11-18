<template>
  <div v-if="hasPermission && isConfigured">
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
export default {
  name: 'AssistantSidebarItem',
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
    hasPermission() {
      return this.$hasPermission(
        'assistant.chat',
        this.workspace,
        this.workspace.id
      )
    },
    isConfigured() {
      return this.$config.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL !== null
    },
  },
  mounted() {
    if (
      this.hasPermission &&
      this.isConfigured &&
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
