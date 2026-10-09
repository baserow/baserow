<template>
  <Button
    type="secondary"
    button-type="button"
    class="member-role-field__link"
    :icon="icon"
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

defineProps({
  icon: { type: String, default: 'iconoir-shield' },
  roleName: { type: String, required: true },
  readOnly: { type: Boolean, default: false },
})
defineEmits(['click'])
</script>
