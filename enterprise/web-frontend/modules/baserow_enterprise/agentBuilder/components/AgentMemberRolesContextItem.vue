<template>
  <div>
    <a class="context__menu-item-link" @click="showRoles">
      <i class="context__menu-item-icon iconoir-community"></i>
      {{ $t('memberRolesDatabaseContexItem.label') }}
      <div v-if="deactivated" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
    </a>
    <MemberRolesModal
      ref="memberRolesModal"
      :application="application"
      :agent-definition="agentDefinition"
    />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      initial-selected-type="rbac"
      :workspace="application.workspace"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import MemberRolesModal from '@baserow_enterprise/components/member-roles/MemberRolesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

const props = defineProps({
  application: { type: Object, required: true },
  agentDefinition: { type: Object, required: true },
})
const { $hasFeature } = useNuxtApp()
const memberRolesModal = ref(null)
const paidFeaturesModal = ref(null)
const deactivated = computed(
  () => !$hasFeature(EnterpriseFeatures.RBAC, props.application.workspace.id)
)

function showRoles() {
  if (deactivated.value) {
    paidFeaturesModal.value.show()
  } else {
    memberRolesModal.value.show()
  }
}
</script>
