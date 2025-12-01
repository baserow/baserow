<template>
  <Badge
    :color="row[column.key].is_enabled ? 'green' : 'neutral'"
    :rounded="true"
  >
    <span v-if="row[column.key].is_enabled">
      {{ $t('twoFactorAuthField.enabled') }}
    </span>
    <span v-else>
      {{ $t('twoFactorAuthField.disabled') }}
    </span>
  </Badge>
</template>

<script>
export default {
  name: 'TwoFactorAuthField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
}
</script>
