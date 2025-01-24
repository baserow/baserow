<template functional>
  <div :class="[data.staticClass, data.class]" v-on="listeners">
    <div v-if="props.row[props.column.key]" class="user-admin-active">
      <i
        class="iconoir-check user-admin-active__icon user-admin-active__icon--activated"
      ></i>
      {{ parent.$t('user.active') }}
    </div>
    <div v-else>
      <i
        class="iconoir-cancel user-admin-active__icon user-admin-active__icon--deactivated"
      ></i>
      {{ parent.$t('user.deactivated') }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'ActiveField',
  functional: true,
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
