<template>
  <div>
    <Alert v-if="!hasValidSignature" type="error" class="margin-bottom-2">
      {{ $t('aiAgentSignatureBuilder.errorNoValidSignature') }}
    </Alert>
    <FormSection
      class="margin-bottom-2"
      :title="$t('aiAgentSignatureBuilder.inputsTitle')"
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('aiAgentSignatureBuilder.inputsDescription') }}
      </p>
      <div v-if="inputs.length > 0">
        <SidebarExpandable
          v-for="(field, index) in inputs"
          :key="field.uid"
          v-sortable="{
            id: field.uid,
            update: orderInputs,
            enabled: true,
            handle: '[data-sortable-handle]',
          }"
          :default-expanded="index === 0"
          toggle-on-click
        >
          <template #title>
            <span v-if="field.name">{{ field.name }}</span>
            <span v-else class="color-neutral">{{
              $t('aiAgentSignatureBuilder.unnamedField')
            }}</span>
            <span v-if="field.type" class="margin-left-1 color-neutral-dark">
              ({{ $t(`aiAgentSignatureBuilder.${field.type}FieldType`) }})
            </span>
            <Icon
              v-if="getFieldErrorMessage(field, 'input')"
              :key="getFieldErrorMessage(field, 'input')"
              v-tooltip="getFieldErrorMessage(field, 'input')"
              icon="iconoir-warning-circle"
              size="medium"
              type="error"
            />
          </template>
          <template #default>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldName')"
              :error-message="getFieldNameError(index, 'input')"
            >
              <FormInput
                v-model="inputs[index].name"
                @input="emitChange"
              ></FormInput>
            </FormGroup>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldType')"
            >
              <Dropdown
                v-model="inputs[index].type"
                :fixed-items="true"
                @input="handleTypeChange(index, 'input')"
              >
                <DropdownItem name="String" :value="'string'" />
                <DropdownItem name="Number" :value="'number'" />
                <DropdownItem name="Boolean" :value="'boolean'" />
              </Dropdown>
            </FormGroup>
            <FormGroup
              small-label
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldDescription')"
            >
              <FormInput
                v-model="inputs[index].description"
                :placeholder="
                  $t('aiAgentSignatureBuilder.fieldDescriptionPlaceholder')
                "
                @input="emitChange"
              ></FormInput>
            </FormGroup>
            <FormGroup
              v-if="inputs[index].type === 'choice'"
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.choiceOptions')"
            >
              <div class="signature-choice-options">
                <div
                  v-for="(option, optionIndex) in inputs[index].options"
                  :key="optionIndex"
                  class="signature-choice-option"
                >
                  <FormInput
                    v-model="inputs[index].options[optionIndex]"
                    :placeholder="
                      $t('aiAgentSignatureBuilder.choiceOptionPlaceholder')
                    "
                    @input="emitChange"
                  />
                  <ButtonIcon
                    tag="a"
                    icon="iconoir-cancel"
                    @click.stop.prevent="
                      removeOption(index, optionIndex, 'input')
                    "
                  ></ButtonIcon>
                </div>
              </div>
              <ButtonText
                icon="iconoir-plus"
                tag="a"
                size="small"
                @click="addOption(index, 'input')"
              >
                {{ $t('aiAgentSignatureBuilder.addOption') }}
              </ButtonText>
            </FormGroup>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldValue')"
              :error-message="getFieldValueError(index)"
            >
              <template v-if="inputs[index].type === 'choice'">
                <Dropdown
                  v-model="inputs[index].value"
                  :fixed-items="true"
                  @input="emitChange"
                >
                  <DropdownItem
                    v-for="(option, optionIndex) in inputs[index].options"
                    :key="optionIndex"
                    :name="option"
                    :value="option"
                  />
                </Dropdown>
              </template>
              <template v-else-if="inputs[index].type === 'boolean'">
                <Dropdown
                  v-model="inputs[index].value"
                  :fixed-items="true"
                  @input="emitChange"
                >
                  <DropdownItem name="True" :value="'true'" />
                  <DropdownItem name="False" :value="'false'" />
                </Dropdown>
              </template>
              <template v-else-if="inputs[index].type === 'number'">
                <InjectedFormulaInput
                  v-model="inputs[index].value"
                  :placeholder="
                    $t('aiAgentSignatureBuilder.numberValuePlaceholder')
                  "
                  @input="emitChange"
                />
              </template>
              <template v-else>
                <InjectedFormulaInput
                  v-model="inputs[index].value"
                  :placeholder="
                    $t('aiAgentSignatureBuilder.stringValuePlaceholder')
                  "
                  @input="emitChange"
                />
              </template>
            </FormGroup>
          </template>
          <template #footer>
            <ButtonText icon="iconoir-bin" @click="removeField(index, 'input')">
              {{ $t('action.delete') }}
            </ButtonText>
          </template>
        </SidebarExpandable>
      </div>
      <div v-else class="margin-bottom-2">
        <p class="color-neutral">
          {{ $t('aiAgentSignatureBuilder.noInputsYet') }}
        </p>
      </div>
      <ButtonText
        type="primary"
        icon="iconoir-plus"
        size="small"
        @click="addInput"
      >
        {{ $t('aiAgentSignatureBuilder.addInput') }}
      </ButtonText>
    </FormSection>

    <FormSection
      class="margin-bottom-2"
      :title="$t('aiAgentSignatureBuilder.outputsTitle')"
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('aiAgentSignatureBuilder.outputsDescription') }}
      </p>
      <div v-if="outputs.length > 0">
        <SidebarExpandable
          v-for="(field, index) in outputs"
          :key="field.uid"
          v-sortable="{
            id: field.uid,
            update: orderOutputs,
            enabled: true,
            handle: '[data-sortable-handle]',
          }"
          :default-expanded="index === 0"
          toggle-on-click
        >
          <template #title>
            <span v-if="field.name">{{ field.name }}</span>
            <span v-else class="color-neutral">{{
              $t('aiAgentSignatureBuilder.unnamedField')
            }}</span>
            <span v-if="field.type" class="margin-left-1 color-neutral-dark">
              ({{ $t(`aiAgentSignatureBuilder.${field.type}FieldType`) }})
            </span>
            <Icon
              v-if="getFieldErrorMessage(field, 'output')"
              :key="getFieldErrorMessage(field, 'output')"
              v-tooltip="getFieldErrorMessage(field, 'output')"
              icon="iconoir-warning-circle"
              size="medium"
              type="error"
            />
          </template>
          <template #default>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldName')"
              :error-message="getFieldNameError(index, 'output')"
            >
              <FormInput
                v-model="outputs[index].name"
                @input="emitChange"
              ></FormInput>
            </FormGroup>
            <FormGroup
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldType')"
            >
              <Dropdown
                v-model="outputs[index].type"
                :fixed-items="true"
                @input="handleTypeChange(index, 'output')"
              >
                <DropdownItem name="String" :value="'string'" />
                <DropdownItem name="Number" :value="'number'" />
                <DropdownItem name="Boolean" :value="'boolean'" />
                <DropdownItem name="Choice" :value="'choice'" />
              </Dropdown>
            </FormGroup>
            <FormGroup
              small-label
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.fieldDescription')"
            >
              <FormInput
                v-model="outputs[index].description"
                :placeholder="
                  $t('aiAgentSignatureBuilder.fieldDescriptionPlaceholder')
                "
                @input="emitChange"
              ></FormInput>
            </FormGroup>
            <FormGroup
              v-if="outputs[index].type === 'choice'"
              small-label
              required
              class="margin-bottom-2"
              :label="$t('aiAgentSignatureBuilder.choiceOptions')"
            >
              <div class="signature-choice-options">
                <div
                  v-for="(option, optionIndex) in outputs[index].options"
                  :key="optionIndex"
                  class="signature-choice-option"
                >
                  <FormInput
                    v-model="outputs[index].options[optionIndex]"
                    :placeholder="
                      $t('aiAgentSignatureBuilder.choiceOptionPlaceholder')
                    "
                    @input="emitChange"
                  />
                  <ButtonIcon
                    tag="a"
                    icon="iconoir-cancel"
                    @click.stop.prevent="
                      removeOption(index, optionIndex, 'output')
                    "
                  ></ButtonIcon>
                </div>
              </div>
              <ButtonText
                icon="iconoir-plus"
                tag="a"
                size="small"
                @click="addOption(index, 'output')"
              >
                {{ $t('aiAgentSignatureBuilder.addOption') }}
              </ButtonText>
            </FormGroup>
          </template>
          <template #footer>
            <ButtonText
              icon="iconoir-bin"
              @click="removeField(index, 'output')"
            >
              {{ $t('action.delete') }}
            </ButtonText>
          </template>
        </SidebarExpandable>
      </div>
      <div v-else class="margin-bottom-2">
        <p class="color-neutral">
          {{ $t('aiAgentSignatureBuilder.noOutputsYet') }}
        </p>
      </div>
      <ButtonText
        type="primary"
        icon="iconoir-plus"
        size="small"
        @click="addOutput"
      >
        {{ $t('aiAgentSignatureBuilder.addOutput') }}
      </ButtonText>
    </FormSection>
  </div>
