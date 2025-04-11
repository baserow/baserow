<template>
  <li v-if="!isFieldReadOnly(field)" class="context__menu-item">
    <FieldPermissionModal
      ref="editFieldPermissionModal"
      :field="field"
      :workspace-id="database.workspace.id"
    />
    <a
      class="context__menu-item-link"
      @click="
        $refs.editFieldPermissionModal.show()
        $emit('hide-context')
      "
    >
      <i class="context__menu-item-icon iconoir-lock"></i>
      {{ $t('fieldPermissionMenuItem.label') }}
    </a>
  </li>
</template>

<script>
import FieldPermissionModal from '@baserow_enterprise/components/field-permissions/FieldPermissionModal'

export default {
  name: 'FieldPermissionMenuItem',
  components: {
    FieldPermissionModal,
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
  methods: {
    isFieldReadOnly(field) {
      return this.$registry.get('field', field.type).isReadOnlyField(field)
    },
  },
}
</script>
