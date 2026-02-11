<template>
  <FormGroup
    small-label
    required
    :label="$t('horizontalAlignmentSelector.alignment')"
  >
    <RadioGroup
      v-model="selected"
      :options="alignmentValues"
      type="button"
      @input="$emit('input', $event)"
    >
    </RadioGroup>
  </FormGroup>
</template>

<script>
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'HorizontalAlignmentsSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: null,
    },
    alignments: {
      type: Object,
      required: false,
      default: () => HORIZONTAL_ALIGNMENTS,
    },
  },
  emits: ['input'],
  data() {
    return {
      selected: this.value,
    }
  },
  computed: {
    alignmentValues() {
      const values = Object.values(this.alignments)
      return values.map((value) => {
        return {
          icon: value.icon,
          value: value.value,
          title: this.$t(value.name),
        }
      })
    },
  },
  watch: {
    value: {
      handler(value) {
        this.selected = value
      },
      immediate: true,
    },
  },
}
</script>
