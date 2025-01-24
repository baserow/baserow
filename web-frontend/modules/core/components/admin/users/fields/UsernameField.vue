<template functional>
  <div class="user-admin-username" :class="[data.staticClass, data.class]">
    <Avatar
      class="user-admin-username__avatar"
      rounded
      size="large"
      :initials="$options.methods.firstTwoInitials(props.row.name)"
    ></Avatar>
    <div class="user-admin-username__name" :title="props.row.username">
      {{ props.row.username }}
    </div>
    <i
      v-if="props.row.is_staff"
      v-tooltip="parent.$t('user.isStaff')"
      class="user-admin-username__icon iconoir-user-crown"
    ></i>
  </div>
</template>

<script>
export default {
  name: 'UsernameField',
  functional: true,
  props: {
    row: {
      required: true,
      type: Object,
    },
  },
  methods: {
    firstTwoInitials(name) {
      return name
        .split(' ')
        .map((s) => s.slice(0, 1))
        .join('')
        .slice(0, 2)
        .toUpperCase()
    },
  },
}
</script>
