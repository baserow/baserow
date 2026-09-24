<template>
  <form @submit.prevent>
    <LocalBaserowTableSelector
      v-model="fakeTableId"
      v-model:view-id="values.view_id"
      :databases="databases"
      :service-type="serviceType"
      :display-view-dropdown="enableViewPicker"
    />
    <FormGroup
      v-if="enableRowId"
      small-label
      :label="$t(rowIdLabel)"
      :helper-text="rowIdHelperText"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.row_id"
        :disabled="values.table_id === null"
        :placeholder="$t(rowIdPlaceholder)"
      />
    </FormGroup>
  </form>
</template>

<script>
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import form from '@baserow/modules/core/mixins/form'

/**
 * The purpose of this component is to reuse the concept of a "Local Baserow service form"
 * across our Local Baserow workflow action forms. Upsert (used by Create and Update)
 * and Delete need to be able to manage the table and optional row ID.
 * Rather than duplicate the form a few times, this component keeps things tidier.
 *
 * The databases to pick a table from are passed in: an integration's for the
 * builder and automation, the workspace's for a button field.
 */
export default {
  name: 'LocalBaserowServiceForm',
  components: {
    LocalBaserowTableSelector,
    InjectedFormulaInput,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    serviceType: {
      type: Object,
      required: true,
    },
    enableRowId: {
      type: Boolean,
      required: false,
      default: false,
    },
    rowIdLabel: {
      type: String,
      required: false,
      default: 'localBaserowServiceForm.rowIdLabel',
    },
    rowIdPlaceholder: {
      type: String,
      required: false,
      default: 'localBaserowServiceForm.rowIdPlaceholder',
    },
    rowIdHelperText: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * Whether to show the view picker or not.
     * By default, we do show it, but in some cases,
     * we don't want to allow the user to select a view.
     */
    enableViewPicker: {
      type: Boolean,
      required: false,
      default: true,
    },
    /**
     * The databases to choose a table from, supplied by the wrapper of the
     * application type this form is rendered in.
     */
    databases: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['table-changed'],
  data() {
    const values = { table_id: null }
    const allowedValues = ['table_id']
    if (this.enableRowId) {
      values.row_id = {}
      allowedValues.push('row_id')
    }
    if (this.enableViewPicker) {
      values.view_id = null
      allowedValues.push('view_id')
    }
    return {
      values,
      allowedValues,
    }
  },
  computed: {
    fakeTableId: {
      get() {
        return this.values.table_id
      },
      set(newValue) {
        this.values.table_id = newValue
        // Emit that the table changed so that the parent
        // component can optionally do something with it,
        // e.g. showing a loading spinner.
        this.$emit('table-changed', newValue)
      },
    },
  },
  watch: {
    'values.table_id': {
      handler(newValue, oldValue) {
        if (this.enableRowId && oldValue && newValue !== oldValue) {
          this.values.row_id = {}
        }
      },
    },
  },
}
</script>
