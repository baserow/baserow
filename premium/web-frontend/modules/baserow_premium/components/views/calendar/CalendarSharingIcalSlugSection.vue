<template>
  <!-- extra section for shared view with ical/ics url -->
  <div v-if="view.ical_public" class="view-sharing__shared-link">
    <div class="view-sharing__shared-link-title">
      {{ $t('calendarViewType.sharedViewTitle', { viewTypeSharingLinkName }) }}
    </div>
    <div class="view-sharing__shared-link-description">
      {{
        $t('calendarViewType.sharedViewDescription', {
          viewTypeSharingLinkName,
        })
      }}
    </div>

    <div class="view-sharing__shared-link-content">
      <span v-if="!view.ical_feed_url" class="view-sharing__loading-icon" />
      <div :class="shareUrlCss">
        {{ shareUrl }}
      </div>
      <a
        v-tooltip="$t('shareViewLink.copyURL')"
        class="view-sharing__shared-link-action"
        @click="copyShareUrlToClipboard()"
      >
        <i class="iconoir-copy"></i>
        <Copied ref="copied"></Copied>
      </a>
      <a
        v-if="!readOnly"
        v-tooltip="$t('shareViewLink.generateNewUrl')"
        class="view-sharing__shared-link-action"
        @click.prevent="$refs.rotateSlugModal.show()"
      >
        <i class="iconoir-refresh-double"></i>
        <ViewRotateSlugModal
          ref="rotateSlugModal"
          :view="view"
          :service="viewService"
        />
      </a>
    </div>
  </div>
</template>
<script>
import Copied from '@baserow/modules/core/components/Copied'

import ViewRotateSlugModal from '@baserow/modules/database/components/view/ViewRotateSlugModal'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

import CalendarService from '@baserow_premium/services/views/calendar'

export default {
  name: 'CalendarSharingIcalSlugSection',
  components: { ViewRotateSlugModal, Copied },
  props: {
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      viewService: CalendarService(this.$client),
    }
  },
  computed: {
    shareUrl() {
      return this.view.ical_feed_url
    },
    shareUrlCss() {
      return {
        'view-sharing__shared-link-box': true,
        'view-sharing__shared-link-box--short': !this.view.ical_feed_url,
      }
    },
    viewType() {
      return this.$registry.get('view', this.view.type)
    },
    viewTypeSharingLinkName() {
      return this.viewType.getSharingLinkName()
    },
  },
  methods: {
    copyShareUrlToClipboard() {
      copyToClipboard(this.shareUrl)
      this.$refs.copied.show()
    },
  },
}
</script>
