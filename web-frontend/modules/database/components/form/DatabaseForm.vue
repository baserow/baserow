<template>
  <div>
    <FormGroup
      :label="$t('databaseForm.importLabel')"
      small-label
      required
      class="margin-bottom-3"
    >
      <ul class="choice-items">
        <li>
          <a
            class="choice-items__link"
            :class="{ active: importType === 'none' }"
            @click="importType = 'none'"
          >
            <i class="choice-items__icon iconoir-copy"></i>
            <span>{{ $t('databaseForm.emptyLabel') }}</span>
            <i
              v-if="importType === 'none'"
              class="choice-items__icon-active iconoir-check-circle"
            ></i>
          </a>
        </li>
        <li>
          <a
            class="choice-items__link"
            :class="{ active: importType === 'airtable' }"
            @click="importType = 'airtable'"
          >
            <i class="choice-items__icon iconoir-copy"></i>
            <span>{{ $t('databaseForm.airtableLabel') }}</span>
            <i
              v-if="importType === 'airtable'"
              class="choice-items__icon-active iconoir-check-circle"
            ></i>
          </a>
        </li>
      </ul>
    </FormGroup>
    <BlankDatabaseForm
      v-if="importType === 'none'"
      ref="blankDatabaseForm"
      :default-name="defaultName"
      :loading="loading"
      @submitted="$emit('submitted', $event)"
    />
    <ImportFromAirtable
      v-else-if="importType === 'airtable'"
      ref="importFromAirtable"
      :loading="loading"
      @hidden="$emit('hidden', $event)"
      @job-updated="$emit('job-updated', $event)"
      @job-done="$emit('job-done', $event)"
      @job-failed="$emit('job-failed', $event)"
      @job-polling-error="$emit('job-failed', $event)"
      @submit="$emit('airtable-submitted', $event)"
    ></ImportFromAirtable>
  </div>
</template>

<script>
import ImportFromAirtable from '@baserow/modules/database/components/airtable/ImportFromAirtable'
import BlankDatabaseForm from '@baserow/modules/database/components/form/BlankDatabaseForm'

export default {
  name: 'DatabaseForm',
  components: { BlankDatabaseForm, ImportFromAirtable },
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      importType: 'none',
    }
  },
  watch: {
    importType() {
      this.$emit('import-type-changed', this.importType)
    },
  },
  methods: {
    submit() {
      if (this.importType === 'none') this.$refs.blankDatabaseForm.submit()
      else if (this.importType === 'airtable')
        this.$refs.importFromAirtable.submit()
    },
  },
}
</script>
