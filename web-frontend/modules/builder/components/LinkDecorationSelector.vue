<template>
  <Dropdown
    :value="linkDecorationValue"
    fixed-items
    @input="$emit('input', $event)"
  >
    <DropdownItem
      v-for="linkDecoration in linkDecorations"
      :key="linkDecoration.type"
      :value="linkDecoration.type"
      :name="linkDecoration.label"
    />
  </Dropdown>
</template>

<script>
import { LINK_DECORATIONS } from '@baserow/modules/builder/enums'

export default {
  name: 'LinkDecorationSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: LINK_DECORATIONS.NORMAL,
    },
  },
  computed: {
    linkDecorations() {
      return [
        {
          type: LINK_DECORATIONS.NORMAL,
          label: this.$i18n.t('linkDecorations.normal'),
        },
        {
          type: LINK_DECORATIONS.PLAIN,
          label: this.$i18n.t('linkDecorations.plain'),
        },
      ]
    },
    linkDecorationValue: {
      get() {
        return this.value
      },
      set(newValue) {
        this.$emit('input', newValue)
      },
    },
  },
}
</script>
