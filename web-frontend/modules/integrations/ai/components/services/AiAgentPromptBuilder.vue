<template>
  <div>
    <div
      v-if="
        signatureFields &&
        signatureFields.inputs &&
        signatureFields.inputs.length > 0
      "
    >
      <FormGroup
        v-for="(field, index) in signatureFields.inputs"
        :key="field.uid || index"
        small-label
        required
        class="margin-bottom-2"
        :label="getFieldLabel(field)"
      >
        <template v-if="field.description" #help>
          {{ field.description }}
        </template>
        <template v-if="field.type === 'choice'">
          <Dropdown
            v-model="promptValues[field.name]"
            :fixed-items="true"
            @input="emitChange"
          >
            <DropdownItem
              v-for="(option, optionIndex) in field.options"
              :key="optionIndex"
              :name="option"
              :value="option"
            />
          </Dropdown>
        </template>
        <template v-else-if="field.type === 'number'">
          <InjectedFormulaInput
            v-model="promptValues[field.name]"
            :placeholder="$t('aiAgentPromptBuilder.numberPlaceholder')"
            @input="emitChange"
          />
        </template>
        <template v-else>
          <InjectedFormulaInput
            v-model="promptValues[field.name]"
            :placeholder="$t('aiAgentPromptBuilder.stringPlaceholder')"
            @input="emitChange"
          />
        </template>
      </FormGroup>
    </div>
    <div v-else class="margin-bottom-2">
      <p class="color-neutral">
        {{ $t('aiAgentPromptBuilder.noInputsDefined') }}
      </p>
    </div>
  </div>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'AiAgentPromptBuilder',
  components: {
    InjectedFormulaInput,
  },
  props: {
    signatureFields: {
      type: Object,
      required: false,
      default: () => ({ inputs: [], outputs: [] }),
    },
    value: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      promptValues: {},
    }
  },
  watch: {
    value: {
      immediate: true,
      deep: true,
      handler(newValue) {
        if (newValue) {
          this.promptValues = { ...newValue }
        }
      },
    },
    signatureFields: {
      immediate: true,
      deep: true,
      handler(newFields) {
        // Initialize prompt values for new fields
        if (newFields && newFields.inputs) {
          newFields.inputs.forEach((field) => {
            if (!(field.name in this.promptValues)) {
              this.$set(this.promptValues, field.name, '')
            }
          })
          // Remove values for fields that no longer exist
          Object.keys(this.promptValues).forEach((key) => {
            if (!newFields.inputs.find((f) => f.name === key)) {
              this.$delete(this.promptValues, key)
            }
          })
        }
      },
    },
  },
  methods: {
    getFieldLabel(field) {
      return field.name.charAt(0).toUpperCase() + field.name.slice(1)
    },
    emitChange() {
      this.$emit('input', this.promptValues)
    },
  },
}
</script>
