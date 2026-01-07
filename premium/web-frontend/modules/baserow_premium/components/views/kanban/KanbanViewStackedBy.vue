<template>
  <div class="kanban-view__stacked-by">
    <div class="kanban-view__stacked-by-title">
      {{ $t('kanbanViewStakedBy.title') }}
    </div>
    <ChooseSingleSelectField
      :view="view"
      :table="table"
      :fields="fields"
      :database="database"
      :value="view.single_select_field"
      :read-only="readOnly"
      :loading="loading"
      @input="update"
    >
      <div class="kanban-view__stacked-by-description">
        {{ $t('kanbanViewStakedBy.chooseField') }}
      </div>
    </ChooseSingleSelectField>
  </div>
</template>

<script>
import kanbanViewHelper from '@baserow_premium/mixins/kanbanViewHelper'
import ChooseSingleSelectField from '@baserow/modules/database/components/field/ChooseSingleSelectField.vue'

export default {
  name: 'KanbanViewStackedBy',
  emits: ['refresh'],
  components: { ChooseSingleSelectField },
  mixins: [kanbanViewHelper],
  props: {
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    includeFieldOptionsOnRefresh: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async update(value) {
      this.loading = true
      await this.updateKanban({
        single_select_field: value,
      })
      this.$emit('refresh', {
        callback: () => {
          this.loading = false
        },
        includeFieldOptions: this.includeFieldOptionsOnRefresh,
      })
    },
  },
}
</script>
