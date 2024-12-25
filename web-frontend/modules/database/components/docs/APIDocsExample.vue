<template>
  <div>
    <div
      v-if="type !== '' && url !== ''"
      class="api-docs__example api-docs__example--with-padding"
    >
      <a
        class="api-docs__copy"
        @click.prevent=";[copyToClipboard(url), $refs.urlCopied.show()]"
      >
        {{ $t('action.copy') }}
        <Copied ref="urlCopied"></Copied>
      </a>
      <div class="api-docs__example-request">
        <div
          class="api-docs__example-request-type"
          :class="{
            'api-docs__example-request-type--success':
              type.toLowerCase() === 'get',
            'api-docs__example-request-type--primary':
              type.toLowerCase() === 'post',
            'api-docs__example-request-type--warning':
              type.toLowerCase() === 'patch',
            'api-docs__example-request-type--error':
              type.toLowerCase() === 'delete',
          }"
        >
          {{ type | uppercase }}
        </div>
        <div class="api-docs__example-request-url">
          {{ url }}
        </div>
      </div>
    </div>
    <div class="api-docs__example-title">
      {{ $t('apiDocsExample.requestSample') }}
    </div>
    <div class="api-docs__example">
      <a
        class="api-docs__copy"
        @click.prevent="
          ;[
            copyToClipboard(getFormattedRequest().example),
            $refs.requestCopied.show(),
          ]
        "
      >
        {{ $t('action.copy') }}
        <Copied ref="requestCopied"></Copied>
      </a>
      <div class="api-docs__example-type">
        <Dropdown
          class="dropdown--floating"
          :value="value.type"
          @input="
            $emit('input', {
              userFieldNames: value.userFieldNames,
              type: $event,
            })
          "
        >
          <DropdownItem value="curl" name="cURL"></DropdownItem>
          <DropdownItem value="http" name="HTTP"></DropdownItem>
          <DropdownItem
            value="javascript"
            name="JavaScript (axios)"
          ></DropdownItem>
          <DropdownItem value="python" name="Python (requests)"></DropdownItem>
        </Dropdown>
        <Checkbox
          v-if="includeUserFieldsCheckbox"
          :checked="value.userFieldNames"
          class="api-docs__example-type-item"
          @input="$emit('input', { userFieldNames: $event, type: value.type })"
          >{{ $t('apiDocsExample.userFieldNames') }}</Checkbox
        >
      </div>
      <div class="api-docs__example-content-container">
        <div
          v-if="Object.keys(mapping).length > 0"
          class="api-docs__example-content-side"
        >
          <div
            v-for="(lineValue, line) in formattedRequest.lines"
            :key="'response-info-line-' + line"
            class="api-docs__example-content-line"
            :style="'top:' + (line - 1) * 21 + 'px;'"
            :title="lineValue"
          >
            {{ lineValue }}
          </div>
        </div>
        <div class="api-docs__example-content-wrapper">
          <div class="api-docs__example-content">
            <pre
              class="api-docs__example-content"
            ><code>{{ formattedRequest.example }}</code></pre>
          </div>
        </div>
      </div>
    </div>
    <template v-if="response !== false">
      <div class="api-docs__example-title">
        {{ $t('apiDocsExample.responseSample') }}
      </div>
      <div class="api-docs__example">
        <a
          class="api-docs__copy"
          @click.prevent="
            ;[
              copyToClipboard(getFormattedResponse().example),
              $refs.responseCopied.show(),
            ]
          "
        >
          {{ $t('action.copy') }}
          <Copied ref="responseCopied"></Copied>
        </a>
        <div class="api-docs__example-content-container">
          <div
            v-if="Object.keys(mapping).length > 0"
            class="api-docs__example-content-side"
          >
            <div
              v-for="(lineValue, line) in formattedResponse.lines"
              :key="'response-info-line-' + line"
              class="api-docs__example-content-line"
              :style="'top:' + (line - 1) * 21 + 'px;'"
              :title="lineValue"
            >
              {{ lineValue }}
            </div>
          </div>
          <div class="api-docs__example-content-wrapper">
            <div class="api-docs__example-content">
              <pre
                class="api-docs__example-content"
              ><code>{{ formattedResponse.example }}</code></pre>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { mappingToStringifiedJSONLines } from '@baserow/modules/core/utils/object'

