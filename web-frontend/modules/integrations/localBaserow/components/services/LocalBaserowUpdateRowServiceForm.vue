<template>
  <UpsertRowWorkflowActionForm
    enable-row-id
    v-bind="$attrs"
    v-on="$listeners"
  />
</template>

<script>
import UpsertRowWorkflowActionForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowUpsertRowServiceForm.vue'

export default {
  name: 'UpdateRowWorkflowAction',
  components: { UpsertRowWorkflowActionForm },
}
</script>
