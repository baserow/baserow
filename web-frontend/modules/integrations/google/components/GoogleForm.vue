<template>
  <div>
    <FormGroup
      :label="$t('googleIntegration.clientMode')"
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.client_mode">
        <DropdownItem
          v-if="context.default_client_available"
          value="default"
          :name="$t('googleIntegration.defaultClient')"
        />
        <DropdownItem
          value="custom"
          :name="$t('googleIntegration.customClient')"
        />
      </Dropdown>
    </FormGroup>
    <template v-if="values.client_mode === 'custom'">
      <FormGroup
        :label="$t('googleIntegration.clientId')"
        class="margin-bottom-2"
        ><FormInput v-model="values.client_id"
      /></FormGroup>
      <FormGroup
        :label="$t('googleIntegration.clientSecret')"
        class="margin-bottom-2"
        ><FormInput
          v-model="values.client_secret"
          type="password"
          autocomplete="new-password"
      /></FormGroup>
    </template>
    <FormGroup
      :label="$t('googleIntegration.redirectUri')"
      class="margin-bottom-2"
      ><code>{{ context.redirect_uri }}</code></FormGroup
    >
    <GoogleConnect
      v-if="savedIntegration"
      :integration="savedIntegration"
      :application="application"
      :disabled="clientChanged"
    />
    <p v-else>{{ $t('googleIntegration.saveFirst') }}</p>
    <p>{{ $t('googleIntegration.saveChanges') }}</p>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref, toRef } from 'vue'
import { useForm } from '@baserow/modules/core/composables/useForm'
import GoogleConnect from '@baserow/modules/integrations/google/components/GoogleConnect'
const props = defineProps({
  defaultValues: { type: Object, default: () => ({}) },
  application: { type: Object, required: true },
})
const emit = defineEmits(['values-changed'])
const { $store, $client } = useNuxtApp()
const values = reactive({
  client_mode: 'custom',
  client_id: '',
  client_secret: null,
})
const form = useForm({
  defaultValues: toRef(props, 'defaultValues'),
  values,
  allowedValues: ['client_mode', 'client_id', 'client_secret'],
  emit,
})
const originalGetFormValues = form.getFormValues.bind(form)
const getFormValues = (...args) => {
  const result = originalGetFormValues(...args)
  if (result.client_secret === null || result.client_secret === '')
    delete result.client_secret
  return result
}
form.getFormValues = getFormValues
defineExpose({ ...form, getFormValues })
const savedIntegration = computed(() =>
  $store.getters['integration/getIntegrations'](props.application).find(
    ({ id }) => id === props.defaultValues.id
  )
)
const clientChanged = computed(
  () =>
    values.client_mode !== savedIntegration.value?.client_mode ||
    values.client_id !== savedIntegration.value?.client_id ||
    !!values.client_secret
)
const config = ref({})
const context = computed(
  () => savedIntegration.value?.context_data || config.value
)
onMounted(async () => {
  if (savedIntegration.value?.context_data) return
  try {
    const { data } = await $client.get('/integrations/google/oauth/config/')
    config.value = data
  } catch {
    /* The saved integration also provides this configuration. */
  }
})
</script>
