<template>
  <Modal
    ref="modal"
    class="user-template-modal-wrapper user-template-modal-wrapper--small"
    :box-padding="false"
    :close-button="false"
    @hidden="emit('hidden')"
  >
    <div class="user-template-modal">
      <div class="user-template-modal__head">
        <h2 class="user-template-modal__title">
          {{ $t(copy.title, { name: template.name }) }}
        </h2>
        <button
          type="button"
          class="user-template-modal__head-action user-template-modal__close"
          :title="$t('action.close')"
          @click="hide()"
        >
          <i class="iconoir-cancel"></i>
        </button>
      </div>

      <div class="user-template-modal__body">
        <i18n-t
          :keypath="copy.description"
          tag="p"
          class="user-template-modal__description margin-bottom-0"
        >
          <template #name>{{ template.name }}</template>
          <template #author>
            <strong>{{ authorName }}</strong>
          </template>
        </i18n-t>
      </div>

      <div class="user-template-modal__footer">
        <div class="user-template-modal__footer-actions">
          <Button type="secondary" @click="hide()">
            {{ $t('action.cancel') }}
          </Button>
          <Button :loading="loading" :disabled="loading" @click="confirm">
            {{ $t(copy.button) }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { notifyTemplateUpdated } from '@baserow/modules/core/utils/userTemplate'

/**
 * Asks the author to agree that their template and their name are listed for
 * everyone on this instance, then makes the template public. The button is the
 * agreement, which the server requires.
 */
const props = defineProps({
  // The user's template as listed in their templates.
  template: {
    type: Object,
    required: true,
  },
})

// `made-public` is emitted with the template as listed in the user's templates,
// also when the modal was closed or opened for another template while the request
// ran. `outdated` is emitted with the id of a template that was updated since it
// was shown, which stays private.
const emit = defineEmits(['made-public', 'outdated', 'hidden'])

const { $client, $store, $i18n } = useNuxtApp()

const modal = ref(null)
// The ids of the templates whose request runs.
const pending = reactive(new Set())

const loading = computed(() => pending.has(props.template.id))

// A template goes to review when approval is on or an admin rejected it, see
// `needs_review`.
const copy = computed(() =>
  props.template.needs_review
    ? {
        title: 'makeTemplatePublicModal.resubmitTitle',
        description: props.template.listed
          ? 'makeTemplatePublicModal.resubmitListedDescription'
          : 'makeTemplatePublicModal.resubmitDescription',
        button: 'makeTemplatePublicModal.submitForReview',
      }
    : {
        title: 'makeTemplatePublicModal.title',
        description: 'makeTemplatePublicModal.description',
        button: 'makeTemplatePublicModal.makePublic',
      }
)

// The author of the user's own templates is the user.
const authorName = computed(() => $store.getters['auth/getName'])

function show(...args) {
  modal.value.show(...args)
}

function hide(...args) {
  modal.value.hide(...args)
}

async function confirm() {
  const { id, slug, revision_id: revisionId } = props.template
  if (pending.has(id)) {
    return
  }
  pending.add(id)
  try {
    const { data } = await TemplateService($client).setListed(
      slug,
      true,
      revisionId
    )
    emit('made-public', data)
    // A template sent to review isn't listed yet.
    if (data.state === 'public') {
      $store.dispatch('toast/success', {
        title: $i18n.t('makeTemplatePublicModal.madePublicTitle', {
          name: data.name,
        }),
        message: $i18n.t('makeTemplatePublicModal.madePublicDescription'),
      })
    }
    if (props.template.id === id) {
      hide()
    }
  } catch (error) {
    // The author agreed to list what they were shown, so they check the update
    // first.
    if (error.handler?.code === 'ERROR_TEMPLATE_UPDATED') {
      notifyTemplateUpdated(error, $i18n.t)
      emit('outdated', id)
      if (props.template.id === id) {
        hide()
      }
    } else {
      notifyIf(error, 'templates')
    }
  } finally {
    pending.delete(id)
  }
}

defineExpose({ show, hide })
</script>
