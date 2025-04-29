<template>
  <li v-if="!isFieldReadOnly(field)" class="context__menu-item">
    <FieldPermissionsModal
      ref="editFieldPermissionsModal"
      :field="field"
      :workspace-id="database.workspace.id"
    />
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :workspace="database.workspace"
      :initial-selected-type="featureName"
    />
    <a class="context__menu-item-link" @click="onClick">
      <i class="context__menu-item-icon iconoir-lock"></i>
      {{ $t('fieldPermissionsMenuItem.label') }}
      <div v-if="deactivated" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
    </a>
  </li>
</template>

<script>
import FieldPermissionsModal from '@baserow_enterprise/components/fieldPermissions/FieldPermissionsModal'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { FieldLevelPermissionsPaidFeature } from '@baserow_enterprise/paidFeatures'

export default {
  name: 'FieldPermissionsContextItem',
  components: {
    FieldPermissionsModal,
    PaidFeaturesModal,
  },
  props: {
    field: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    featureName() {
      return FieldLevelPermissionsPaidFeature.getType()
    },
    deactivated() {
      return this.isDeactivated(this.database.workspace.id)
    },
  },
  methods: {
    isFieldReadOnly(field) {
      return this.$registry.get('field', field.type).isReadOnlyField(field)
    },
    isDeactivated(workspaceId) {
      return !this.$hasFeature(
        EnterpriseFeatures.FIELD_LEVEL_PERMISSIONS,
        workspaceId
      )
    },
    onClick() {
      if (this.deactivated) {
        this.$refs.paidFeaturesModal.show()
      } else {
        this.$refs.editFieldPermissionsModal.show()
        this.$emit('hide-context')
      }
    },
  },
}
</script>
