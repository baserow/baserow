<template>
  <div class="user-admin-username">
    <Avatar
      class="user-admin-username__avatar"
      rounded
      size="large"
      :initials="firstTwoInitials(row.name)"
    ></Avatar>
    <div class="user-admin-username__name" :title="row.username">
      {{ row.username }}
    </div>
    <i
      v-if="row.is_staff"
      v-tooltip="$t('user.isStaff')"
      class="user-admin-username__icon iconoir-user-crown"
    ></i>
  </div>
</template>

<script>
export default {
  name: 'UsernameField',
  props: {
    row: {
      required: true,
      type: Object,
    },
  },
  methods: {
    firstTwoInitials(name) {
      return (name || '')
        .split(' ')
        .map((s) => s.slice(0, 1))
        .join('')
        .slice(0, 2)
        .toUpperCase()
    },
  },
}
</script>