</template>

<script>
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'AiAgentSignatureBuilder',
  components: {
    SidebarExpandable,
    InjectedFormulaInput,
  },
  props: {
    value: {
      type: Object,
      required: false,
      default: () => ({ inputs: [], outputs: [] }),
    },
  },
  data() {
    return {
      inputs: [],
      outputs: [],
      emitTimeout: null,
    }
  },
  computed: {
    hasValidSignature() {
      // Check if we have at least one valid input and one valid output
      const validInputs = this.inputs.filter((f) =>
        this.isFieldValid(f, 'input')
      )
      const validOutputs = this.outputs.filter((f) =>
        this.isFieldValid(f, 'output')
      )
      return validInputs.length > 0 && validOutputs.length > 0
    },
  },
  watch: {
    value: {
      immediate: true,
      deep: true,
      handler(newValue) {
        if (newValue) {
          this.inputs = newValue.inputs || []
          this.outputs = newValue.outputs || []
        }
      },
    },
  },
  mounted() {
    // Initialize with default "question -> answer" signature if empty
    if (this.inputs.length === 0 && this.outputs.length === 0) {
      this.inputs = [
        {
          name: 'question',
          type: 'string',
          description: '',
          options: [],
          value: '',
          uid: uuid(),
        },
      ]
      this.outputs = [
        {
          name: 'answer',
          type: 'string',
          description: '',
          options: [],
          uid: uuid(),
        },
      ]
      this.emitChange()
    }
  },
  methods: {
    addInput() {
      this.inputs.push({
        name: '',
        type: 'string',
        description: '',
        options: [],
        value: '',
        uid: uuid(),
      })
      this.emitChange()
    },
    addOutput() {
      this.outputs.push({
        name: '',
        type: 'string',
        description: '',
        options: [],
        uid: uuid(),
      })
      this.emitChange()
    },
    removeField(index, category) {
      if (category === 'input') {
        this.inputs.splice(index, 1)
      } else {
        this.outputs.splice(index, 1)
      }
      this.emitChange()
    },
    addOption(fieldIndex, category) {
      const field =
        category === 'input'
          ? this.inputs[fieldIndex]
          : this.outputs[fieldIndex]
      if (!field.options) {
        field.options = []
      }
      field.options.push('')
      this.emitChange()
    },
    removeOption(fieldIndex, optionIndex, category) {
      const field =
        category === 'input'
          ? this.inputs[fieldIndex]
          : this.outputs[fieldIndex]
      field.options.splice(optionIndex, 1)
      this.emitChange()
    },
    handleTypeChange(index, category) {
      const field =
        category === 'input' ? this.inputs[index] : this.outputs[index]
      if (field.type === 'choice' && !field.options) {
        field.options = []
      }
      this.emitChange()
    },
    orderInputs(newOrder) {
      const fieldByUid = Object.fromEntries(
        this.inputs.map((field) => [field.uid, field])
      )
      this.inputs = newOrder.map((fieldUid) => fieldByUid[fieldUid])
      this.emitChange()
    },
    orderOutputs(newOrder) {
      const fieldByUid = Object.fromEntries(
        this.outputs.map((field) => [field.uid, field])
      )
      this.outputs = newOrder.map((fieldUid) => fieldByUid[fieldUid])
      this.emitChange()
    },
    getFieldErrorMessage(field, category) {
      if (!field.name) {
        return this.$t('aiAgentSignatureBuilder.errorFieldNameRequired')
      }
      // Validate field name format (must be valid identifier)
      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(field.name)) {
        return this.$t('aiAgentSignatureBuilder.errorInvalidFieldName')
      }
      if (!field.type) {
        return this.$t('aiAgentSignatureBuilder.errorFieldTypeRequired')
      }
      if (
        field.type === 'choice' &&
        (!field.options || field.options.length === 0)
      ) {
        return this.$t('aiAgentSignatureBuilder.errorChoiceOptionsRequired')
      }
      // For input fields, value is required
      if (category === 'input' && (!field.value || field.value === '')) {
        return this.$t('aiAgentSignatureBuilder.errorValueRequired')
      }
      // Check for duplicate names
      const fields = category === 'input' ? this.inputs : this.outputs
      const duplicates = fields.filter((f) => f.name === field.name)
      if (duplicates.length > 1) {
        return this.$t('aiAgentSignatureBuilder.errorDuplicateFieldName')
      }
      return null
    },
    getFieldNameError(index, category) {
      const field =
        category === 'input' ? this.inputs[index] : this.outputs[index]
      if (!field.name) {
        return this.$t('aiAgentSignatureBuilder.errorFieldNameRequired')
      }
      // Validate field name (must be valid identifier)
      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(field.name)) {
        return this.$t('aiAgentSignatureBuilder.errorInvalidFieldName')
      }
      return null
    },
    getFieldValueError(index) {
      const field = this.inputs[index]
      if (!field.value || field.value === '') {
        return this.$t('aiAgentSignatureBuilder.errorValueRequired')
      }
      return null
    },
    emitChange($event) {
      console.log('emitChange called with event:', $event)
      // Debounce emissions to prevent rapid-fire updates that can cause 400 errors
      // Wait for user to stop typing before emitting
      if (this.emitTimeout) {
        clearTimeout(this.emitTimeout)
      }
      this.emitTimeout = setTimeout(() => {
        const signature = this.buildSignatureString()
        const promptValues = this.buildPromptValues()

        // Always emit the raw inputs/outputs for internal state tracking
        this.$emit('input', {
          inputs: this.inputs,
          outputs: this.outputs,
        })

        // Always emit signature-data, even if invalid
        // This allows the backend to receive and validate the signature
        // and show appropriate error messages
        this.$emit('signature-data', {
          signature,
          promptValues,
        })

        this.emitTimeout = null
      }, 2000) // Wait 2 seconds after last change before emitting to ensure user is done typing
    },
    buildPromptValues() {
      const promptValues = []
      // Only include inputs that pass all validation checks

      this.inputs.forEach((input) => {
        if (this.isFieldValid(input, 'input')) {
          promptValues.push(`'"${input.name}": "', ${input.value}, '"'`)
        }
      })
      return promptValues.length > 0 ? `concat(${promptValues.join(',')})` : ''
    },
    isFieldValid(field, category) {
      // Check if field has no validation errors
      return this.getFieldErrorMessage(field, category) === null
    },
    buildSignatureString() {
      // Only include fields that pass all validation
      const inputParts = this.inputs
        .filter((f) => this.isFieldValid(f, 'input'))
        .map((f) => {
          const typeStr = this.getTypeString(f.type)
          return f.description
            ? `${f.name}: ${typeStr} = "${f.description}"`
            : `${f.name}: ${typeStr}`
        })
      const outputParts = this.outputs
        .filter((f) => this.isFieldValid(f, 'output'))
        .map((f) => {
          const typeStr = this.getTypeString(f.type)
          return f.description
            ? `${f.name}: ${typeStr} = "${f.description}"`
            : `${f.name}: ${typeStr}`
        })

      // Build signature even if incomplete to allow backend validation
      const inputStr = inputParts.length > 0 ? inputParts.join(', ') : ''
      const outputStr = outputParts.length > 0 ? outputParts.join(', ') : ''

      // Return empty string only if there are no fields at all
      if (!inputStr && !outputStr) {
        return ''
      }

      return `${inputStr} -> ${outputStr}`
    },
    getTypeString(type) {
      switch (type) {
        case 'string':
          return 'str'
        case 'number':
          return 'int'
        case 'boolean':
          return 'bool'
        case 'choice':
          return 'str'
        default:
          return 'str'
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.signature-choice-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.signature-choice-option {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
