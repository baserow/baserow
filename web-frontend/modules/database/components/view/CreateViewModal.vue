<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{
        $t('createViewModal.createNew', {
          view: viewType.getName().toLowerCase(),
        })
      }}
    </h2>
    <Error :error="error"></Error>
    <component
      :is="viewType.getViewFormComponent()"
      ref="viewForm"
      :default-name="getDefaultName()"
      :database="database"
      :table="table"
      @submitted="submitted"
    >
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading"
          >
            {{
              $t('createViewModal.add', {
                view: viewType.getName().toLowerCase(),
              })
            }}
          </Button>
        </div>
      </div>
    </component>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'CreateViewModal',
  mixins: [modal, error],
  props: {
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    viewType: {
      type: Object,
      required: true,
    },
  },
  emits: ['created'],
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    getDefaultName() {
      const excludeNames = this.$store.getters['view/getAll'].map(
        (view) => view.name
      )
      const baseName = this.viewType.getName()
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    async submitted(values) {
      this.loading = true
      this.hideError()

      try {
        const { view } = await this.$store.dispatch('view/create', {
          type: this.viewType.type,
          table: this.table,
          values,
        })
        this.loading = false
        this.$emit('created', view)
        this.hide()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'view')
      }
    },
  },
}
</script>
