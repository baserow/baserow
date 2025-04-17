<template>
  <Alert
    v-if="displayAlert"
    type="blank"
    close-button
    position="bottom"
    :width="396"
    @close="handleAlertClose"
  >
    <template #image
      ><img
        src="@baserow/modules/core/assets/images/dashboard_alert_image.png"
        srcset="
          @baserow/modules/core/assets/images/dashboard_alert_image@2x.png 2x
        "
      />
    </template>
    <template #title
      ><h4>{{ $t('dashboard.alertTitle') }}</h4></template
    >
    <p>{{ $t('dashboard.alertText') }}</p>
    <template #actions>
      <Button
        tag="a"
        href="https://gitlab.com/baserow/baserow"
        target="_blank"
        rel="noopener noreferrer"
        type="secondary"
        icon="baserow-icon-gitlab"
      >
        {{ $t('dashboard.starOnGitlab') }}</Button
      >
      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnTwitter')"
        tag="a"
        tooltip-position="top"
        :href="`https://twitter.com/intent/tweet?url=https://baserow.io&hashtags=opensource,nocode,database,baserow&text=${encodeURI(
          $t('dashboard.tweetContent')
        )}`"
        target="_blank"
        rel="noopener noreferrer"
        icon="baserow-icon-twitter"
      ></ButtonIcon>
      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnReddit')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-reddit"
        :href="
          'https://www.reddit.com/submit?url=https://baserow.io&title=' +
          encodeURI($t('dashboard.redditTitle'))
        "
        target="_blank"
        rel="noopener noreferrer"
      ></ButtonIcon>
      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnFacebook')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-facebook"
        href="https://www.facebook.com/sharer/sharer.php?u=https://baserow.io"
        target="_blank"
        rel="noopener noreferrer"
      ></ButtonIcon>
      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnLinkedIn')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-linkedin"
        href="https://www.linkedin.com/sharing/share-offsite/?url=https://baserow.io"
        target="_blank"
        rel="noopener noreferrer"
      ></ButtonIcon>
    </template>
  </Alert>
</template>

<script>
import { useCookies } from '@vueuse/integrations/useCookies'
const helpDisplayCookieName = 'baserow_dashboard_alert_closed'

export default {
  name: 'DashboardHelp',
  setup() {
    const cookies = useCookies(['helpDisplayCookieName'])
    return {
      cookies,
    }
  },
  data() {
    return {
      displayAlert: false,
    }
  },
  mounted() {
    this.displayAlert = !this.cookies.get(helpDisplayCookieName)
  },
  methods: {
    handleAlertClose() {
      this.displayAlert = false
      this.cookies.set(helpDisplayCookieName, true, {
        path: '/',
        maxAge: 60 * 60 * 24 * 182, // 6 months
      })
    },
  },
}
</script>
