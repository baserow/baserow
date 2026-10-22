<template>
  <Modal ref="modal" small @hidden="settle(false)">
    <h2 class="box__title">{{ $t('shareScope.noAccessTitle') }}</h2>
    <p>{{ description }}</p>
    <div class="actions margin-bottom-0">
      <ul class="action__links">
        <li>
          <a @click="hide()">{{ $t('action.cancel') }}</a>
        </li>
      </ul>
      <Button type="danger" @click="confirm">
        {{ $t('shareScope.noAccessConfirm') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

/**
 * Asks before giving members, teams or agents no access on an object, as that
 * takes the object away from them whatever role they have above it.
 */
export default {
  name: 'ScopeNoAccessModal',
  mixins: [modal],
  data() {
    return {
      description: '',
      resolve: null,
    }
  },
  methods: {
    /**
     * Shows the modal with the given description and resolves with whether
     * giving no access was confirmed.
     */
    ask(description) {
      this.settle(false)
      this.description = description
      this.show()
      return new Promise((resolve) => {
        this.resolve = resolve
      })
    },
    settle(confirmed) {
      const resolve = this.resolve
      this.resolve = null
      resolve?.(confirmed)
    },
    confirm() {
      this.settle(true)
      this.hide()
    },
  },
}
</script>
