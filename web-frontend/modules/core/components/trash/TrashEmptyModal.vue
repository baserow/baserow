<template>
  <ModalV2 size="small" :close-button="false">
    <template #header-content>
      <h3>
        <template v-if="selectedIsTrashed">{{
          $t('trashEmptyModal.titleIsTrashed', { name })
        }}</template>
        <template v-else>{{
          $t('trashEmptyModal.titleIsNotTrashed', { name })
        }}</template>
      </h3>
    </template>
    <template #content>
      <p>
        <template v-if="selectedIsTrashed">{{
          $t('trashEmptyModal.messageIsTrashed')
        }}</template>
        <template v-else>{{
          $t('trashEmptyModal.messageIsNotTrashed')
        }}</template>
      </p>
    </template>

    <template #footer-content>
      <Button type="secondary" @click.prevent="hide()">{{
        $t('action.cancel')
      }}</Button>
      <Button type="danger" @click.prevent="emitEmptyAndClose">
        <template v-if="selectedIsTrashed">{{
          $t('trashEmptyModal.buttonIsTrashed')
        }}</template>
        <template v-else>{{
          $t('trashEmptyModal.buttonIsNotTrashed')
        }}</template></Button
      >
    </template>
  </ModalV2>
</template>

<script>
/**
 * A simple confirmation modal to check that the user is sure they want to permanently
 * delete / empty.
 */
import modalv2 from '@baserow/modules/core/mixins/modalv2'

export default {
  name: 'TrashEmptyModal',
  components: {},
  mixins: [modalv2],
  props: {
    name: {
      type: String,
      required: true,
    },
    selectedIsTrashed: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    emitEmptyAndClose() {
      this.$emit('empty')
      this.hide()
    },
  },
}
</script>
