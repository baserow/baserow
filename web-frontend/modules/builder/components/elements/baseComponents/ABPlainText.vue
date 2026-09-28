<template>
  <template v-if="isInline">{{ value }}</template>
  <template v-else>
    <ABParagraph v-for="paragraph in paragraphs" :key="paragraph.id">
      {{ paragraph.content }}
    </ABParagraph>
  </template>
</template>

<script>
import formattedTextRenderer from '@baserow/modules/builder/mixins/formattedTextRenderer'
import { generateHash } from '@baserow/modules/core/utils/hashing'

/**
 * @typedef Paragraph
 * @property {string} content - The text of the paragraph
 * @property {string} id - A hash identifying the paragraph
 */

/**
 * The plain text renderer of `ABFormattedText`: the value as it is in the
 * inline profile, one paragraph per line in the block profile.
 */
export default {
  name: 'ABPlainText',
  mixins: [formattedTextRenderer],
  computed: {
    /**
     * The value split into paragraphs, for the block profile.
     * @returns {Array.<Paragraph>}
     */
    paragraphs() {
      return this.value
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line)
        .map((line, index) => ({
          content: line,
          id: generateHash(line + index),
        }))
    },
  },
}
</script>
