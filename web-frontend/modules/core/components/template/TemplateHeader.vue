<template>
  <div class="templates__header">
    <template v-if="template !== null">
      <div class="templates__icon">
        <i :class="template.icon"></i>
      </div>
      <div class="templates__header-title">
        {{ template.name }}
        <small v-if="category !== null">{{ category.name }}</small>
      </div>
      <div class="templates__install">
        <Button
          :loading="installing"
          :disabled="installing"
          @click="install(template)"
          >{{ $t('templateHeader.use') }}</Button
        >
      </div>
    </template>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import TemplateService from '@baserow/modules/core/services/template'

export default {
  name: 'TemplateHeader',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    template: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
    category: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  emits: ['installed'],
  data() {
    return {
      job: null,
      installing: false,
    }
  },
  watch: {
    'job.state'(newState) {
      if (['finished', 'failed'].includes(newState)) {
        this.installing = false
      }
    },
  },
  methods: {
    async install(template) {
      this.installing = true

      try {
        const { data: job } = await TemplateService(this.$client).asyncInstall(
          this.workspace.id,
          template.id
        )
        this.job = job
        this.$store.dispatch('job/create', job)
        this.$emit('installed')
      } catch (error) {
        notifyIf(error, 'template')
        this.installing = false
      }
    },
  },
}
</script>
