<template>
  <div
    v-if="open"
    ref="modalWrapper"
    class="modal__wrapper file-field-modal__wrapper"
    @mousedown="outside($event)"
  >
    <div class="file-field-modal">
      <div class="file-field-modal__head">
        <div class="file-field-modal__name">
          <template v-if="preview">
            <Editable
              ref="rename"
              :value="preview.visible_name"
              @change="
                $emit('renamed', {
                  value: files,
                  index: selected,
                  value: $event.value,
                })
              "
              @editing="renaming = $event"
            ></Editable>
            <a
              v-if="!readOnly"
              v-show="!renaming"
              class="file-field-modal__rename"
              @click="$refs.rename.edit()"
            >
              <i class="iconoir-edit-pencil"></i>
            </a>
          </template>
        </div>
        <a class="file-field-modal__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>
      </div>
      <div class="file-field-modal__body">
        <a
          class="file-field-modal__body-nav file-field-modal__body-nav--previous"
          @click="previous()"
        >
          <i class="iconoir-nav-arrow-left"></i>
        </a>
        <a
          class="file-field-modal__body-nav file-field-modal__body-nav--next"
          @click="next()"
        >
          <i class="iconoir-nav-arrow-right"></i>
        </a>
        <div v-if="preview !== null" class="file-field-modal__preview">
          <PreviewAny
            ref="modalPreview"
            :mime-type="preview.mime_type"
            :url="preview.url"
          >
            <template #fallback>
              <div class="file-field-modal__preview-icon">
                <i :class="getIconClass(preview.mime_type)"></i>
              </div>
            </template>
          </PreviewAny>
        </div>
      </div>
      <div class="file-field-modal__foot">
        <ul class="file-field-modal__nav">
          <li
            v-for="(file, index) in files"
            :key="file.name + '-' + index"
            class="file-field-modal__nav-item"
          >
            <a
              class="file-field-modal__nav-link"
              :class="{ active: index === selected }"
              @click="selected = index"
            >
              <img
                v-if="file.is_image"
                :src="file.thumbnails.small.url"
                class="file-field-modal__nav-image"
              />
              <i
                v-else
                class="file-field-modal__nav-icon"
                :class="getIconClass(file.mime_type)"
              ></i>
            </a>
          </li>
        </ul>
        <ul v-if="preview" class="file-field-modal__actions">
          <DownloadLink
            class="file-field-modal__action"
            :url="preview.url"
            :filename="preview.visible_name"
            :loading-class="'file-field-modal__action--loading'"
          >
            <template #default="{ loading }">
              <i v-if="!loading" class="iconoir-download" />
            </template>
          </DownloadLink>
          <a
            v-if="!readOnly"
            class="file-field-modal__action"
            @click="remove(selected)"
          >
            <i class="iconoir-bin"></i>
          </a>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import baseModal from '@baserow/modules/core/mixins/baseModal'
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import PreviewAny from '@baserow/modules/database/components/preview/PreviewAny'
import {
  isElement,
  doesAncestorMatchPredicate,
} from '@baserow/modules/core/utils/dom'

export default {
  name: 'FileFieldModal',
  components: {
    PreviewAny,
  },
  mixins: [baseModal],
  props: {
    files: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['removed', 'renamed'],
  data() {
    return {
      renaming: false,
      selected: 0,
    }
  },
  computed: {
    preview() {
      if (this.files.length > this.selected) {
        return this.files[this.selected]
      }
      return null
    },
  },
  methods: {
    show(index = 0) {
      this.selected = index
      this.renaming = false
      return baseModal.methods.show.call(this)
    },
    getIconClass(mimeType) {
      return mimetype2icon(mimeType)
    },
    next() {
      this.selected =
        this.files.length - 1 > this.selected ? this.selected + 1 : 0
    },
    previous() {
      this.selected =
        this.selected === 0 ? this.files.length - 1 : this.selected - 1
    },
    remove(index) {
      if (index === this.files.length - 1) {
        this.selected = 0
      }

      const length = this.files.length
      this.$emit('removed', index)

      if (length === 1) {
        this.hide()
      }
    },
    keyup(event) {
      // When we are renaming we want the arrow keys to be available to move the
      // cursor.
      if (this.renaming) {
        return
      }

      // If left arrow
      if (event.key === 'ArrowLeft') {
        this.previous()
      }
      // If right arrow
      if (event.key === 'ArrowRight') {
        this.next()
      }
      return baseModal.methods.keyup.call(this, event)
    },
    outside(event) {
      const isChildOfAnchor = () =>
        doesAncestorMatchPredicate(
          event.target,
          (el) => el.tagName === 'A',
          this.$el
        )

      const protectedElements = [
        this.$refs.rename.$el,
        ...this.$refs.modalPreview.$el.children,
      ]
      const isProtectedElement = () =>
        protectedElements.some((element) => isElement(element, event.target))

      if (!this.renaming && !isProtectedElement() && !isChildOfAnchor()) {
        this.hide()
      }
    },
  },
}
</script>
