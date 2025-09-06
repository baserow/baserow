<template>
  <div v-if="sources && sources.length > 0" class="assistant__sources-section">
    <button
      class="assistant__sources-toggle"
      :aria-expanded="expanded"
      @click="toggleSources"
    >
      <i class="iconoir-book-stack assistant__sources-icon"></i>
      <span class="assistant__sources-label">
        {{
          $tc('assistantMessageSources.sources', sources.length, {
            count: sources.length,
          })
        }}
      </span>
      <i
        class="iconoir-nav-arrow-down assistant__sources-chevron"
        :class="{
          'assistant__sources-chevron--expanded': expanded,
        }"
      ></i>
    </button>

    <!-- v-if ensures auto-scrolling works correctly if we're at the bottom -->
    <div
      v-if="expanded"
      class="assistant__sources-list"
      :class="{
        'assistant__sources-list--expanded': expanded,
      }"
    >
      <div
        v-for="(source, index) in sources"
        :key="index"
        class="assistant__source-item"
      >
        <a
          :href="source"
          target="_blank"
          rel="noopener noreferrer"
          class="assistant__source-link"
          @click.stop
        >
          <i class="iconoir-link assistant__source-link-icon"></i>
          <span class="assistant__source-url">{{
            formatSourceUrl(source)
          }}</span>
          <i
            class="iconoir-open-new-window assistant__source-external-icon"
          ></i>
        </a>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AssistantMessageSources',
  props: {
    sources: {
      type: Array,
      default: () => [],
    },
    expanded: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
    toggleSources() {
      this.$emit('toggle')
    },

    formatSourceUrl(url) {
      try {
        const urlObj = new URL(url)
        // Return a concise representation of the URL
        const pathname =
          urlObj.pathname.length > 30
            ? '...' + urlObj.pathname.slice(-27)
            : urlObj.pathname
        return urlObj.hostname + pathname
      } catch {
        // If URL parsing fails, return the original or truncate if too long
        return url.length > 50 ? url.slice(0, 47) + '...' : url
      }
    },
  },
}
</script>
