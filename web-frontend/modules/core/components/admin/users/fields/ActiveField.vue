<template>
  <div class="user-admin-active">
    <i
      v-if="row[column.key]"
      v-tooltip="$t('user.active')"
      class="iconoir-check user-admin-active__icon user-admin-active__icon--activated"
    ></i>
    <i
      v-else
      v-tooltip="$t('user.deactivated')"
      class="iconoir-cancel user-admin-active__icon user-admin-active__icon--deactivated"
    ></i>
  </div>
</template>

<script>
export default {
  name: 'ActiveField',
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
