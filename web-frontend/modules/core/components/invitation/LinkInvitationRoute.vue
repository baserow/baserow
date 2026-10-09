<template>
  <div>
    <h2 class="box__title">{{ $t('inviteModal.linkTitle') }}</h2>
    <div class="invitation-link-empty">
      <div class="invitation-link-empty__icon">
        <i class="iconoir-link"></i>
      </div>
      <h3 class="invitation-link-empty__title">
        {{ $t('inviteModal.linkEmptyTitle') }}
      </h3>
      <p class="invitation-link-empty__description">
        {{ $t('inviteModal.linkEmptyDescription') }}
      </p>
    </div>
  </div>
</template>

<script>
/**
 * Placeholder for inviting people with a permanent link. It only shows the empty
 * state for now and is registered behind the `RBAC_IMPROVEMENTS` feature flag
 * until the links exist.
 */
export default {
  name: 'LinkInvitationRoute',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
}
</script>
