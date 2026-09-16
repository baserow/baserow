<template>
  <MarkdownIt
    v-if="isMarkdown"
    :content="text"
    :inline="markdownPreset.inline"
    :rules="markdownPreset.rules"
    :disabled-rules="markdownPreset.disabledRules"
    @click="onMarkdownClick"
  />
  <template v-else>{{ text }}</template>
</template>

<script>
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import {
  MARKDOWN_PRESETS,
  createApplicationBuilderMarkdownPreset,
  handleMarkdownClick,
} from '@baserow/modules/builder/utils/markdown'

/**
 * Renders a user-provided text either as-is or as Markdown, depending on its
 * `format`, using one of the Application Builder rendering presets.
 *
 * `builder` and `mode` are needed to resolve internal links; they're injected
 * from the surrounding element by default, and can be passed explicitly by
 * consumers living outside an element (e.g. the toasts).
 */
export default {
  name: 'FormattedText',
  inject: {
    injectedBuilder: { from: 'builder', default: null },
    injectedMode: { from: 'mode', default: null },
  },
  props: {
    content: {
      type: [String, Number],
      required: false,
      default: '',
    },
    format: {
      type: String,
      required: false,
      default: TEXT_FORMAT_TYPES.PLAIN,
    },
    preset: {
      type: String,
      required: false,
      default: MARKDOWN_PRESETS.BLOCK,
      validator: (value) => Object.values(MARKDOWN_PRESETS).includes(value),
    },
    builder: {
      type: Object,
      required: false,
      default: null,
    },
    mode: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    text() {
      return this.content === null || this.content === undefined
        ? ''
        : String(this.content)
    },
    isMarkdown() {
      return this.format === TEXT_FORMAT_TYPES.MARKDOWN
    },
    resolvedBuilder() {
      return this.builder || this.injectedBuilder
    },
    resolvedMode() {
      return this.mode || this.injectedMode
    },
    markdownPreset() {
      return createApplicationBuilderMarkdownPreset(this.preset, {
        builder: this.resolvedBuilder,
        mode: this.resolvedMode,
      })
    },
  },
  methods: {
    onMarkdownClick(event) {
      handleMarkdownClick(event, {
        mode: this.resolvedMode,
        router: this.$router,
      })
    },
  },
}
</script>
