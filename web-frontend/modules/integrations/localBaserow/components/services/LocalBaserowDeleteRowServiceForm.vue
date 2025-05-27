<template>
  <LocalBaserowServiceForm
    enable-row-id
    v-bind="$attrs"
    :application="application"
    v-on="$listeners"
  />
</template>

<script>
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'DeleteRowWorkflowActionForm',
  components: {
    LocalBaserowServiceForm,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
}
</script>
