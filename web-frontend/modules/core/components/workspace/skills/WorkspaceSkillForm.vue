<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('workspaceSkills.nameLabel')"
      :error="v$.values.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        :disabled="readOnly"
        :placeholder="$t('workspaceSkills.namePlaceholder')"
        :error="v$.values.name.$error"
        @blur="v$.values.name.$touch"
      ></FormInput>
      <template #error>
        {{
          nameNotUnique
            ? $t('workspaceSkills.nameNotUnique')
            : $t('error.requiredField')
        }}
      </template>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('workspaceSkills.descriptionLabel')"
      :helper-text="$t('workspaceSkills.descriptionHelp')"
      class="margin-bottom-2"
    >
      <FormTextarea
        v-model="values.description"
        :rows="2"
        :disabled="readOnly"
        :placeholder="$t('workspaceSkills.descriptionPlaceholder')"
      ></FormTextarea>
    </FormGroup>
    <FormGroup small-label class="margin-bottom-2">
      <template #label>
        <span class="workspace-skill-form__content-label">
          <span>{{ $t('workspaceSkills.contentLabel') }}</span>
          <span class="workspace-skill-form__content-actions">
            <a
              v-if="!readOnly"
              class="workspace-skill-form__mode"
              :title="$t('workspaceSkills.importHelp')"
              @click.prevent="$refs.fileInput.click()"
            >
              <i class="iconoir-upload"></i>
              {{ $t('workspaceSkills.importFile') }}
            </a>
            <input
              ref="fileInput"
              type="file"
              accept=".md,.mdc,.markdown,.txt,text/markdown,text/plain"
              class="workspace-skill-form__file-input"
              @change="importFile"
            />
            <a
              class="workspace-skill-form__mode"
              @click.prevent="toggleMarkdown"
            >
              <i :class="markdownMode ? 'iconoir-text' : 'iconoir-code'"></i>
              {{
                markdownMode
                  ? $t('workspaceSkills.richTextMode')
                  : $t('workspaceSkills.markdownMode')
              }}
            </a>
          </span>
        </span>
      </template>
      <FormTextarea
        v-if="markdownMode"
        v-model="values.content"
        class="workspace-skill-form__markdown"
        :rows="16"
        :disabled="readOnly"
        :placeholder="$t('workspaceSkills.contentPlaceholder')"
      ></FormTextarea>
      <RichTextEditor
        v-else
        ref="editor"
        v-model="richContent"
        class="form-input workspace-skill-form__editor"
        :editable="!readOnly"
        :enable-rich-text-formatting="true"
        :placeholder="$t('workspaceSkills.contentPlaceholder')"
        thin-scrollbar
        @update:model-value="syncFromEditor"
      ></RichTextEditor>
      <div class="workspace-skill-form__counter">
        {{ $t('workspaceSkills.characters', { count: values.content.length }) }}
      </div>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import { parseSkillFile } from '@baserow/modules/core/utils/skillFile'

/**
 * Edits a workspace skill. The content is stored as markdown; the rich text
 * editor works on a markdown copy and is serialized back before the form
 * values are read, so switching to the raw markdown view or saving always
 * sees the same text.
 */
export default {
  name: 'WorkspaceSkillForm',
  components: { RichTextEditor },
  mixins: [form],
  props: {
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['name', 'description', 'content'],
      values: {
        name: '',
        description: '',
        content: '',
      },
      markdownMode: false,
      richContent: '',
      nameNotUnique: false,
    }
  },
  watch: {
    'values.name'() {
      this.nameNotUnique = false
    },
  },
  created() {
    this.richContent = this.values.content
  },
  mounted() {
    this.$refs.name?.focus()
  },
  validations() {
    return {
      values: {
        name: { required },
      },
    }
  },
  methods: {
    // Only called for edits made in the editor; programmatic content (an
    // import, switching back from markdown) is already in `values.content`.
    syncFromEditor() {
      if (!this.markdownMode && this.$refs.editor) {
        this.values.content = this.$refs.editor.serializeToMarkdown()
      }
    },
    toggleMarkdown() {
      if (this.markdownMode) {
        // Back to rich text: the editor re-parses the markdown.
        this.richContent = this.values.content
      } else {
        this.syncFromEditor()
      }
      this.markdownMode = !this.markdownMode
    },
    // Reads a SKILL.md, Cursor rule, Copilot instructions file or plain
    // markdown into the form; a typed name and description are kept.
    async importFile(event) {
      const file = event.target.files?.[0]
      event.target.value = ''
      if (!file) {
        return
      }
      const parsed = parseSkillFile(await file.text(), file.name)
      if (this.values.name.trim() === '' && parsed.name) {
        this.values.name = parsed.name
      }
      if (this.values.description.trim() === '' && parsed.description) {
        this.values.description = parsed.description
      }
      this.values.content = parsed.content
      this.richContent = parsed.content
    },
    setNameNotUnique() {
      this.nameNotUnique = true
      this.v$.values.name.$touch()
    },
    getFormValues() {
      this.syncFromEditor()
      return { ...this.values }
    },
  },
}
</script>
