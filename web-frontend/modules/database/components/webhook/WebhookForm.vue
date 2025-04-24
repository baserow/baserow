<template>
  <form @submit.prevent="submit" @input="$emit('formchange')">
    <div>
      <Alert v-if="!v$.values.active.$model" type="info-primary">
        <template #title> {{ $t('webhookForm.deactivated.title') }} </template>
        <p>{{ $t('webhookForm.deactivated.content') }}</p>

        <template #actions>
          <button
            class="alert__actions-button-text"
            @click="v$.values.active.$model = true"
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
            :error="fieldHasErrors('name')"
            required
            class="margin-bottom-2"
          >
            <FormInput
              v-model="v$.values.name.$model"
              :error="fieldHasErrors('name')"
              @blur="v$.values.name.$touch"
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
            <Checkbox v-model="v$.values.use_user_field_names.$model">{{
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
            <Dropdown v-model="v$.values.request_method.$model">
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
            :error="fieldHasErrors('url')"
            class="margin-bottom-2"
          >
            <FormInput
              v-model="values.url"
              :placeholder="$t('webhookForm.inputLabels.url')"
              :error="fieldHasErrors('url')"
              @blur="v$.values.url.$touch"
            ></FormInput>

            <template #error>
              <span v-if="v$.values.url.required.$invalid">{{
                $t('error.requiredField')
              }}</span>
              <span v-else-if="v$.values.url.maxLength.$invalid">{{
                $t('error.maxLength', {
                  max: v$.values.url.maxLength.$params.max,
                })
              }}</span>
              <span
                v-else-if="v$.values.url.isValidURLWithHttpScheme.$invalid"
                >{{ $t('webhookForm.errors.urlField') }}</span
              >
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
          v-model="v$.values.include_all_events.$model"
          :options="eventsRadioOptions"
          vertical-layout
        >
        </RadioGroup>
      </FormGroup>

      <div v-if="!values.include_all_events" class="margin-bottom-2">
        <div
          v-for="webhookEvent in webhookEventTypes"
          :key="webhookEvent.type"
          v-tooltip="
            webhookEvent.isDeactivated(database.workspace.id)
              ? webhookEvent.getDeactivatedText()
              : null
          "
          class="webhook__type"
          tooltip-position="bottom-cursor"
          @mousedown="
            webhookEvent.isDeactivated(database.workspace.id) &&
              !values.events.includes(webhookEvent.type) &&
              $refs[`${webhookEvent.getName()}DeactivatedClickModal`][0].show()
          "
        >
          <Checkbox
            :checked="values.events.includes(webhookEvent.type)"
            :disabled="
              !values.events.includes(webhookEvent.type) &&
              webhookEvent.isDeactivated(database.workspace.id)
            "
            @input="toggleEventType(webhookEvent, $event)"
          >
            {{ webhookEvent.getName() }}
            <div
              v-if="webhookEvent.isDeactivated(database.workspace.id)"
              class="deactivated-label"
            >
              <i class="iconoir-lock"></i>
            </div>
          </Checkbox>
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
          <div
            v-if="webhookEvent.getHasRelatedView()"
            class="webhook__type-dropdown-container"
          >
            <Dropdown
              :value="
                values.events.includes(webhookEvent.type)
                  ? getEventView(webhookEvent)
                  : null
              "
              :placeholder="webhookEvent.getRelatedViewPlaceholder()"
              :disabled="!values.events.includes(webhookEvent.type)"
              class="dropdown--tiny webhook__type-dropdown"
              @input="setEventView(webhookEvent, $event)"
            >
              <DropdownItem
                v-for="view in filterableViews"
                :key="view.id"
                :name="view.name"
                :value="view.id"
              >
              </DropdownItem>
            </Dropdown>
            <HelpIcon
              v-if="webhookEvent.getRelatedViewHelpText()"
              class="margin-left-1"
              :tooltip="webhookEvent.getRelatedViewHelpText()"
            />
          </div>
          <component
            :is="webhookEvent.getDeactivatedClickModal()[0]"
            v-if="webhookEvent.isDeactivated(database.workspace.id)"
            :ref="`${webhookEvent.getName()}DeactivatedClickModal`"
            :workspace="database.workspace"
            v-bind="webhookEvent.getDeactivatedClickModal()[1]"
          ></component>
        </div>
      </div>

      <FormGroup
        small-label
        :label="$t('webhookForm.inputLabels.headers')"
        required
        class="margin-bottom-2"
      >
        <div
          v-for="(header, index) in headers.concat({
            name: '',
            value: '',
          })"
          :key="`header-input-${index}`"
          class="webhook__header"
        >
          <div class="webhook__header-row">
            <FormInput
              :ref="`headerNameInput${index}`"
              v-model="header.name"
              :error="v$.headers.$each.$response?.$data[index]?.name.$error"
              class="webhook__header-key"
              :placeholder="$t('webhookForm.inputLabels.name')"
              @input="lastHeader(index) && addHeader(header.name, header.value)"
              @blur="!lastHeader(index) && v$.headers.$touch()"
            />
            <FormInput
              v-model="header.value"
              class="webhook__header-value"
              :error="v$.headers.$each.$response?.$data[index]?.value.$error"
              :placeholder="$t('webhookForm.inputLabels.value')"
              @input="lastHeader(index) && addHeader(header.name, header.value)"
              @blur="!lastHeader(index) && v$.headers.$touch()"
            />
            <ButtonIcon
              v-if="!lastHeader(index)"
              icon="iconoir-bin"
              class="webhook__header-delete"
              @click="removeHeader(index)"
            >
            </ButtonIcon>
          </div>
        </div>
        <template #error>
          <div v-if="v$.headers.$error">
            {{ $t('webhookForm.errors.invalidHeaders') }}
          </div>
        </template>
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
import { reactive } from 'vue'
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
    views: {
      type: Array,
      required: true,
    },
  },
  setup() {
    const values = reactive({
      values: {
        name: '',
        active: true,
        use_user_field_names: true,
        url: '',
        request_method: 'POST',
        include_all_events: true,
        events: [],
        event_config: [],
      },
      headers: [],
    })

    const rules = {
      values: {
        name: { required },
        url: {
          required,
          maxLength: maxLength(2000),
          isValidURLWithHttpScheme,
        },
        active: {},
        use_user_field_names: {},
        request_method: {},
        include_all_events: {},
        events: {},
        event_config: {},
      },
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
    }
    return {
      values: values.values,
      headers: values.headers,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
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
    filterableViews() {
      return this.views.filter(
        (view) => this.$registry.get('view', view.type).canFilter
      )
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
        const empty = fieldType.getDefaultValue(field)
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
    const keys = Object.keys(this.webhookEventTypes)
    if (keys.length > 0) {
      this.exampleWebhookEventType = this.webhookEventTypes[keys[0]].type
    }

    // If an headers object is provided as default value, we need to populate the
    // internal headers representation that can be edited by this form. When the form
    // is submitted, it will be converted to the correct structure.
    if (this.defaultValues.headers) {
      Object.keys(this.defaultValues.headers).forEach((name) => {
        this.headers.push({
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
      return eventConfig.fields ?? []
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
    getEventView(event) {
      const eventConfig = this.values.event_config.find(
        (e) => e.event_type === event.type
      )
      if (eventConfig === undefined) {
        return null
      }
      const viewId = eventConfig.views?.[0]
      const view =
        viewId && this.filterableViews.find((view) => view.id === viewId)
      return view?.id || null
    },
    setEventView(event, view) {
      const eventConfig = this.values.event_config.find(
        (e) => e.event_type === event.type
      )
      if (eventConfig === undefined) {
        this.values.event_config.push({
          event_type: event.type,
          views: [],
        })
        return this.setEventView(event, view)
      }
      this.$set(eventConfig, 'views', [view])
    },
    toggleEventType(webhookEvent, event) {
      if (event) {
        this.values.events.push(webhookEvent.type)
      } else {
        this.values.events.splice(
          this.values.events.indexOf(webhookEvent.type),
          1
        )
        this.values.event_config.splice(
          this.values.event_config.indexOf((e) => e.event_type === event.type),
          1
        )
      }
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
      values.headers = this.prepareHeaders(this.headers)
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
    addHeader(name, value) {
      this.headers.push({ name, value })
      const index = this.headers.length - 1

      this.$nextTick(() => {
        this.$refs[`headerNameInput${index}`][0].focus()
      })
    },
    removeHeader(index) {
      this.headers.splice(index, 1)
    },
    lastHeader(index) {
      return index === this.headers.length
    },
  },
}
</script>
