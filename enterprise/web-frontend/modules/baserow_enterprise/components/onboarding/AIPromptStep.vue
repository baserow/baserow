<template>
  <div>
    <h1>{{ $t('aiPromptStep.title') }}</h1>

    <template v-if="hasVisibleError">
      <Error :error="error"></Error>
      <p>{{ $t('aiPromptStep.errorOtherOptions') }}</p>
    </template>
    <template v-else>
      <p>{{ $t('aiPromptStep.description') }}</p>

      <div v-if="loading" class="ai-prompt-loading">
        <div class="loading"></div>
        <div class="ai-prompt-loading__text">
          {{ $t('aiPromptStep.generating') }}
        </div>
      </div>
      <FormGroup
        v-else
        :label="$t('aiPromptStep.label')"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormTextarea
          ref="promptInput"
          v-model="prompt"
          :placeholder="$t('aiPromptStep.placeholder')"
          :rows="5"
          @input="promptEdited = true"
        />
      </FormGroup>

      <div class="ai-prompt-suggestions__head">
        <div class="ai-prompt-suggestions__title">
          {{ $t('aiPromptStep.suggestionsTitle') }}
        </div>
        <ButtonText
          icon="iconoir-edit-pencil"
          :disabled="loading"
          @click="editDetails()"
          >{{ $t('aiPromptStep.editDetails') }}</ButtonText
        >
      </div>

      <div class="ai-prompt-suggestions">
        <template v-if="loading">
          <div
            v-for="index in 4"
            :key="index"
            class="ai-prompt-suggestion ai-prompt-suggestion--skeleton"
          >
            <div class="ai-prompt-suggestion__preview">
              <div class="ai-prompt-suggestion__preview-text"></div>
            </div>
            <div class="ai-prompt-suggestion__name"></div>
          </div>
        </template>
        <button
          v-for="suggestion in suggestions"
          v-else
          :key="suggestion.name"
          type="button"
          class="ai-prompt-suggestion"
          :class="{
            'ai-prompt-suggestion--active': suggestion.prompt === prompt,
          }"
          @click="selectSuggestion(suggestion)"
        >
          <div class="ai-prompt-suggestion__preview">
            <div class="ai-prompt-suggestion__preview-text">
              {{ suggestion.prompt }}
            </div>
          </div>
          <div class="ai-prompt-suggestion__name">{{ suggestion.name }}</div>
        </button>
      </div>
    </template>

    <AIOnboardingDetailsModal
      ref="detailsModal"
      :industry="details.industry"
      :team="details.team"
      @updated="detailsUpdated"
    />
  </div>
</template>

<script>
import AIOnboardingDetailsModal from '@baserow_enterprise/components/onboarding/AIOnboardingDetailsModal'
import AssistantService from '@baserow_enterprise/services/assistant'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'

export default {
  name: 'AIPromptStep',
  components: { AIOnboardingDetailsModal },
  mixins: [error],
  props: {
    data: {
      type: Object,
      required: true,
    },
  },
  emits: ['update-data'],
  data() {
    return {
      loading: false,
      prompt: '',
      promptEdited: false,
      suggestions: [],
      details: this.answers(),
      lastAnswers: this.answers(),
    }
  },
  watch: {
    prompt() {
      this.emitData()
    },
    details() {
      this.emitData()
    },
  },
  mounted() {
    this.emitData()
    this.fetchSuggestions()
  },
  activated() {
    // The onboarding keeps this step alive, so the user can go back, change their
    // answers and end up here again with suggestions that no longer match.
    const answers = this.answers()
    if (
      answers.industry !== this.lastAnswers.industry ||
      answers.team !== this.lastAnswers.team
    ) {
      this.lastAnswers = answers
      this.details = answers
      this.fetchSuggestions()
    }
  },
  methods: {
    emitData() {
      this.$emit('update-data', {
        prompt: this.prompt,
        language: this.$i18n.locale,
        ...this.details,
      })
    },
    answers() {
      const database = this.data[DatabaseOnboardingType.getType()] || {}
      return {
        industry: database.industry || '',
        team: database.team || '',
      }
    },
    async fetchSuggestions() {
      const requested = this.details
      this.hideError()
      this.loading = true
      try {
        const suggestions = await AssistantService(
          this.$client
        ).fetchOnboardingPromptSuggestions({
          ...requested,
          language: this.$i18n.locale,
        })
        if (requested !== this.details) {
          return
        }
        this.suggestions = suggestions
        if (!this.promptEdited && suggestions.length > 0) {
          this.prompt = suggestions[0].prompt
        }
      } catch (requestError) {
        if (requested !== this.details) {
          return
        }
        // Without suggestions the assistant most likely can't build the database
        // either, so the error replaces the form instead of being a toast that's
        // easily missed.
        this.handleError(requestError, null, {
          ERROR_ASSISTANT_MODEL_NOT_SUPPORTED: new ResponseErrorMessage(
            this.$t('aiPromptStep.modelNotSupportedTitle'),
            this.$t('aiPromptStep.modelNotSupportedMessage')
          ),
        })
      }
      this.loading = false
    },
    selectSuggestion(suggestion) {
      this.prompt = suggestion.prompt
      this.promptEdited = false
    },
    editDetails() {
      this.$refs.detailsModal.show()
    },
    detailsUpdated(details) {
      this.details = details
      this.fetchSuggestions()
    },
    isValid() {
      return !this.hasVisibleError && this.prompt.trim() !== ''
    },
  },
}
</script>
