<template>
  <form @submit.prevent="submit" @input="$emit('formchange')">
    <div>
      <Alert v-if="!v$.active.$model" type="info-primary">
        <template #title> {{ $t('webhookForm.deactivated.title') }} </template>
        <p>{{ $t('webhookForm.deactivated.content') }}</p>

        <template #actions>
          <button
            class="alert__actions-button-text"
            @click="v$.active.$model = true"
          >
            {{ $t('webhookForm.deactivated.activate') }}
          </button>
        </template>
      </Alert>
      <div class="row">
        <div class="col col-12">
          <FormGroup
            small-label
            :label="$t('webhookForm.inputLabels.name')"
            :error="v$.name.$error"
            required
            class="margin-bottom-2"
          >
            <FormInput
              v-model="v$.name.$model"
              :error="v$.name.$error"
              @blur="v$.name.$touch"
            ></FormInput>

            <template #error>
              {{ $t('error.requiredField') }}
            </template>
          </FormGroup>
        </div>
        <div class="col col-12">
          <FormGroup
            small-label
            :label="$t('webhookForm.inputLabels.userFieldNames')"
            required
            class="margin-bottom-2"
          >
            <Checkbox v-model="v$.use_user_field_names.$model">{{
              $t('webhookForm.checkbox.sendUserFieldNames')
            }}</Checkbox>
          </FormGroup>
        </div>
        <div class="col col-4">
          <FormGroup
            small-label
            :label="$t('webhookForm.inputLabels.requestMethod')"
            required
            class="margin-bottom-2"
          >
            <Dropdown v-model="v$.request_method.$model">
              <DropdownItem name="GET" value="GET"></DropdownItem>
              <DropdownItem name="POST" value="POST"></DropdownItem>
              <DropdownItem name="PATCH" value="PATCH"></DropdownItem>
              <DropdownItem name="PUT" value="PUT"></DropdownItem>
              <DropdownItem name="DELETE" value="DELETE"></DropdownItem>
            </Dropdown>
          </FormGroup>
        </div>
        <div class="col col-8">
          <FormGroup
            small-label
            :label="$t('webhookForm.inputLabels.url')"
            required
            :error="v$.url.$error"
            class="margin-bottom-2"
          >
            <FormInput
              v-model="values.url"
              :placeholder="$t('webhookForm.inputLabels.url')"
              :error="v$.url.$error"
              @blur="v$.url.$touch"
            ></FormInput>

            <template #error>
              <span
                v-if="
                  v$.url.required.$invalid ||
                  v$.url.isValidURLWithHttpScheme.$invalid
                "
              >
                {{ $t('webhookForm.errors.urlField') }}
              </span>
              <span v-else-if="v$.url.maxLength.$invalid">
                {{
                  $t('error.maxLength', {
                    max: v$.url.$params.maxLength.max,
                  })
                }}
              </span>
            </template>
          </FormGroup>
        </div>
      </div>

      <FormGroup
        small-label
        :label="$t('webhookForm.inputLabels.events')"
        required
        class="margin-bottom-2"
      >
        <RadioGroup
          v-model="v$.include_all_events.$model"
          :options="eventsRadioOptions"
          vertical-layout
        >
        </RadioGroup>
      </FormGroup>

      <div v-if="!values.include_all_events" class="margin-bottom-2">
        <div
          v-for="webhookEvent in webhookEventTypes"
          :key="webhookEvent.type"
          class="webhook__type"
        >
          <Checkbox
            :checked="values.events.includes(webhookEvent.type)"
            @input="
              $event
                ? values.events.push(webhookEvent.type)
                : values.events.splice(
                    values.events.indexOf(webhookEvent.type),
                    1
                  )
            "
            >{{ webhookEvent.getName() }}</Checkbox
          >
          <div
            v-if="webhookEvent.getHasRelatedFields()"
            class="webhook__type-dropdown-container"
          >
            <Dropdown
              :value="
                values.events.includes(webhookEvent.type)
                  ? getEventFields(webhookEvent)
                  : []
              "
              :placeholder="webhookEvent.getRelatedFieldsPlaceholder()"
              :multiple="true"
              :disabled="!values.events.includes(webhookEvent.type)"
              class="dropdown--tiny webhook__type-dropdown"
              @input="setEventFields(webhookEvent, $event)"
            >
              <DropdownItem
                v-for="field in fields"
                :key="field.id"
                :name="field.name"
                :value="field.id"
              >
              </DropdownItem>
            </Dropdown>
            <HelpIcon
              v-if="webhookEvent.getRelatedFieldsHelpText()"
              class="margin-left-1"
              :tooltip="webhookEvent.getRelatedFieldsHelpText()"
            />
          </div>
        </div>
      </div>

      <FormGroup
        small-label
        :label="$t('webhookForm.inputLabels.headers')"
        required
        class="margin-bottom-2"
      >
        <div
          v-for="(header, index) in values.headers"
          :key="`header-input-${index}`"
          class="webhook__header"
        >
          <div class="webhook__header-row">
            <FormInput
              :ref="`headerNameInput${index}`"
              v-model="header.name"
              :error="v$.headers.$each.$response?.$data[index].name.$error"
              class="webhook__header-key"
              :placeholder="$t('webhookForm.inputLabels.name')"
              @blur="v$.headers.$touch"
            />
            <FormInput
              v-model="header.value"
              class="webhook__header-value"
              :error="v$.headers.$each.$response?.$data[index].value.$error"
              :placeholder="$t('webhookForm.inputLabels.value')"
              @blur="v$.headers.$touch"
            />
            <ButtonIcon
              icon="iconoir-bin"
              class="webhook__header-delete"
              @click="removeHeader(index)"
            >
            </ButtonIcon>
          </div>
        </div>

        <ButtonText tag="a" icon="iconoir-plus" @click="addHeader"
          >Add header</ButtonText
        >
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('webhookForm.inputLabels.example')"
        required
        class="margin-bottom-2"
      >
        <div class="webhook__code-with-dropdown">
          <div class="webhook__code-dropdown">
            <Dropdown
              v-model="exampleWebhookEventType"
              class="dropdown--floating-left"
            >
              <DropdownItem
                v-for="webhookEvent in webhookEventTypes"
                :key="webhookEvent.type"
                :name="webhookEvent.getName()"
                :value="webhookEvent.type"
              ></DropdownItem>
            </Dropdown>
          </div>
          <div class="webhook__code-container">
            <pre
              class="webhook__code"
            ><code>{{ JSON.stringify(testExample, null, 4)}}</code></pre>
          </div>
        </div>
      </FormGroup>

      <Button type="secondary" tag="a" @click="openTestModal()">{{
        $t('webhookForm.triggerButton')
      }}</Button>
      <slot></slot>
      <TestWebhookModal ref="testModal" />
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { helpers, required, maxLength } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import TestWebhookModal from '@baserow/modules/database/components/webhook/TestWebhookModal'
import { isValidURLWithHttpScheme } from '@baserow/modules/core/utils/string'