export default {
  name: 'APIDocsExample',
  props: {
    value: {
      type: Object,
      required: true,
    },
    type: {
      type: String,
      required: false,
      default: 'GET',
    },
    url: {
      type: String,
      required: false,
      default: '',
    },
    fileRequest: {
      type: String,
      required: false,
      default: '',
    },
    request: {
      type: [Object, Boolean],
      required: false,
      default: false,
    },
    response: {
      type: [Object, Boolean, Array],
      required: false,
      default: false,
    },
    mapping: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    includeUserFieldsCheckbox: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  computed: {
    formattedResponse() {
      return this.getFormattedResponse()
    },
    formattedRequest() {
      return this.getFormattedRequest()
    },
  },
  methods: {
    format(value) {
      return value !== false ? JSON.stringify(value, null, 4) : ''
    },
    getFormattedRequest() {
      if (this.value.type === 'curl') {
        return this.getCURLRequestExample()
      } else if (this.value.type === 'http') {
        return this.getHTTPRequestExample()
      } else if (this.value.type === 'javascript') {
        return this.getJavaScriptExample()
      } else if (this.value.type === 'python') {
        return this.getPythonExample()
      }
      return ''
    },
    getCURLRequestExample() {
      let index = 3
      let example = 'curl \\'

      if (this.type !== '') {
        index++
        example += `\n-X ${this.type} \\`
      }

      example += '\n-H "Authorization: Token YOUR_DATABASE_TOKEN" \\'

      if (this.request !== false) {
        index++
        example += '\n-H "Content-Type: application/json" \\'
      }

      if (this.fileRequest !== '') {
        index++
        example += ` \\\n-F file=@${this.fileRequest}`
      }

      example += `\n"${this.url}"`

      if (this.request !== false) {
        index++
        example += ` \\\n--data '${this.format(this.request)}'`
      }

      return {
        example,
        lines: mappingToStringifiedJSONLines(this.mapping, this.request, index),
      }
    },
    getHTTPRequestExample() {
      let index = 2
      let example = ''

      if (this.type !== '') {
        index++
        example += `${this.type.toUpperCase()} `
      }

      example += `${this.url} HTTP`
      example += '\nAuthorization: Token YOUR_DATABASE_TOKEN'

      if (this.fileRequest !== '') {
        example += '\nContent-Length: YOUR_CONTENT_LENGTH'
        example +=
          '\nContent-Type: multipart/form-data; boundary=------------------------YOUR_BOUNDARY'
      }

      if (this.request !== false) {
        index += 2
        example += '\nContent-Type: application/json'
        example += `\n\n${this.format(this.request)}`
      }

      return {
        example,
        lines: mappingToStringifiedJSONLines(this.mapping, this.request, index),
      }
    },
    getJavaScriptExample() {
      let index = 5
      let example = ''
      if (this.fileRequest !== '') {
        example += 'const formData = new FormData()'
        example += `\nformData.append('file', '${this.fileRequest}')`
        example += "\naxios.post('/fileupload', formData, {"
      } else {
        example = 'axios({'
      }

      if (this.type !== '') {
        index++
        example += `\n  method: "${this.type.toUpperCase()}",`
      }

      example += `\n  url: "${this.url}",`
      example += '\n  headers: {'
      example += '\n    Authorization: "Token YOUR_DATABASE_TOKEN"'

      if (this.fileRequest !== '') {
        index++
        example += ',\n    "Content-Type": "multipart/form-data"'
      }

      if (this.request !== false) {
        index++
        example += ',\n    "Content-Type": "application/json"'
      }

      example += '\n  }'

      if (this.request !== false) {
        index++
        const data = this.format(this.request).slice(0, -1) + '  }'
        example += `,\n  data: ${data}`
      }

      example += '\n})'
      return {
        example,
        lines: mappingToStringifiedJSONLines(this.mapping, this.request, index),
      }
    },
    getPythonExample() {
      let index = 5
      const type = (this.type || 'get').toLowerCase()
      let example = `requests.${type}(`
      example += `\n    "${this.url}",`

      example += '\n    headers={'
      example += `\n        "Authorization": "Token YOUR_DATABASE_TOKEN"`

      if (this.request !== false) {
        index++
        example += `,\n        "Content-Type": "application/json"`
      }

      example += '\n    }'

      if (this.fileRequest !== '') {
        index++
        example += `\n    files={'file': open('${this.fileRequest}', 'rb')}`
      }

      if (this.request !== false) {
        index++
        const data = this.format(this.request).split('\n').join('\n    ')
        example += `,\n    json=${data}`
      }

      example += '\n)'
      return {
        example,
        lines: mappingToStringifiedJSONLines(this.mapping, this.request, index),
      }
    },
    getFormattedResponse() {
      return {
        example: this.format(this.response),
        lines: mappingToStringifiedJSONLines(this.mapping, this.response),
      }
    },
    copyToClipboard(value) {
      copyToClipboard(value)
    },
  },
}
</script>
