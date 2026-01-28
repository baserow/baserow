<template>
  <div class="upload-files__file-in-progress">
    <div class="field-file__preview">
      <a class="field-file__icon field-file__icon--static">
        <img v-if="file.is_image" :src="file.thumbnails.small.url" />
        <i v-else :class="iconClass"></i>
      </a>
    </div>
    <div class="field-file__description">
      <div class="field-file__name">
        <div class="upload-files__file-name">
          {{ file.visible_name }}
        </div>
        <div class="upload-files__percentage">{{ file.percentage }}%</div>
      </div>
      <div class="field-file__info">
        <div>
          <div class="upload-files__progress">
            <ProgressBar :value="file.percentage" :show-value="false" />
          </div>
        </div>
      </div>
    </div>
    <div class="upload-files__state">
      <a
        v-tooltip="$t('action.delete')"
        class="field-file__action"
        @click="$emit('delete')"
      >
        <i class="iconoir-bin"></i>
      </a>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileInProgress',
  props: {
    file: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    iconClass: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['delete'],
}
</script>