export default {
  name: 'WebhookForm',
  components: {
    Checkbox,
    TestWebhookModal,
  },
  mixins: [form, error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      allowedValues: [
        'name',
        'url',
        'request_method',
        'include_all_events',
        'use_user_field_names',
        'headers',
        'events',
        'event_config',
        'active',
      ],
      values: null,
      v$: null,
      exampleWebhookEventType: '',
      eventsRadioOptions: [
        { value: true, label: this.$t('webhookForm.radio.allEvents') },
        { value: false, label: this.$t('webhookForm.radio.customEvents') },
      ],
    }
  },
  computed: {
    webhookEventTypes() {
      return this.$registry.getAll('webhookEvent')
    },
    /**
     * Generates an example payload of the webhook event based on the chosen webhook
     * event type.
     */
    testExample() {
      if (this.exampleWebhookEventType === '') {
        return {}
      }

      const rowExample = {
        id: 0,
        order: '1.00000000000000000000',
      }
      this.fields.forEach((field) => {
        const fieldType = this.$registry.get('field', field.type)
        const empty = fieldType.getEmptyValue(field)
        rowExample[
          this.values.use_user_field_names ? field.name : `field_${field.id}`
        ] = empty
      })
      const webhookEvent = this.$registry.get(
        'webhookEvent',
        this.exampleWebhookEventType
      )
      return webhookEvent.getExamplePayload(
        this.database,
        this.table,
        rowExample
      )
    },
  },
  created() {
    const values = reactive({
      name: '',
      active: true,
      use_user_field_names: true,
      url: '',
      request_method: 'POST',
      include_all_events: true,
      events: [],
      event_config: [],
      headers: [],
    })

    const rules = computed(() => ({
      name: { required },
      active: {},
      use_user_field_names: {},
      request_method: {},
      include_all_events: {},
      events: {},
      event_config: {},
      url: { required, maxLength: maxLength(2000), isValidURLWithHttpScheme },
      headers: {
        $each: helpers.forEach({
          name: {
            required,
            valid(value) {
              const regex = /[^:\\s][^:\\r\\n]*$/
              return !!value.match(regex)
            },
          },
          value: {
            required,
          },
        }),
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
    const keys = Object.keys(this.webhookEventTypes)
    if (keys.length > 0) {
      this.exampleWebhookEventType = this.webhookEventTypes[keys[0]].type
    }
    // If an headers object is provided as default value, we need to populate the
    // internal headers representation that can be edited by this form. When the form
    // is submitted, it will be converted to the correct structure.
  },
  mounted() {
    if (this.defaultValues.headers) {
      this.values.headers = []
      Object.keys(this.defaultValues.headers).forEach((name) => {
        this.values.headers.push({
          name,
          value: this.defaultValues.headers[name],
        })
      })
    }
  },

  methods: {
    getEventFields(event) {
      const eventConfig = this.values.event_config.find(
        (e) => e.event_type === event.type
      )
      if (eventConfig === undefined) {
        return []
      }
      return eventConfig.fields
    },
    setEventFields(event, fields) {
      const eventConfig = this.values.event_config.find(
        (e) => e.event_type === event.type
      )
      if (eventConfig === undefined) {
        this.values.event_config.push({
          event_type: event.type,
          fields: [],
        })
        return this.setEventFields(event, fields)
      }

      eventConfig.fields = fields
    },
    prepareHeaders(headers) {
      const preparedHeaders = {}
      headers.forEach((header) => {
        if (header.name !== '' && header.value !== '')
          preparedHeaders[header.name] = header.value
      })
      return preparedHeaders
    },
    getFormValues() {
      const values = form.methods.getFormValues.call(this)
      values.headers = this.prepareHeaders(this.values.headers)

      return values
    },
    openTestModal() {
      // The form must be valid we can show the test modal.
      if (!this.isFormValid()) {
        this.v$.$touch()
        return
      }

      const values = this.getFormValues()
      this.$refs.testModal.show(
        this.table.id,
        this.exampleWebhookEventType,
        values
      )
    },
    addHeader() {
      this.values.headers.push({ name: '', value: '' })
      const index = this.values.headers.length - 1

      this.$nextTick(() => {
        this.$refs[`headerNameInput${index}`][0].focus()
      })
    },
    removeHeader(index) {
      this.values.headers.splice(index, 1)
    },
  },
}
</script>
