<template>
  <Button
    type="secondary"
    button-type="button"
    class="member-role-field__link"
    :icon="getRoleIcon(roleUid)"
    append-icon="iconoir-nav-arrow-down"
    :disabled="readOnly"
    aria-haspopup="true"
    @click="$emit('click', $event)"
  >
    {{ roleName }}
  </Button>
</template>

<script setup>
import Button from '@baserow/modules/core/components/Button'
import { getRoleIcon } from '@baserow/modules/core/utils/roles'

defineProps({
  roleUid: { type: String, required: true },
  roleName: { type: String, required: true },
  readOnly: { type: Boolean, default: false },
})
defineEmits(['click'])
</script>
