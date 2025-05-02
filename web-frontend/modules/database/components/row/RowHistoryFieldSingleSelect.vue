<template>
  <div class="row-history-entry__field-content">
    <div>
      <div
        v-if="entry.before[fieldIdentifier]"
        class="row-history-field-select-option__diff row-history-field-select-option__diff--removed"
      >
        <div
          class="row-history-field-select-option__diff-inner"
          :class="
            'background-color--' +
            selectOptionColor(entry.before[fieldIdentifier])
          "
        >
          {{ selectOptionValue(entry.before[fieldIdentifier]) }}
        </div>
      </div>
    </div>
    <div>
      <div
        v-if="entry.after[fieldIdentifier]"
        class="row-history-field-select-option__diff row-history-field-select-option__diff--added"
      >
        <div
          class="row-history-field-select-option__diff-inner"
          :class="
            'background-color--' +
            selectOptionColor(entry.after[fieldIdentifier])
          "
        >
          {{ selectOptionValue(entry.after[fieldIdentifier]) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowHistoryFieldSingleSelect',
  props: {
    entry: {
      type: Object,
      required: true,
    },
    fieldIdentifier: {
      type: String,
      required: true,
    },
    field: {
      type: Object,
      required: false,
      default: null,
    },
  },
  methods: {
    selectOptionValue(id) {
      return this.entry.fields_metadata[this.fieldIdentifier]?.select_options[
        id
      ]?.value
    },
    selectOptionColor(id) {
      return this.entry.fields_metadata[this.fieldIdentifier]?.select_options[
        id
      ]?.color
    },
  },
}
</script>
