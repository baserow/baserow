<template>
  <div class="ai-assistant__recent-chats">
    <div class="ai-assistant__recent-chats-header">
      <h4>Recent chats</h4>
    </div>

    <div class="ai-assistant__recent-chats-list">
      <!-- Loading state -->
      <template v-if="chatsLoading">
        <div class="ai-assistant__recent-chat-item ai-assistant__recent-chat-loading">
          <i class="iconoir-system-restart ai-assistant__recent-chat-loading-icon"></i>
          <span>Loading chats...</span>
        </div>
        <!-- Placeholder items to maintain height -->
        <div v-for="i in 4" :key="`placeholder-${i}`" class="ai-assistant__recent-chat-item ai-assistant__recent-chat-placeholder"></div>
      </template>
      
      <!-- Chat items (up to 5) -->
      <template v-else>
        <div
          v-for="chat in displayedChats"
          :key="chat.uid"
          :class="['ai-assistant__recent-chat-item', { 
            'ai-assistant__recent-chat-item--deleting': deletingChats.includes(chat.uid)
          }]"
          @click="!deletingChats.includes(chat.uid) && $emit('select-chat', chat)"
        >
          <div class="ai-assistant__recent-chat-content">
            <div class="ai-assistant__recent-chat-title">
              {{ chat.title }}
            </div>
          </div>
          <button
            class="ai-assistant__recent-chat-delete"
            @click.stop="handleDeleteChat(chat)"
            :title="'Delete chat'"
            :disabled="deletingChats.includes(chat.uid)"
          >
            <i v-if="deletingChats.includes(chat.uid)" class="iconoir-system-restart ai-assistant__recent-chat-delete-loading"></i>
            <i v-else class="iconoir-trash"></i>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AiAssistantRecentChats',
  props: {
    chats: {
      type: Array,
      default: () => [],
    },
    chatsLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['select-chat', 'delete-chat'],
  data() {
    return {
      deletingChats: [], // Track which chats are being deleted
      localChats: [], // Local copy to manage animations
    }
  },
  computed: {
    displayedChats() {
      // Use local chats for display to control animations
      const maxChats = 5
      return this.localChats.slice(0, maxChats)
    },
  },
  watch: {
    chats: {
      handler(newChats) {
        // Update local chats when store chats change, but handle deletions specially
        if (newChats.length >= this.localChats.length) {
          // Adding chats or initial load
          this.localChats = [...newChats]
        } else {
          // A chat was deleted - find which one and mark for removal
          const deletedChats = this.localChats.filter(localChat => 
            !newChats.some(chat => chat.uid === localChat.uid)
          )
          
          // Only update if we're not already deleting these chats
          const newlyDeleted = deletedChats.filter(chat => 
            !this.deletingChats.includes(chat.uid)
          )
          
          if (newlyDeleted.length === 0) {
            // Safe to update local chats now
            this.localChats = [...newChats]
          }
        }
      },
      immediate: true,
    },
  },
  methods: {
    async handleDeleteChat(chat) {
      if (this.deletingChats.includes(chat.uid)) return
      
      // Add chat to deleting state for visual feedback
      this.deletingChats.push(chat.uid)
      
      try {
        // Emit the delete event and wait for it to complete
        await this.$emit('delete-chat', chat)
        
        // After deletion, wait for animation then remove from local state
        setTimeout(() => {
          // Remove from local chats to trigger the fade-out
          this.localChats = this.localChats.filter(localChat => localChat.uid !== chat.uid)
          
          // Clean up deleting state
          const index = this.deletingChats.indexOf(chat.uid)
          if (index > -1) {
            this.deletingChats.splice(index, 1)
          }
        }, 300) // Match CSS transition duration
      } catch (error) {
        // Remove from deleting state if deletion failed
        const index = this.deletingChats.indexOf(chat.uid)
        if (index > -1) {
          this.deletingChats.splice(index, 1)
        }
        throw error
      }
    },
  },
}
</script>
