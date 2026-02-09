<template>
  <a class="template__card" @click="$emit('click', $event)">
    <TemplateIllustration
      v-if="!viewMore"
      :color="template.color"
      :type="template.type"
    />

    <div v-else class="template__card-more">
      <img
        class="template__card-more-icon"
        src="@baserow/modules/core/assets/images/template_more_icon.svg?data"
        :alt="$t('templateCard.viewMore')"
      />
    </div>

    <h4 class="template__card-name">
      <span v-if="!viewMore">{{ template.name }} </span>
      <span v-else> {{ $t('templateCard.viewMore') }} </span>
    </h4>
  </a>
</template>

<script>
import TemplateIllustration from '@baserow/modules/core/components/template/TemplateIllustration'

export default {
  components: {
    TemplateIllustration,
  },
  props: {
    template: {
      type: Object,
      default: () => ({}),
    },
    viewMore: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['click'],
}
</script>
