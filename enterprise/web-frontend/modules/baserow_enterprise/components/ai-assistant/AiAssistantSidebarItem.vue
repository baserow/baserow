<template>
  <div v-if="hasPermission">
    <li
      class="tree__item"
      :class="{
        'tree__item--loading': loading,
        'tree__action--deactivated': deactivated,
      }"
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
            $t('aiAssistantSidebarItem.title')
          }}</span>
        </a>
      </div>
      <PaidFeaturesModal
        ref="paidFeaturesModal"
        :workspace="workspace"
        initial-selected-type="audit_log"
      ></PaidFeaturesModal>
    </li>
  </div>
</template>

<script>
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'AiAssistantSidebarItem',
  components: { PaidFeaturesModal },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    deactivated() {
      return false // TODO
      // return !this.$hasFeature(EnterpriseFeatures.AUDIT_LOG, this.workspace.id)
    },
    hasPermission() {
      return true // TODO
      // return this.$hasPermission(
      //   'workspace.list_audit_log_entries',
      //   this.workspace,
      //   this.workspace.id
      // )
    },
  },
}
</script>
