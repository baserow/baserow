<template>
  <div>
    <FormGroup
      :label="$t('smtpForm.host')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('host')"
    >
      <FormInput
        v-model="v$.values.host.$model"
        :placeholder="$t('smtpForm.hostPlaceholder')"
        @blur="v$.values.host.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.port')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('port')"
    >
      <FormInput
        v-model="v$.values.port.$model"
        type="number"
        :placeholder="$t('smtpForm.portPlaceholder')"
        :to-value="(value) => parseInt(value)"
        @blur="v$.values.port.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.security')"
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="security" :show-search="false">
        <DropdownItem
          v-for="option in securityOptions"
          :key="option.value"
          :name="option.name"
          :value="option.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.username')"
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.username"
        :placeholder="$t('smtpForm.usernamePlaceholder')"
      />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.password')"
      small-label
      :helper-text="hasPassword ? $t('smtpForm.passwordConfigured') : ''"
    >
      <FormInput
        v-model="values.password"
        type="password"
        autocomplete="new-password"
        :placeholder="
          hasPassword
            ? $t('smtpForm.passwordKeepPlaceholder')
            : $t('smtpForm.passwordPlaceholder')
        "
      />
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'

// The conventional port for each encryption mode. "None" has no entry: port 25
// is blocked by most hosts, so suggesting it would do more harm than good.
const SECURITY_DEFAULT_PORTS = { starttls: 587, ssl: 465 }

export default {
  name: 'SMTPForm',
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        host: '',
        port: 587,
        use_tls: true,
        use_ssl: false,
        username: '',
        // Untouched (`null`) is dropped on submit to keep the stored password;
        // an empty string clears it.
        password: null,
      },
      allowedValues: [
        'host',
        'port',
        'use_tls',
        'use_ssl',
        'username',
        'password',
      ],
    }
  },
  computed: {
    securityOptions() {
      return [
        { name: this.$t('smtpForm.securityStartTls'), value: 'starttls' },
        { name: this.$t('smtpForm.securitySsl'), value: 'ssl' },
        { name: this.$t('smtpForm.securityNone'), value: 'none' },
      ]
    },
    /**
     * STARTTLS and implicit SSL/TLS are stored as two flags, but only one can
     * be on, so they're edited as a single choice.
     */
    security: {
      get() {
        if (this.values.use_ssl) {
          return 'ssl'
        }
        return this.values.use_tls ? 'starttls' : 'none'
      },
      set(value) {
        // Follow the mode with the port, but only while it's still a
        // conventional one, so a custom port the provider chose is kept.
        const isDefaultPort = Object.values(SECURITY_DEFAULT_PORTS).includes(
          Number(this.values.port)
        )
        if (isDefaultPort && SECURITY_DEFAULT_PORTS[value]) {
          this.values.port = SECURITY_DEFAULT_PORTS[value]
        }
        this.values.use_tls = value === 'starttls'
        this.values.use_ssl = value === 'ssl'
      },
    },
    hasPassword() {
      return this.defaultValues.has_password === true
    },
  },
  methods: {
    getFormValues(deep = false) {
      const values = Object.assign(
        {},
        this.values,
        this.getChildFormsValues(deep)
      )
      if (values.password === null) {
        delete values.password
      }
      return values
    },
  },
  validations() {
    return {
      values: {
        host: { required },
        port: {
          required,
          integer,
          minValue: minValue(1),
          maxValue: maxValue(65535),
        },
        use_tls: {},
        use_ssl: {},
        username: {},
        password: {},
      },
    }
  },
}
</script>
