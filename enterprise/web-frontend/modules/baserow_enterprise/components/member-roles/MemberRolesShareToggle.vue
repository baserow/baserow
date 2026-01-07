<template>
  <div class="member-roles-share-toggle">
    <div>
      {{ $t('memberRolesShareToggle.label', { name }) }}
      <div class="member-roles-share-toggle__sub-label">
        {{ $t('memberRolesShareToggle.subLabel', { totalUserAmount }) }}
      </div>
    </div>
    <SwitchInput
      disabled
      small
      :value="toggled"
      @input="$emit('update:toggled', $event)"
    ></SwitchInput>
  </div>
</template>

<script>
export default {
  name: 'MemberRolesShareToggle',
  emits: ['update:toggled'],
  props: {
    name: {
      type: String,
      required: true,
    },
    toggled: {
      type: Boolean,
      required: false,
      default: () => true,
    },
  },
  computed: {
    totalUserAmount() {
      return 5 // TODO
    },
  },
}
</script>
