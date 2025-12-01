<template>
  <LocalBaserowServiceForm
    ref="form"
    enable-row-id
    v-bind="$attrs"
    :enable-view-picker="false"
    disallow-data-synced-tables
    v-on="$listeners"
  />
</template>

<script>
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'LocalBaserowDeleteRowServiceForm',
  components: {
    LocalBaserowServiceForm,
  },
  methods: {
    isFormValid() {
      return this.$refs.form.isFormValid()
    },
  },
}
</script>
