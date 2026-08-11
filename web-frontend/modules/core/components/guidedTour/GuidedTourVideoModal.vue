<template>
  <Teleport to="body">
    <div
      v-if="open"
      ref="modalEl"
      v-bind="$attrs"
      class="modal__wrapper guided-tour-video-modal__wrapper"
      @click.stop="outside()"
    >
      <div class="guided-tour-video-modal">
        <a
          class="guided-tour-video-modal__close"
          :title="$t('guidedTourVideoModal.close')"
          @click="hide()"
        >
          <i class="iconoir-cancel"></i>
        </a>
        <div class="guided-tour-video-modal__body">
          <a
            v-if="hasMultiple"
            class="guided-tour-video-modal__nav guided-tour-video-modal__nav--previous"
            :class="{
              'guided-tour-video-modal__nav--disabled': selected === 0,
            }"
            :title="$t('guidedTourVideoModal.previous')"
            @click="previous()"
          >
            <i class="iconoir-nav-arrow-left"></i>
          </a>
          <div ref="playerEl" class="guided-tour-video-modal__player">
            <div ref="player"></div>
          </div>
          <a
            v-if="hasMultiple"
            class="guided-tour-video-modal__nav guided-tour-video-modal__nav--next"
            :class="{
              'guided-tour-video-modal__nav--disabled':
                selected === videos.length - 1,
            }"
            :title="$t('guidedTourVideoModal.next')"
            @click="next()"
          >
            <i class="iconoir-nav-arrow-right"></i>
          </a>
        </div>
        <div class="guided-tour-video-modal__foot">
          <ul v-if="hasMultiple" class="guided-tour-video-modal__thumbnails">
            <li v-for="(video, index) in videos" :key="video">
              <a
                class="guided-tour-video-modal__thumbnail"
                :class="{
                  'guided-tour-video-modal__thumbnail--active':
                    index === selected,
                }"
                @click="select(index)"
              >
                <img :src="getThumbnailUrl(video)" alt="" />
              </a>
            </li>
          </ul>
          <a
            class="guided-tour-video-modal__academy"
            :href="academyUrl"
            target="_blank"
            rel="noopener noreferrer"
            >{{ $t('academy.learnMore') }}</a
          >
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import baseModal from '@baserow/modules/core/mixins/baseModal'
import {
  isElement,
  doesAncestorMatchPredicate,
} from '@baserow/modules/core/utils/dom'
import { BASEROW_ACADEMY_URL } from '@baserow/modules/core/utils/academy'
import {
  createYouTubePlayer,
  getYouTubeThumbnailUrl,
} from '@baserow/modules/core/utils/youtube'

export default {
  name: 'GuidedTourVideoModal',
  mixins: [baseModal],
  inheritAttrs: false,
  props: {
    videos: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      selected: 0,
      player: null,
    }
  },
  computed: {
    academyUrl() {
      return BASEROW_ACADEMY_URL
    },
    hasMultiple() {
      return this.videos.length > 1
    },
  },
  beforeUnmount() {
    this.player?.destroy()
    this.player = null
  },
  methods: {
    getThumbnailUrl(videoId) {
      return getYouTubeThumbnailUrl(videoId)
    },
    async show(index = 0) {
      this.selected = index
      baseModal.methods.show.call(this)
      await this.$nextTick()

      try {
        this.player = await createYouTubePlayer(
          this.$refs.player,
          this.videos[this.selected],
          () => this.next()
        )
      } catch (error) {
        // Without internet access the API can't be loaded. There is nothing to play
        // then, so the modal closes again.
        this.hide()
      }
    },
    hide(emit = true) {
      // The player must be destroyed, otherwise the video keeps playing in the
      // background.
      this.player?.destroy()
      this.player = null
      baseModal.methods.hide.call(this, emit)
    },
    select(index) {
      this.selected = index
      // `loadVideoById` immediately starts playing the new video.
      this.player?.loadVideoById(this.videos[index])
    },
    // The videos are deliberately not wrapping around because the last one
    // automatically calls `next` when it finished, and that would loop forever.
    next() {
      if (this.selected < this.videos.length - 1) {
        this.select(this.selected + 1)
      }
    },
    previous() {
      if (this.selected > 0) {
        this.select(this.selected - 1)
      }
    },
    keyup(event) {
      if (event.key === 'ArrowLeft') {
        this.previous()
      }
      if (event.key === 'ArrowRight') {
        this.next()
      }
      return baseModal.methods.keyup.call(this, event)
    },
    outside() {
      // The `downElement` of the mixin is used instead of the click target because
      // hiding on `mousedown` would remove the modal while the browser is still
      // completing the gesture, making it select all the text of the page below.
      const target = this.downElement

      // Anything outside of the video closes the modal, except the anchors because
      // their own click event must still fire.
      const isChildOfAnchor = doesAncestorMatchPredicate(
        target,
        (element) => element.tagName === 'A',
        this.$refs.modalEl
      )

      if (
        this.canClose &&
        !isChildOfAnchor &&
        !isElement(this.$refs.playerEl, target)
      ) {
        this.hide()
      }
    },
  },
}
</script>
