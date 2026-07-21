<template>
  <div
    class="ai-provider-model-combobox"
    role="combobox"
    aria-autocomplete="list"
    aria-haspopup="listbox"
    :aria-expanded="contextOpen"
    :aria-controls="listId"
    :aria-busy="loading"
  >
    <FormInput
      ref="input"
      :model-value="currentValue"
      :error="error"
      :loading="loading"
      :placeholder="placeholder"
      autocomplete="off"
      @focus="onInputFocus"
      @input="updateValue"
      @keydown="onKeydown"
    />

    <Context
      ref="suggestions"
      class="ai-provider-model-combobox__suggestions select"
      @shown="contextOpen = true"
      @hidden="contextOpen = false"
    >
      <div v-if="loading" class="select__items-loading" />
      <ul
        v-else-if="filteredSuggestions.length"
        :id="listId"
        class="select__items"
        role="listbox"
      >
        <li
          v-for="(suggestion, index) in filteredSuggestions"
          :key="suggestion"
          class="select__item ai-provider-model-combobox__suggestion"
          :class="{ hover: index === highlightedIndex }"
          role="option"
          :aria-selected="suggestion === currentValue"
          @mousedown.prevent
          @click="selectSuggestion(suggestion)"
          @mousemove="highlightedIndex = index"
        >
          <a class="select__item-link">
            {{ suggestion }}
          </a>
        </li>
      </ul>
      <div v-else :id="listId" class="select__items--empty" role="listbox">
        {{ emptyMessage }}
      </div>
    </Context>
  </div>
</template>

<script>
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'AIProviderModelCombobox',
  props: {
    value: { type: String, default: undefined },
    modelValue: { type: String, default: undefined },
    suggestions: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    unavailable: { type: Boolean, default: false },
    error: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
  },
  emits: ['input', 'update:modelValue', 'focus'],
  data() {
    return {
      contextOpen: false,
      highlightedIndex: -1,
      listId: `ai-provider-model-suggestions-${uuid()}`,
    }
  },
  computed: {
    currentValue() {
      return this.modelValue !== undefined
        ? this.modelValue || ''
        : this.value || ''
    },
    trimmedValue() {
      return this.currentValue.trim()
    },
    filteredSuggestions() {
      const query = this.trimmedValue.toLowerCase()
      if (!query) {
        return this.suggestions
      }
      return this.suggestions.filter((suggestion) =>
        suggestion.toLowerCase().includes(query)
      )
    },
    emptyMessage() {
      if (this.unavailable) {
        return this.$t('aiProviderAdmin.modelDiscoveryUnavailable')
      }
      if (this.suggestions.length === 0) {
        return this.$t('aiProviderAdmin.modelDiscoveryEmpty')
      }
      return this.$t('aiProviderAdmin.modelDiscoveryNoMatch')
    },
  },
  watch: {
    currentValue() {
      this.highlightedIndex = -1
    },
    suggestions() {
      this.highlightedIndex = -1
    },
  },
  methods: {
    onInputFocus(event) {
      this.showSuggestions(event)
      this.$emit('focus')
    },
    updateValue(value) {
      this.$emit('input', value)
      this.$emit('update:modelValue', value)
      if (!this.contextOpen) {
        this.$nextTick(() => this.showSuggestions())
      }
    },
    showSuggestions(event) {
      if (this.contextOpen) {
        return
      }
      const anchor = event?.currentTarget || this.$refs.input?.$el
      if (anchor) {
        this.$refs.suggestions.show(anchor, 'bottom', 'left', 0, 0)
      }
      this.highlightedIndex =
        this.trimmedValue === '' && this.filteredSuggestions.length ? 0 : -1
    },
    hideSuggestions() {
      this.$refs.suggestions?.hide()
    },
    selectSuggestion(suggestion) {
      this.$emit('input', suggestion)
      this.$emit('update:modelValue', suggestion)
      this.hideSuggestions()
    },
    onKeydown(event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        if (!this.contextOpen) {
          this.showSuggestions(event)
          return
        }
        const count = this.filteredSuggestions.length
        if (!count) {
          return
        }
        const offset = event.key === 'ArrowDown' ? 1 : -1
        this.highlightedIndex = (this.highlightedIndex + offset + count) % count
      } else if (event.key === 'Enter' && this.contextOpen) {
        event.preventDefault()
        if (this.highlightedIndex >= 0) {
          this.selectSuggestion(this.filteredSuggestions[this.highlightedIndex])
        } else {
          this.hideSuggestions()
        }
      } else if (event.key === 'Escape' || event.key === 'Tab') {
        this.hideSuggestions()
      }
    },
  },
}
</script>
