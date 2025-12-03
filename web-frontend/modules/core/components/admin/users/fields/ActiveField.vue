<template>
  <div>
    <div v-if="row[column.key]" class="user-admin-active">
      <i
        class="iconoir-check user-admin-active__icon user-admin-active__icon--activated"
      ></i>
      {{ $t('user.active') }}
    </div>
    <div v-else>
      <i
        class="iconoir-cancel user-admin-active__icon user-admin-active__icon--deactivated"
      ></i>
      {{ $t('user.deactivated') }}
    </div>
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
