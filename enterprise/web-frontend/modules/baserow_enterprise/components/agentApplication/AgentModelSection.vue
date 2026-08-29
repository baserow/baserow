<template>
  <div>
    <div v-if="readOnly" class="agent-configuration__read-only-values">
      <div class="agent-configuration__read-only-row">
        <span class="agent-configuration__read-only-label">
          {{ $t('agentModelSection.typeLabel') }}
        </span>
        <span>{{ agent?.ai_generative_ai_type || '—' }}</span>
      </div>
      <div class="agent-configuration__read-only-row">
        <span class="agent-configuration__read-only-label">
          {{ $t('agentModelSection.modelLabel') }}
        </span>
        <span>{{ agent?.ai_generative_ai_model || '—' }}</span>
      </div>
      <div class="agent-configuration__read-only-row">
        <span class="agent-configuration__read-only-label">
          {{ $t('agentModelSection.temperatureLabel') }}
        </span>
        <span>{{ agent?.ai_temperature ?? '—' }}</span>
      </div>
    </div>
    <SelectAIModelForm
      v-else
      :key="reseedKey"
      ref="modelForm"
      :default-values="agentModelValues"
      :database="application"
      @values-changed="onValuesChanged"
    ></SelectAIModelForm>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'
import { notifyIf } from '@baserow/modules/core/utils/error'

const MODEL_FIELDS = [
  'ai_generative_ai_type',
  'ai_generative_ai_model',
  'ai_temperature',
]

/**
 * The backend serializes the temperature as a string while the form emits a
 * number; normalize before comparing so a realtime echo of our own save is
 * never mistaken for a remote change.
 */
function normalizeModelValues(values) {
  const temperature = values.ai_temperature
  return {
    ai_generative_ai_type: values.ai_generative_ai_type ?? null,
    ai_generative_ai_model: values.ai_generative_ai_model ?? null,
    ai_temperature:
      temperature === null || temperature === undefined || temperature === ''
        ? null
        : parseFloat(temperature),
  }
}

export default {
  name: 'AgentModelSection',
  components: { SelectAIModelForm },
  props: {
    application: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      reseedKey: 0,
      lastEmittedValues: null,
      savePending: false,
    }
  },
  computed: {
    agent() {
      return this.$store.getters['agentApplication/getAgent']
    },
    agentModelValues() {
      return normalizeModelValues(
        MODEL_FIELDS.reduce((result, field) => {
          result[field] = this.agent?.[field] ?? null
          return result
        }, {})
      )
    },
  },
  watch: {
    /**
     * Re-seed the form when the agent's model values change remotely (e.g.
     * the agent configuring itself via chat). Never re-key while a user edit
     * is pending, when the store merely caught up with what the form already
     * shows (our own save or its realtime echo), or when the values did not
     * actually change — re-keying remounts the form, which refetches the
     * workspace AI models and re-emits its values.
     */
    agentModelValues(newValues, oldValues) {
      if (isEqual(newValues, oldValues) || this.savePending) {
        return
      }
      if (
        this.lastEmittedValues !== null &&
        isEqual(newValues, this.lastEmittedValues)
      ) {
        return
      }
      this.lastEmittedValues = null
      this.reseedKey += 1
    },
  },
  created() {
    this.debouncedSave = debounce(this.save, 1000)
  },
  beforeUnmount() {
    this.debouncedSave.flush()
  },
  methods: {
    onValuesChanged(values) {
      this.lastEmittedValues = normalizeModelValues(values)
      // The form emits on seed as well; only save when the values actually
      // differ from the agent's current values.
      if (isEqual(this.lastEmittedValues, this.agentModelValues)) {
        return
      }
      this.savePending = true
      this.debouncedSave()
    },
    async save() {
      this.savePending = false
      if (
        !this.agent ||
        this.lastEmittedValues === null ||
        isEqual(this.lastEmittedValues, this.agentModelValues) ||
        !this.$refs.modelForm?.isFormValid()
      ) {
        return
      }
      try {
        await this.$store.dispatch('agentApplication/update', {
          agentId: this.agent.id,
          values: { ...this.lastEmittedValues },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
