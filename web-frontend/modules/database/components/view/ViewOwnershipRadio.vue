<template>
  <Radio
    v-tooltip="isDeactivated ? viewOwnershipType.getDeactivatedText() : null"
    :model-value="selectedType"
    :value="viewOwnershipType.getType()"
    @input="input"
  >
    <i :class="viewOwnershipType.getIconClass()"></i>
    {{ viewOwnershipType.getName() }}
    <div v-if="isDeactivated" class="deactivated-label">
      <i class="iconoir-lock"></i>
    </div>
    <component
      :is="viewOwnershipType.getDeactivatedModal()[0]"
      v-if="viewOwnershipType.getDeactivatedModal() !== null"
      ref="deactivatedClickModal"
      v-bind="viewOwnershipType.getDeactivatedModal()[1]"
      :name="viewOwnershipType.getFeatureName()"
      :workspace="database.workspace"
    ></component>
  </Radio>
</template>

<script>
import Radio from '@baserow/modules/core/components/Radio'

export default {
  name: 'ViewOwnershipRadio',
  components: { Radio },
  props: {
    viewOwnershipType: {
      type: Object,
      required: true,
    },
    selectedType: {
      type: String,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    isDeactivated() {
      return this.viewOwnershipType.isDeactivated(this.database?.workspace?.id)
    },
  },
  methods: {
    input(value) {
      if (!this.isDeactivated) {
        this.$emit('input', value)
      } else if (this.viewOwnershipType.getDeactivatedModal()) {
        this.$refs.deactivatedClickModal.show()
      }
    },
  },
}
</script>
