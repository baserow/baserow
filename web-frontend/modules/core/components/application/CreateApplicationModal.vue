<template>
  <Modal @show="loading = false">
    <h2 class="box__title">
      {{ $t('action.createNew') }} {{ applicationType.getName() | lowercase }}
    </h2>
    <Error :error="error"></Error>
    <component
      :is="applicationType.getApplicationFormComponent()"
      ref="applicationForm"
      :default-name="getDefaultName()"
      :loading="loading"
      :workspace="workspace"
      @submitted="submitted"
      @hidden="hide()"
    >
    </component>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'

export default {
  name: 'CreateApplicationModal',
  mixins: [modal, error],
  props: {
    applicationType: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    DEVELOPMENT_STAGES() {
      return DEVELOPMENT_STAGES
    },
  },
  methods: {
    getDefaultName() {
      const excludeNames = this.$store.getters['application/getAllOfWorkspace'](
        this.workspace
      ).map((application) => application.name)
      const baseName = this.applicationType.getDefaultName()
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    async submitted(values) {
      this.loading = true
      this.hideError()

      try {
        const application = await this.$store.dispatch('application/create', {
          type: this.applicationType.type,
          workspace: this.workspace,
          values,
        })
        this.$emit('created', application)
        // select the application just created in the sidebar and open it
        await this.$store.dispatch('application/selectById', application.id)
        await this.$registry
          .get('application', application.type)
          .select(application, this)
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
