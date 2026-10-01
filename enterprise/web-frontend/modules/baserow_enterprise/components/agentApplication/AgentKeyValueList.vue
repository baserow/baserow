<template>
  <div class="agent-key-value">
    <div v-for="field in fields" :key="field.key" class="agent-key-value__row">
      <span class="agent-key-value__key">{{ field.key }}</span>
      <span class="agent-key-value__value">
        <span
          v-if="field.kind && CHIP_KINDS.includes(field.kind)"
          class="agent-key-value__chip"
        >
          <Avatar
            v-if="field.kind === 'member'"
            :initials="String(field.value).slice(0, 1).toUpperCase()"
            color="blue"
            size="x-small"
            rounded
          />
          <i v-else :class="CHIP_ICONS[field.kind]"></i>
          {{ field.value }}
        </span>
        <template v-else>{{ field.value }}</template>
      </span>
    </div>
  </div>
</template>

<script>
/**
 * Label/value rows of a trigger or approval preview. Rows, tables and
 * members render as chips like the references in the rest of the app.
 */
const CHIP_KINDS = ['row', 'table', 'member']
const CHIP_ICONS = {
  row: 'iconoir-menu',
  table: 'iconoir-table',
}

export default {
  name: 'AgentKeyValueList',
  props: {
    fields: {
      type: Array,
      required: true,
    },
  },
  data() {
    return { CHIP_KINDS, CHIP_ICONS }
  },
}
</script>
