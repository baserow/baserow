<template>
  <FormGroup
    small-label
    required
    :label="$t('verticalAlignmentSelector.alignment')"
  >
    <Dropdown
      class="control__elements"
      :show-search="false"
      :value="value"
      @input="$emit('input', $event)"
    >
      <DropdownItem
        v-for="alignment in alignmentValues"
        :key="alignment.value"
        :name="$t(alignment.name)"
        :icon="alignment.icon"
        :value="alignment.value"
      />
    </Dropdown>
  </FormGroup>
</template>

<script>
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'VerticalAlignmentSelector',
  emits: ['input'],
  props: {
    value: {
      type: String,
      required: false,
      default: null,
    },
    alignments: {
      type: Object,
      required: false,
      default: () => VERTICAL_ALIGNMENTS,
    },
  },
  computed: {
    alignmentValues() {
      return Object.values(this.alignments)
    },
  },
}
</script>
