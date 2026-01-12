<template>
  <UpsertRowWorkflowActionForm enable-row-id v-bind="$attrs" />
</template>

<script>
import UpsertRowWorkflowActionForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowUpsertRowServiceForm'

export default {
  name: 'LocalBaserowUpdateRowServiceForm',
  components: { UpsertRowWorkflowActionForm },
}
</script>
