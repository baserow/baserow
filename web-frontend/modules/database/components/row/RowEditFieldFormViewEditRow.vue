<template>
  <div class="control__elements">
    <template v-if="value">
      <Button
        v-if="value"
        tag="a"
        size="tiny"
        type="secondary"
        :href="value"
        target="_blank"
        rel="nofollow noopener noreferrer"
      >
        {{ $t('editRowLink.editRow') }}
      </Button>
      <a
        class="margin-left-1 position-relative"
        @click.prevent=";[copyToClipboard(value), $refs.copied.show()]"
      >
        {{ $t('action.copy') }}
        <Copied ref="copied"></Copied>
      </a>
    </template>
    <Button v-else size="tiny" type="secondary" disabled>
      {{ $t('editRowLink.editRow') }}
    </Button>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'RowEditFieldFormViewEditRowLink',
  mixins: [rowEditField],
  methods: {
    copyToClipboard(value) {
      copyToClipboard(value)
    },
  },
}
</script>
