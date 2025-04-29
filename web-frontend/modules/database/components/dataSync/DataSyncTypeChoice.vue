<template>
  <li>
    <a
      class="choice-items__link"
      :class="{ active }"
      @click="select(dataSyncType)"
    >
      <i class="choice-items__icon" :class="dataSyncType.iconClass"></i>
      <span> {{ dataSyncType.getName() }}</span>
      <div v-if="deactivated" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
      <i
        v-if="active"
        class="choice-items__icon-active iconoir-check-circle"
      ></i>
    </a>
    <component
      :is="deactivatedClickModal[0]"
      v-if="deactivatedClickModal !== null"
      ref="deactivatedClickModal"
      v-bind="deactivatedClickModal[1]"
      :workspace="database.workspace"
      :name="dataSyncType.getName()"
    ></component>
  </li>
</template>
<script>
export default {
  name: 'DataSyncTypeChoice',
  props: {
    database: {
      type: Object,
      required: true,
    },
    dataSyncType: {
      required: true,
      type: Object,
    },
    active: {
      required: true,
      type: Boolean,
    },
  },
  computed: {
    deactivated() {
      return this.dataSyncType.isDeactivated(this.database.workspace.id)
    },
    deactivatedClickModal() {
      return this.dataSyncType.getDeactivatedClickModal()
    },
  },
  methods: {
    select(dataSyncType) {
      if (dataSyncType.isDeactivated(this.database.workspace.id)) {
        this.$refs.deactivatedClickModal.show()
      } else {
        this.$emit('selected')
      }
    },
  },
}
</script>
