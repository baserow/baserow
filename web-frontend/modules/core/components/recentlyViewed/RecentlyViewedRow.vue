<template>
  <nuxt-link v-slot="{ href }" custom :to="item.route">
    <a
      :href="href"
      class="recently-viewed__row"
      :class="{ 'recently-viewed__row--with-workspace': showWorkspace }"
      @click="select($event)"
    >
      <div class="recently-viewed__cell">
        <ItemIcon
          :icon="item.iconClass"
          :color="item.iconColor"
          :loading="item.loading"
        ></ItemIcon>
        <div class="recently-viewed__name-details">
          <div class="recently-viewed__name">{{ item.name }}</div>
          <div class="recently-viewed__path">
            {{ item.typeName
            }}<template v-for="(parent, index) in item.parentPath" :key="index"
              ><span class="recently-viewed__path-separator">{{
                index === 0 ? '\u2022' : '\u203a'
              }}</span
              >{{ parent }}</template
            >
          </div>
        </div>
      </div>

      <div class="recently-viewed__cell recently-viewed__cell--muted">
        <span
          class="recently-viewed__cell-text recently-viewed__cell-text--capitalized"
          >{{ item.lastViewedLabel }}</span
        >
      </div>

      <div
        v-if="showWorkspace"
        class="recently-viewed__cell recently-viewed__cell--workspace"
      >
        <Avatar
          :initials="item.workspaceInitial"
          color="blue"
          size="medium"
        ></Avatar>
        <span class="recently-viewed__cell-text">{{ item.workspaceName }}</span>
      </div>
    </a>
  </nuxt-link>
</template>

<script setup>
import ItemIcon from '@baserow/modules/core/components/ItemIcon'

defineProps({
  // A presented entry, see `presentEntry` in `RecentlyViewed.vue`.
  item: {
    type: Object,
    required: true,
  },
  showWorkspace: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['click'])

/**
 * A plain click opens the item in place, so the owner can show it loading. A
 * modified or middle click is left to the browser, which opens the `href` in a
 * new tab or window.
 */
function select(event) {
  if (
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return
  }
  event.preventDefault()
  emit('click')
}
</script>
