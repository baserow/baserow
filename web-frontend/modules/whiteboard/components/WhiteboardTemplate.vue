<template>
  <client-only>
    <div ref="container" class="whiteboard-template" />
  </client-only>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'WhiteboardTemplate',
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      controller: null,
    }
  },
  computed: {
    excalidrawLangCode() {
      // Mirror Excalidraw's locale to the user's Baserow language so
      // the template preview reads in the same language as the rest
      // of the app.
      const map = {
        en: 'en',
        de: 'de-DE',
        es: 'es-ES',
        fr: 'fr-FR',
        it: 'it-IT',
        ko: 'ko-KR',
        nl: 'nl-NL',
        pl: 'pl-PL',
        uk: 'uk-UA',
      }
      const userLanguage = this.$store.getters['auth/getLanguage']
      return map[userLanguage] || 'en'
    },
  },
  watch: {
    pageValue: {
      handler(pageValue) {
        this.loadWhiteboard(pageValue.whiteboard)
      },
    },
    excalidrawLangCode(newCode) {
      if (this.controller) {
        this.controller.setLangCode(newCode)
      }
    },
  },
  async mounted() {
    if (!import.meta.client) return
    await this.loadWhiteboard(this.pageValue.whiteboard)
  },
  beforeUnmount() {
    if (this.controller) {
      this.controller.unmount()
      this.controller = null
    }
  },
  methods: {
    async loadWhiteboard(whiteboard) {
      try {
        await this.$store.dispatch(
          'template/whiteboardApplication/fetchInitial',
          { whiteboardId: whiteboard.id }
        )
        const content =
          this.$store.getters['template/whiteboardApplication/getContent']
        await this.renderReadOnly(content)
      } catch (error) {
        notifyIf(error, 'whiteboard')
      }
    },
    async renderReadOnly(content) {
      // Tear down any previous instance — `pageValue` can change while
      // the user navigates between applications in the templates modal.
      if (this.controller) {
        this.controller.unmount()
        this.controller = null
      }
      const { mountExcalidraw } = await import('./excalidrawReactRoot.js')
      this.controller = mountExcalidraw(this.$refs.container, {
        initialData: {
          elements: content?.elements || [],
          appState: {
            ...(content?.appState || {}),
            collaborators: new Map(),
          },
          files: content?.files || {},
        },
        // Excalidraw's built-in read-only mode. Hides the editing
        // toolbar and the shape-properties panel, disables every
        // mutating action, and lets the user pan/zoom the scene to
        // explore it. Templates are static previews so nothing in
        // here is wired to autosave or broadcast either.
        viewModeEnabled: true,
        langCode: this.excalidrawLangCode,
        onChange: () => {},
        onPointerUpdate: () => {},
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-template {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
}
</style>
