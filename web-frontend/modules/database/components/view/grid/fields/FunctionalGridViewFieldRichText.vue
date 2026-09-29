<!-- eslint-disable vue/no-v-html -->
<template>
  <div
    class="field-rich-text--preview grid-view__cell grid-field-rich-text__cell"
  >
    <div
      class="grid-field-rich-text__cell-content grid-field-rich-text__cell-content--preview"
      v-html="renderFormattedValue()"
    ></div>
  </div>
</template>

<script>
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'
import {
  IMAGE_PLACEHOLDER,
  replaceImagesWithPlaceholder,
  trimUnfinishedImageRef,
} from '@baserow/modules/core/editor/richTextImageUtils'

const PREVIEW_LENGTH = 200
// Bounds the work on every scroll render, with room for long signed image URLs.
const RAW_PREVIEW_LENGTH = 5000

/**
 * The start of the value as the cell shows it, each image as its placeholder.
 *
 * @param {string} value The cell value, with resolved image URLs.
 * @return {string} Markdown of at most PREVIEW_LENGTH chars plus an ellipsis.
 */
function previewMarkdown(value) {
  const rawCut = value.length > RAW_PREVIEW_LENGTH
  const visible = replaceImagesWithPlaceholder(
    rawCut ? trimUnfinishedImageRef(value.slice(0, RAW_PREVIEW_LENGTH)) : value
  )
  if (!rawCut && visible.length <= PREVIEW_LENGTH) {
    return visible
  }
  const placeholderStart = visible.lastIndexOf(
    IMAGE_PLACEHOLDER,
    PREVIEW_LENGTH - 1
  )
  const end =
    placeholderStart >= 0 &&
    placeholderStart + IMAGE_PLACEHOLDER.length > PREVIEW_LENGTH
      ? placeholderStart
      : PREVIEW_LENGTH
  return `${visible.slice(0, end).trimEnd()}...`
}

export default {
  name: 'FunctionalGridViewFieldRichText',
  props: {
    value: {
      type: String,
      default: '',
    },
    workspaceId: {
      type: Number,
      required: true,
    },
  },
  methods: {
    renderFormattedValue() {
      const { value, workspaceId } = this
      const workspace = this.$store.getters['workspace/get'](workspaceId)
      const loggedUserId = this.$store.getters['auth/getUserId']

      return parseMarkdown(previewMarkdown(value || ''), {
        openLinkOnClick: false,
        enableImages: false,
        workspaceUsers: workspace ? workspace.users : null,
        loggedUserId,
      })
    },
  },
}
</script>
