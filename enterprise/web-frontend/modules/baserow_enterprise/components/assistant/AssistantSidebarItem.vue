<template>
  <div v-if="hasPermission">
    <li
      class="tree__item"
      :class="{ 'tree__action--deactivated': deactivated }"
    >
      <div class="tree__action">
        <a
          v-if="deactivated"
          href="#"
          class="tree__link"
          @click.prevent="$refs.paidFeaturesModal.show()"
        >
          <i class="tree__icon iconoir-lock"></i>
          <span class="tree__link-text">{{
            $t('assistantSidebarItem.title')
          }}</span>
        </a>
        <a
          v-else
          href="#"
          class="tree__link"
          @click.prevent="toggleRightSidebar"
        >
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
      <PaidFeaturesModal
        ref="paidFeaturesModal"
        :workspace="workspace"
        initial-selected-type="assistant"
      ></PaidFeaturesModal>
    </li>
  </div>
</template>

<script>
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'AssistantSidebarItem',
  components: { PaidFeaturesModal },
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
    deactivated() {
      return !this.$hasFeature(EnterpriseFeatures.ASSISTANT, this.workspace.id)
    },
    hasPermission() {
      return this.$hasPermission(
        'assistant.chat',
        this.workspace,
        this.workspace.id
      )
    },
  },
  mounted() {
    if (
      this.hasPermission &&
      !this.deactivated &&
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
