<template>
  <form @submit.prevent="submit">
    <p class="margin-bottom-2 margin-top-3">
      {{ $t('postgreSQLDataSync.description') }}
    </p>
    <FormGroup
      v-for="field in [
        { name: 'postgresql_host', translationPrefix: 'host', type: 'text' },
        {
          name: 'postgresql_username',
          translationPrefix: 'username',
          type: 'text',
        },
        {
          name: 'postgresql_password',
          translationPrefix: 'password',
          type: 'password',
        },
        {
          name: 'postgresql_database',
          translationPrefix: 'database',
          type: 'text',
        },
        {
          name: 'postgresql_schema',
          translationPrefix: 'schema',
          type: 'text',
        },
        { name: 'postgresql_table', translationPrefix: 'table', type: 'text' },
      ]"
      :key="field.name"
      :error="v$[field.name].$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{
        $t(`postgreSQLDataSync.${field.translationPrefix}`)
      }}</template>
      <FormInput
        v-model="v$[field.name].$model"
        size="large"
        :type="field.type"
        :error="v$[field.name].$error"
        @blur="v$[field.name].$touch"
      >
      </FormInput>
      <template #error>
        <div v-if="v$[field.name].required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
      </template>
    </FormGroup>
    <div class="row">
      <div class="col col-5">
        <FormGroup
          :error="v$.postgresql_port.$error"
          required
          small-label
          class="margin-bottom-2"
        >
          <template #label>{{ $t('postgreSQLDataSync.port') }}</template>
          <FormInput
            v-model="v$.postgresql_port.$model"
            size="large"
            :error="v$.postgresql_port.$error"
            @blur="v$.postgresql_port.$touch"
          >
          </FormInput>
          <template #error>
            <div v-if="v$.postgresql_port.required.$invalid">
              {{ $t('error.requiredField') }}
            </div>
            <div v-else-if="v$.postgresql_port.numeric.$invalid">
              {{ $t('error.invalidNumber') }}
            </div>
          </template>
        </FormGroup>
      </div>
      <div class="col col-7">
        <FormGroup required small-label class="margin-bottom-2">
          <template #label>{{ $t('postgreSQLDataSync.sslMode') }}</template>
          <Dropdown v-model="v$.postgresql_sslmode.$model" size="large">
            <DropdownItem
              v-for="option in sslModeOptions"
              :key="option"
              :name="option"
              :value="option"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, numeric } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PostgreSQLDataSync',
  mixins: [form],
  data() {
    return {
      allowedValues: [
        'postgresql_host',
        'postgresql_username',
        'postgresql_password',
        'postgresql_port',
        'postgresql_database',
        'postgresql_schema',
        'postgresql_table',
        'postgresql_sslmode',
      ],
      values: null,
      v$: null,
      sslModeOptions: [
        'disable',
        'allow',
        'prefer',
        'require',
        'verify-ca',
        'verify-full',
      ],
    }
  },
  created() {
    const values = reactive({
      postgresql_host: '',
      postgresql_username: '',
      postgresql_password: '',
      postgresql_port: '5432',
      postgresql_database: '',
      postgresql_schema: 'public',
      postgresql_table: '',
      postgresql_sslmode: 'prefer',
    })

    const rules = computed(() => ({
      postgresql_host: { required },
      postgresql_username: { required },
      postgresql_password: { required },
      postgresql_database: { required },
      postgresql_schema: { required },
      postgresql_table: { required },
      postgresql_sslmode: { required },
      postgresql_port: { required, numeric },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
