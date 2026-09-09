<template>
  <Dropdown v-model="selectedRole" :show-search="false" fixed-items>
    <DropdownItem
      v-for="role in roles"
      :key="role.uid"
      :ref="`role${role.uid}`"
      :name="role.name"
      :value="role.uid"
      :disabled="role.isDeactivated"
      :description="role.description"
      @click="clickOnDeactivatedItem($event)"
    >
      {{ role.name }}
      <Badge
        v-if="showCommercialInfo && role.showIsBillable && role.isBillable"
        color="cyan"
        size="small"
        bold
      >
        {{ $t('common.billable') }}
      </Badge>
      <Badge
        v-else-if="
          showCommercialInfo &&
          role.showIsBillable &&
          !role.isBillable &&
          atLeastOneBillableRole
        "
        color="yellow"
        size="small"
        bold
        class="margin-left-1"
      >
        {{ $t('common.free') }}
      </Badge>
      <i v-if="role.isDeactivated" class="iconoir-lock"></i>
      <component
        :is="deactivatedClickModal(role)?.[0]"
        v-if="deactivatedClickModal(role)"
        :ref="`deactivatedClickModal-${role.uid}`"
        v-bind="deactivatedClickModal(role)?.[1]"
        :workspace="workspace"
      />
    </DropdownItem>
  </Dropdown>
</template>

<script>
export default {
  name: 'WorkspaceRoleSelector',
  props: {
    modelValue: {
      type: String,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
    roles: {
      type: Array,
      required: true,
    },
    showCommercialInfo: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:modelValue'],
  computed: {
    selectedRole: {
      get() {
        return this.modelValue
      },
      set(value) {
        this.$emit('update:modelValue', value)
      },
    },
    atLeastOneBillableRole() {
      return this.roles.some((role) => role.isBillable)
    },
  },
  methods: {
    deactivatedClickModal(role) {
      return Object.values(this.$registry.getAll('roles'))
        .find((registeredRole) => registeredRole.getUid() === role.uid)
        ?.getDeactivatedClickModal()
    },
    clickOnDeactivatedItem(value) {
      const role = this.roles.find((role) => role.uid === value)
      if (!role?.isDeactivated) {
        return
      }
      this.$refs[`deactivatedClickModal-${value}`]?.[0]?.show()
    },
  },
}
</script>
