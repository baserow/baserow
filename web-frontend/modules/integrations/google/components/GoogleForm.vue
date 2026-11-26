<template>
  <div>
    <FormGroup
      :label="$t('googleIntegration.clientMode')"
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.client_mode">
        <DropdownItem
          v-if="context.configured"
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
    <OAuthAccountForm
      v-if="savedIntegration && !clientChanged"
      :default-values="savedIntegration"
      :integration-type="integrationType"
      :application="application"
    />
    <p v-else>{{ $t('googleIntegration.saveFirst') }}</p>
    <p>{{ $t('googleIntegration.saveChanges') }}</p>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref, toRef } from 'vue'
import { useForm } from '@baserow/modules/core/composables/useForm'
import OAuthAccountForm from '@baserow/modules/integrations/oauthAccount/components/OAuthAccountForm'
import OAuthAccountService from '@baserow/modules/integrations/oauthAccount/services/oauthAccount'
const props = defineProps({
  defaultValues: { type: Object, default: () => ({}) },
  application: { type: Object, required: true },
})
const emit = defineEmits(['values-changed'])
const { $store, $client, $registry } = useNuxtApp()
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
const integrationType = $registry.get('integration', 'google')
const context = computed(() => config.value)
onMounted(async () => {
  try {
    const { data } = await OAuthAccountService($client, 'google').getConfig()
    config.value = data
  } catch {
    /* The shared account form reports unavailable configuration. */
  }
})
</script>
