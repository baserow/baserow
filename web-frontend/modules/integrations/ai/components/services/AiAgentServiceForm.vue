<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('aiAgentForm.integrationDropdownLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-if="application"
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
      />
    </FormGroup>

    <AiAgentSignatureBuilder
      v-model="signatureFields"
      @signature-data="handleSignatureData"
    />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import AiAgentSignatureBuilder from '@baserow/modules/integrations/ai/components/services/AiAgentSignatureBuilder'
import { LMIntegrationType } from '@baserow/modules/integrations/ai/integrationTypes'
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'AiAgentServiceForm',
  components: {
    IntegrationDropdown,
    AiAgentSignatureBuilder,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: false,
      default: null,
    },
    service: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['integration_id', 'signature', 'prompt'],
      values: {
        integration_id: null,
        signature: '',
        prompt: '',
      },
      signatureFields: {
        inputs: [],
        outputs: [],
      },
      promptValues: {},
    }
  },
  computed: {
    integrations() {
      if (!this.application) {
        return []
      }
      const allIntegrations = this.$store.getters[
        'integration/getIntegrations'
      ](this.application)
      return allIntegrations.filter(
        (integration) => integration.type === this.integrationType.getType()
      )
    },
    integrationType() {
      return this.$registry.get('integration', LMIntegrationType.getType())
    },
  },
  mounted() {
    // Parse existing signature and prompt when editing
    if (this.service) {
      this.parseExistingSignature()
      this.parseExistingPrompt()
    }
  },
  methods: {
    handleSignatureData(data) {
      // Handle single combined event with both signature and prompt values
      // Use Object.assign to update both values atomically in a single Vue reactivity cycle
      // This prevents the form's auto-save watcher from firing with an inconsistent state
      console.log('Received signature data:', data)

      // Always update both signature and prompt, even if they're empty or invalid
      // This ensures the backend receives the latest state and can validate properly
      // Use Vue.set to ensure reactivity triggers properly
      this.$set(this.values, 'signature', data.signature || '')
      this.$set(this.values, 'prompt', data.promptValues || '')
      this.promptValues = data.promptValues
    },
    parseSignatureField(fieldStr) {
      // Parse a single field like "name: type = 'desc'" or "name: type" or "name"
      const trimmed = fieldStr.trim()

      // Extract description if present (between quotes)
      let description = ''
      let fieldWithoutDesc = trimmed
      const descMatch = trimmed.match(/=\s*["'](.+?)["']\s*$/)
      if (descMatch) {
        description = descMatch[1]
        fieldWithoutDesc = trimmed.substring(0, descMatch.index).trim()
      }

      // Extract name and type
      let name = ''
      let type = 'string' // Default type

      if (fieldWithoutDesc.includes(':')) {
        const parts = fieldWithoutDesc.split(':')
        name = parts[0].trim()
        const typeStr = parts[1].trim()

        // Map DSPy types to UI types
        if (typeStr === 'str') {
          type = 'string'
        } else if (typeStr === 'int') {
          type = 'number'
        } else if (typeStr === 'bool') {
          type = 'boolean'
        } else {
          type = 'string' // Default to string for unknown types
        }
      } else {
        // No type specified, use field name and default to string
        name = fieldWithoutDesc
      }

      return { name, type, description }
    },
    parseExistingSignature() {
      if (!this.values.signature) return

      try {
        const signature = this.values.signature.trim()

        // Split by -> to separate inputs from outputs
        const parts = signature.split('->')
        const inputStr = parts[0] ? parts[0].trim() : ''
        const outputStr = parts[1] ? parts[1].trim() : ''

        const inputs = []
        const outputs = []

        // Parse inputs
        if (inputStr) {
          const inputFields = inputStr.split(',')
          inputFields.forEach((fieldStr) => {
            const field = this.parseSignatureField(fieldStr)
            if (field.name) {
              inputs.push({
                uid: uuid(),
                name: field.name,
                type: field.type,
                description: field.description,
                value: '', // Will be populated from prompt
                options: [], // For choice fields
              })
            }
          })
        }

        // Parse outputs
        if (outputStr) {
          const outputFields = outputStr.split(',')
          outputFields.forEach((fieldStr) => {
            const field = this.parseSignatureField(fieldStr)
            if (field.name) {
              outputs.push({
                uid: uuid(),
                name: field.name,
                type: field.type,
                description: field.description,
                options: [], // For choice fields
              })
            }
          })
        }

        this.signatureFields = { inputs, outputs }
      } catch (e) {
        console.error('Error parsing signature:', e)
      }
    },
    parseExistingPrompt() {
      if (!this.values.prompt) return

      try {
        // Parse concat format: concat('"field1": "', value1, '"', '"field2": "', value2, '"')
        const prompt = this.values.prompt.trim()

        if (!prompt.startsWith('concat(') || !prompt.endsWith(')')) {
          console.log('Prompt is not in concat format:', prompt)
          return
        }

        // Extract the content inside concat(...)
        const content = prompt.substring(7, prompt.length - 1)

        // Split by comma, but we need to be careful about nested formulas
        // Use regex to extract field names and values
        const fieldPattern = /"([^"]+)":\s*"',\s*([^,]+),\s*'"/g
        let match

        while ((match = fieldPattern.exec(content)) !== null) {
          const fieldName = match[1]
          const fieldValue = match[2].trim()

          // Find the corresponding input field and set its value
          const inputField = this.signatureFields.inputs.find(
            (input) => input.name === fieldName
          )
          if (inputField) {
            inputField.value = fieldValue
          }
        }
      } catch (e) {
        console.error('Error parsing prompt:', e)
      }
    },
  },
}
</script>
