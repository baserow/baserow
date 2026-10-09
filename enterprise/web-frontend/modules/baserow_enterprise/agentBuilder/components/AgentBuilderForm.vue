<template>
  <ApplicationForm
    :default-values="{ name: defaultName }"
    :workspace="workspace"
    :loading="loading"
    @submitted="$emit('submitted', $event)"
  >
    <div class="actions actions--right">
      <Button size="large" :loading="loading" :disabled="loading">
        {{ $t('agentBuilder.createApplication') }}
      </Button>
    </div>
  </ApplicationForm>
</template>

<script setup>
import ApplicationForm from '@baserow/modules/core/components/application/ApplicationForm'

defineProps({
  defaultName: { type: String, default: '' },
  loading: { type: Boolean, required: true },
  workspace: { type: Object, required: true },
})
defineEmits(['submitted'])
</script>
