<template>
  <Modal ref="modal" :tiny="true" :close-button="false">
    <h3>
      <template v-if="selectedIsTrashed">{{
        $t('trashEmptyModal.titleIsTrashed', { name })
      }}</template>
      <template v-else>{{
        $t('trashEmptyModal.titleIsNotTrashed', { name })
      }}</template>
    </h3>
    <p>
      <template v-if="selectedIsTrashed">{{
        $t('trashEmptyModal.messageIsTrashed')
      }}</template>
      <template v-else>{{
        $t('trashEmptyModal.messageIsNotTrashed')
      }}</template>
    </p>
    <div class="actions">
      <ul class="action__links">
        <li>
          <a @click.prevent="hide()">{{ $t('action.cancel') }}</a>
        </li>
      </ul>

      <Button type="danger" @click.prevent="emitEmptyAndClose">
        <template v-if="selectedIsTrashed">{{
          $t('trashEmptyModal.buttonIsTrashed')
        }}</template>
        <template v-else>{{
          $t('trashEmptyModal.buttonIsNotTrashed')
        }}</template></Button
      >
    </div>
  </Modal>
</template>

<script>
/**
 * A simple confirmation modal to check that the user is sure they want to permanently
 * delete / empty.
 */
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'TrashEmptyModal',
  components: {},
  mixins: [modal],
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
  emits: ['empty'],
  methods: {
    emitEmptyAndClose() {
      this.$emit('empty')
      this.hide()
    },
  },
}
</script>
