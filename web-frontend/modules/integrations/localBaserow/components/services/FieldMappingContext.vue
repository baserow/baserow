<template>
  <Context :overflow-scroll="true" :max-height-if-outside-viewport="true">
    <ul class="context__menu">
      <li class="context__menu-item">
        <a class="context__menu-item-link" @click.prevent="handleEditClick()">
          <i class="context__menu-item-icon" :class="enabledClass"></i>
          {{ toggleEnabledText }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'FieldMappingContext',
  mixins: [context],
  props: {
    fieldMapping: {
      type: Object,
      required: true,
    },
  },
  computed: {
    enabledClass() {
      return this.fieldMapping.enabled ? 'iconoir-eye-off' : 'iconoir-eye-empty'
    },
    toggleEnabledText() {
      return this.fieldMapping.enabled
        ? this.$t('fieldMappingContext.disableField')
        : this.$t('fieldMappingContext.enableField')
    },
  },
  methods: {
    handleEditClick() {
      this.$emit(
        'edit',
        this.fieldMapping.enabled ? undefined : { enabled: true, formula: '' }
      )
      this.hide()
    },
  },
}
</script>
