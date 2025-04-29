<template>
  <nuxt-link
    v-if="hasPermission"
    v-slot="{ href, navigate, isExactActive }"
    :to="{
      name: 'workspace-audit-log',
      params: {
        workspaceId: workspace.id,
      },
    }"
  >
    <li
      class="tree__item"
      :class="{
        'tree__item--loading': loading,
        'tree__action--deactivated': deactivated,
        active: isExactActive,
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
            $t('auditLogSidebarWorkspace.title')
          }}</span>
        </a>
        <a v-else :href="href" class="tree__link" @click="navigate">
          <i class="tree__icon baserow-icon-history"></i>
          <span class="tree__link-text">{{
            $t('auditLogSidebarWorkspace.title')
          }}</span>
        </a>
      </div>
      <PaidFeaturesModal
        ref="paidFeaturesModal"
        :workspace="workspace"
        initial-selected-type="audit_log"
      ></PaidFeaturesModal>
    </li>
  </nuxt-link>
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
  data() {
    return {
      loading: false,
    }
  },
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
