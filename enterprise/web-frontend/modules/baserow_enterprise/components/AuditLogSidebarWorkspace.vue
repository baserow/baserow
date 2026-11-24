<template>
  <li v-if="hasPermission" class="context__menu-item">
    <button
      v-if="deactivated"
      type="button"
      class="context__menu-item-link"
      @click="($refs.paidFeaturesModal.show(), $emit('hide'))"
    >
      <i class="context__menu-item-icon iconoir-lock" aria-hidden="true"></i>
      {{ $t('auditLogSidebarWorkspace.title') }}
    </button>
    <nuxt-link
      v-else
      class="context__menu-item-link"
      exact-active-class="active"
      prefetch-on="interaction"
      :to="{
        name: 'workspace-audit-log',
        params: {
          workspaceId: workspace.id,
        },
      }"
      @click="$emit('hide')"
    >
      <i
        class="context__menu-item-icon baserow-icon-history"
        aria-hidden="true"
      ></i>
      {{ $t('auditLogSidebarWorkspace.title') }}
    </nuxt-link>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :workspace="workspace"
      initial-selected-type="audit_log"
    ></PaidFeaturesModal>
  </li>
</template>

<script>
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'AuditLogSidebarWorkspace',
  components: { PaidFeaturesModal },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['hide'],
  computed: {
    deactivated() {
      return !this.$hasFeature(EnterpriseFeatures.AUDIT_LOG, this.workspace.id)
    },
    hasPermission() {
      return this.$hasPermission(
        'workspace.list_audit_log_entries',
        this.workspace,
        this.workspace.id
      )
    },
  },
}
</script>
