<template>
  <div class="row-history-entry">
    <div class="row-history-entry__header">
      <span class="row-history-entry__initials">{{ initials }}</span>
      <span class="row-history-entry__name">{{ name }} {{ actionName }}</span>
      <span class="row-history-entry__timestamp" :title="timestampTooltip">{{
        formattedTimestamp
      }}</span>
    </div>
    <template v-if="hasContent">
      <div class="row-history-entry__content">
        <template v-for="fieldIdentifier in entryFields">
          <template
            v-if="
              getFieldName(fieldIdentifier) &&
              getEntryComponent(fieldIdentifier)
            "
          >
            <div :key="fieldIdentifier" class="row-history-entry__field">
              {{ getFieldName(fieldIdentifier) }}
            </div>
            <component
              :is="getEntryComponent(fieldIdentifier)"
              :key="fieldIdentifier + 'content'"
              :entry="entry"
              :workspace-id="workspaceId"
              :field-identifier="fieldIdentifier"
              :field="getField(fieldIdentifier)"
            ></component>
          </template>
        </template>
      </div>
    </template>
  </div>
</template>

<script>
import _ from 'lodash'
import moment from '@baserow/modules/core/moment'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

const actioNameMapping = {
  create_rows: 'created',
  create_row: 'created',
  submit_form: 'submitted',
  update_rows: 'updated',
  update_row: 'updated',
  delete_row: 'deleted',
  delete_rows: 'deleted',
  restore_from_trash: 'restored',
  removedCreated: 'removedCreated',
}

export default {
  name: 'RowHistoryEntry',
  mixins: [collaboratorName],
  props: {
    workspaceId: {
      type: Number,
      required: true,
    },
    entry: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  computed: {
    name() {
      if (this.entry.user.id === this.$store.getters['auth/getUserObject'].id) {
        return this.$t('rowHistorySidebar.you')
      }
      return this.getCollaboratorName(this.entry.user, this.store)
    },
    initials() {
      return this.name.slice(0, 1).toUpperCase()
    },
    timestampTooltip() {
      return this.getLocalizedMoment(this.entry.timestamp).format('L LT')
    },
    formattedTimestamp() {
      return this.getLocalizedMoment(this.entry.timestamp).format('LT')
    },
    entryFields() {
      return new Set(
        Object.keys(this.entry.before).concat(Object.keys(this.entry.after))
      )
    },
    hasContent() {
      return !_.isEmpty(this.entry.before) || !_.isEmpty(this.entry.after)
    },
    actionName() {
      const actionCommandType = this.entry.action_command_type
      let actionName = actioNameMapping[this.entry.action_type]
      if (actionCommandType === 'UNDO') {
        actionName = `${actionName}Undo`
      }
      return this.$t(`rowHistorySidebar.${actionName}`)
    },
  },
  methods: {
    getLocalizedMoment(timestamp) {
      return moment.utc(timestamp).tz(moment.tz.guess())
    },
    getFieldName(fieldIdentifier) {
      const field = this.getField(fieldIdentifier)
      if (field) {
        return field.name
      }
      return null
    },
    getField(fieldIdentifier) {
      const id = this.entry.fields_metadata[fieldIdentifier].id
      const field = this.fields.find((f) => f.id === id)
      return field
    },
    getEntryComponent(fieldIdentifier) {
      const fieldMetadata = this.entry.fields_metadata[fieldIdentifier]
      const type = fieldMetadata.type
      const fieldType = this.$registry.get('field', type)
      if (fieldType) {
        return fieldType.getRowHistoryEntryComponent(fieldMetadata)
      }
      return null
    },
  },
}
</script>
