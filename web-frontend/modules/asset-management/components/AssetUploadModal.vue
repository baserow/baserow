<template>
  <div class="modal-overlay" @click="emit('close')">
    <div class="modal" @click.stop>
      <div class="modal-header">
        <h2>Upload Asset</h2>
        <button @click="emit('close')" class="close-btn">×</button>
      </div>

      <div class="modal-content">
        <div class="upload-area" @dragover.prevent @drop="handleDrop">
          <input
            ref="fileInput"
            type="file"
            @change="handleFileSelect"
            style="display: none"
          />
          <div @click="fileInput?.click()" class="upload-prompt">
            <i class="icon icon-cloud-upload"></i>
            <p>Drag and drop files here or click to browse</p>
          </div>
        </div>

        <form @submit.prevent="submitForm" class="upload-form">
          <div class="form-group">
            <label>File Name</label>
            <input v-model="formData.name" type="text" placeholder="Enter file name" />
          </div>

          <div class="form-group">
            <label>Description</label>
            <textarea v-model="formData.description" placeholder="Optional description"></textarea>
          </div>

          <div class="form-group">
            <label>Category</label>
            <select v-model="formData.category">
              <option value="">None</option>
              <option v-for="cat in categories" :key="cat.id" :value="cat.id">
                {{ cat.name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Tags</label>
            <input
              v-model="newTag"
              type="text"
              placeholder="Add tags (comma-separated)"
              @keydown.enter="addTag"
            />
          </div>

          <div class="tags-list">
            <span v-for="tag in formData.tags" :key="tag" class="tag">
              {{ tag }}
              <button type="button" @click="removeTag(tag)" class="remove-tag">×</button>
            </span>
          </div>

          <div class="form-group checkbox">
            <label>
              <input v-model="formData.is_public" type="checkbox" />
              Make Public
            </label>
          </div>

          <div class="modal-footer">
            <button type="button" @click="emit('close')" class="btn-secondary">
              Cancel
            </button>
            <button type="submit" class="btn-primary">Upload</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAssetStore } from '../store/assets';

const emit = defineEmits(['close', 'upload']);
const assetStore = useAssetStore();

const fileInput = ref();
const selectedFile = ref(null);
const newTag = ref('');
const formData = ref({
  name: '',
  description: '',
  category: '',
  tags: [],
  is_public: false,
});

const categories = computed(() => assetStore.getCategories);

const handleFileSelect = (e) => {
  const file = e.target.files?.[0];
  if (file) {
    selectedFile.value = file;
    formData.value.name = file.name;
  }
};

const handleDrop = (e) => {
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    selectedFile.value = file;
    formData.value.name = file.name;
  }
};

const addTag = () => {
  if (newTag.value) {
    const tags = newTag.value.split(',').map((t) => t.trim());
    formData.value.tags = [...new Set([...formData.value.tags, ...tags])];
    newTag.value = '';
  }
};

const removeTag = (tag) => {
  formData.value.tags = formData.value.tags.filter((t) => t !== tag);
};

const submitForm = () => {
  if (!selectedFile.value) {
    alert('Please select a file');
    return;
  }

  const uploadFormData = new FormData();
  uploadFormData.append('file', selectedFile.value);
  uploadFormData.append('name', formData.value.name);
  uploadFormData.append('description', formData.value.description);
  uploadFormData.append('category', formData.value.category);
  uploadFormData.append('tags', JSON.stringify(formData.value.tags));
  uploadFormData.append('is_public', formData.value.is_public);

  emit('upload', uploadFormData);
};
</script>

<style scoped lang="scss">
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: white;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #eee;

  h2 {
    margin: 0;
    font-size: 1.3rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #999;

    &:hover {
      color: #333;
    }
  }
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.upload-area {
  margin-bottom: 2rem;

  .upload-prompt {
    border: 2px dashed #3366cc;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #f0f6ff;
    }

    i {
      font-size: 2rem;
      color: #3366cc;
      display: block;
      margin-bottom: 0.5rem;
    }

    p {
      margin: 0;
      color: #666;
    }
  }
}

.upload-form {
  .form-group {
    margin-bottom: 1.5rem;

    label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 600;
      color: #333;
    }

    input[type='text'],
    textarea,
    select {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-family: inherit;

      &:focus {
        outline: none;
        border-color: #3366cc;
        box-shadow: 0 0 0 2px rgba(51, 102, 204, 0.1);
      }
    }

    textarea {
      resize: vertical;
      min-height: 80px;
    }

    &.checkbox {
      label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0;

        input {
          width: auto;
        }
      }
    }
  }
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: #e8f0fe;
    color: #3366cc;
    padding: 0.3rem 0.6rem;
    border-radius: 3px;
    font-size: 0.85rem;

    .remove-tag {
      background: none;
      border: none;
      color: #3366cc;
      cursor: pointer;
      font-weight: bold;

      &:hover {
        color: #2953a0;
      }
    }
  }
}

.modal-footer {
  display: flex;
  gap: 1rem;
  padding-top: 1.5rem;
  border-top: 1px solid #eee;

  button {
    flex: 1;
    padding: 0.75rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;

    &.btn-primary {
      background: #3366cc;
      color: white;

      &:hover {
        background: #2953a0;
      }
    }

    &.btn-secondary {
      background: #f0f0f0;
      color: #333;

      &:hover {
        background: #e0e0e0;
      }
    }
  }
}
</style>
