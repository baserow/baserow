<template>
  <div class="modal-overlay" @click="emit('close')">
    <div class="modal" @click.stop>
      <div class="modal-header">
        <h2>Create Category</h2>
        <button @click="emit('close')" class="close-btn">×</button>
      </div>

      <form @submit.prevent="handleSubmit" class="modal-content">
        <div class="form-group">
          <label>Category Name</label>
          <input
            v-model="formData.name"
            type="text"
            placeholder="Enter category name"
            required
          />
        </div>

        <div class="form-group">
          <label>Description</label>
          <textarea
            v-model="formData.description"
            placeholder="Optional description"
          ></textarea>
        </div>

        <div class="form-group">
          <label>Color</label>
          <div class="color-picker">
            <input v-model="formData.color" type="color" />
            <span class="color-preview" :style="{ backgroundColor: formData.color }"></span>
          </div>
        </div>

        <div class="form-group">
          <label>Icon</label>
          <select v-model="formData.icon">
            <option value="folder">Folder</option>
            <option value="image">Image</option>
            <option value="video">Video</option>
            <option value="document">Document</option>
            <option value="archive">Archive</option>
            <option value="music">Music</option>
          </select>
        </div>

        <div class="modal-footer">
          <button type="button" @click="emit('close')" class="btn-secondary">
            Cancel
          </button>
          <button type="submit" class="btn-primary">Create</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits(['close', 'create']);

const formData = ref({
  name: '',
  description: '',
  color: '#3366CC',
  icon: 'folder',
});

const handleSubmit = () => {
  if (!formData.value.name) {
    alert('Category name is required');
    return;
  }

  emit('create', { ...formData.value });
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
  max-width: 400px;
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

  .color-picker {
    display: flex;
    gap: 1rem;
    align-items: center;

    input[type='color'] {
      width: 50px;
      height: 40px;
      border: 1px solid #ddd;
      cursor: pointer;
    }

    .color-preview {
      width: 40px;
      height: 40px;
      border-radius: 4px;
      border: 1px solid #ddd;
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
