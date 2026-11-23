<template>
  <div>
    <LocalBaserowServiceForm
      ref="tableForm"
      :application="application"
      :default-values="service"
      :enable-view-picker="false"
      :service-type="serviceType"
      :databases="databases"
      :form-choices-error="
        formChoicesError || serviceType.getCommentAccessError(service) || ''
      "
      @values-changed="$emit('values-changed', $event)"
    />
    <Checkbox
      :model-value="service.only_when_mentioned"
      :disabled="!targetName && !service.only_when_mentioned"
      @update:model-value="
        $emit('values-changed', { only_when_mentioned: $event })
      "
    >
      {{
        targetName
          ? $t('rowCommentTrigger.onlyWhenMentioned', { name: targetName })
          : $t('rowCommentTrigger.noMentionTarget')
      }}
    </Checkbox>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

const props = defineProps({
  application: { type: Object, required: true },
  service: { type: Object, required: true },
  serviceType: { type: Object, required: true },
  databases: { type: Array, default: () => [] },
  formChoicesError: { type: String, default: '' },
  mentionName: { type: String, default: null },
})
defineEmits(['values-changed'])
const store = useStore()
const { $registry } = useNuxtApp()
const targetName = computed(() => {
  if (props.application.type === 'agent')
    return props.formChoicesError ? null : props.mentionName
  const subject = store.getters['integration/getIntegrationById'](
    props.application,
    props.service.integration_id
  )?.authorized_subject
  return subject && !subject.trashed
    ? $registry.get('subject', subject.type).getDisplayName(subject)
    : null
})
const tableForm = ref(null)
defineExpose({ isFormValid: (deep) => tableForm.value?.isFormValid(deep) })
</script>
