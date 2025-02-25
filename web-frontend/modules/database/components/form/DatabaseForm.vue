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
      :default-name="defaultName"
      :loading="loading"
      @submitted="$emit('submitted', $event)"
    />
    <ImportFromAirtable
      v-else-if="importType === 'airtable'"
      :workspace="workspace"
      @hidden="$emit('hidden', $event)"
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
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      importType: 'none',
    }
  },
}
</script>
