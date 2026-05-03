<template>
  <div class="whiteboard-comment-overlay">
    <WhiteboardCommentPin
      v-for="thread in threads"
      :key="thread.id"
      :thread="thread"
      :viewport="viewportFor(thread)"
      :open="openThreadId === thread.id"
      @open="onOpen(thread.id)"
    />
    <WhiteboardCommentPin
      v-if="draftPin"
      :thread="{ id: 'draft', resolved: false, replies: [] }"
      :viewport="viewportFor({ x: draftPin.x, y: draftPin.y })"
      :open="openThreadId === 'draft'"
      :draft="true"
      @open="onOpen('draft')"
    />
    <WhiteboardCommentThread
      v-if="openThread"
      :whiteboard="whiteboard"
      :workspace="workspace"
      :thread="openThread"
      :viewport="openThreadViewport"
      :wrapper-width="appState.width || 0"
      :wrapper-height="appState.height || 0"
      :read-only="readOnly"
      @close="onClose"
    />
    <WhiteboardCommentThread
      v-else-if="openThreadId === 'draft' && draftPin"
      :whiteboard="whiteboard"
      :workspace="workspace"
      :thread="null"
      :draft-pin="draftPin"
      :viewport="viewportFor({ x: draftPin.x, y: draftPin.y })"
      :wrapper-width="appState.width || 0"
      :wrapper-height="appState.height || 0"
      :read-only="readOnly"
      @close="onClose"
      @cancel-draft="$emit('cancel-draft')"
    />
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import WhiteboardCommentPin from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentPin.vue'
import WhiteboardCommentThread from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentThread.vue'

export default {
  name: 'WhiteboardCommentLayer',
  components: { WhiteboardCommentPin, WhiteboardCommentThread },
  props: {
    whiteboard: { type: Object, required: true },
    workspace: { type: Object, required: true },
    readOnly: { type: Boolean, default: false },
    appState: { type: Object, required: true },
    viewportConverter: { type: Function, required: true },
  },
  emits: ['cancel-draft'],
  computed: {
    ...mapGetters({
      threads: 'whiteboardComments/getThreads',
      draftPin: 'whiteboardComments/getDraftPin',
      openThreadId: 'whiteboardComments/getOpenThreadId',
    }),
    openThread() {
      if (!this.openThreadId || this.openThreadId === 'draft') return null
      return this.$store.getters['whiteboardComments/getThreadById'](
        this.openThreadId
      )
    },
    openThreadViewport() {
      if (!this.openThread) return { x: 0, y: 0 }
      return this.viewportFor(this.openThread)
    },
  },
  methods: {
    viewportFor(thread) {
      // Touch the reactive `appState` dependency so the method re-runs
      // whenever Excalidraw pans/zooms — the converter itself reads the
      // latest appState through the controller, but Vue needs the
      // dependency to be observed somewhere in the template.
      void this.appState
      return this.viewportConverter(thread.x ?? 0, thread.y ?? 0)
    },
    onOpen(id) {
      this.$store.dispatch('whiteboardComments/openThread', id)
    },
    onClose() {
      this.$store.dispatch('whiteboardComments/closeThread')
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-comment-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 50;
}
</style>
