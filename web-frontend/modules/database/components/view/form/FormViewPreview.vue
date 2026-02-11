<template>
  <div class="form-view__preview">
    <div class="form-view__page form-view__page--rounded">
      <component
        :is="component"
        :database="database"
        :table="table"
        :view="view"
        :fields="fields"
        :store-prefix="storePrefix"
        :read-only="readOnly"
        @ordered-fields="$emit('ordered-fields', $event)"
      ></component>
    </div>
  </div>
</template>

<script>
import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'

export default {
  name: 'FormViewPreview',
  mixins: [formViewHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
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
  },
  emits: ['ordered-fields'],
  computed: {
    component() {
      return this.$registry
        .get('formViewMode', this.view.mode)
        .getPreviewComponent()
    },
  },
}
</script>
