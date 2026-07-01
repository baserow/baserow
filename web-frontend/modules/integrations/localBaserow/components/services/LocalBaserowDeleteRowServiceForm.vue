<template>
  <LocalBaserowServiceForm
    ref="form"
    enable-row-id
    v-bind="$attrs"
    :enable-view-picker="false"
    row-id-label="localBaserowDeleteRowServiceForm.rowIdLabel"
    row-id-placeholder="localBaserowDeleteRowServiceForm.rowIdPlaceholder"
    :row-id-helper-text="
      $t('localBaserowDeleteRowServiceForm.rowIdHelper', {
        limit: batchOperationSizeLimit,
      })
    "
  />
</template>

<script>
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'LocalBaserowDeleteRowServiceForm',
  components: {
    LocalBaserowServiceForm,
  },
  computed: {
    batchOperationSizeLimit() {
      return this.$config.public.integrationLocalBaserowBatchOperationSizeLimit
    },
  },
  methods: {
    isFormValid() {
      return this.$refs.form.isFormValid()
    },
  },
}
</script>
