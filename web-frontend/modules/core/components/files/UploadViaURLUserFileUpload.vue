<template>
  <div>
    <h2 class="box__title">{{ $t('uploadViaURLUserFileUpload.title') }}</h2>
    <Error :error="error"></Error>
    <form @submit.prevent="upload(values.url)">
      <FormGroup
        :label="$t('uploadViaURLUserFileUpload.urlLabel')"
        small-label
        required
        :error="v$.url.$error"
      >
        <FormInput
          v-model="v$.url.$model"
          size="large"
          :error="v$.url.$error"
          @blur="v$.url.$touch"
        >
        </FormInput>

        <template #error>
          {{ $t('uploadViaURLUserFileUpload.urlError') }}
        </template>
      </FormGroup>

      <div class="actions actions--right">
        <Button type="primary" size="large" :loading="loading">
          {{ $t('action.upload') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, url } from '@vuelidate/validators'

import error from '@baserow/modules/core/mixins/error'
import UserFileService from '@baserow/modules/core/services/userFile'

export default {
  name: 'UploadViaURLUserFileUpload',
  mixins: [error],
  data() {
    return {
      loading: false,
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      url: '',
    })

    const rules = computed(() => ({
      url: { required, url },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    async upload(url) {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const { data } = await UserFileService(this.$client).uploadViaURL(url)
        this.$emit('uploaded', [data])
      } catch (error) {
        this.handleError(error, 'userFile')
      }

      this.loading = false
    },
  },
}
</script>
