<template>
  <div class="sidebar-overlay" @click="emit('close')">
    <div class="sidebar" @click.stop>
      <div class="sidebar-header">
        <h2>{{ asset.name }}</h2>
        <button @click="emit('close')" class="close-btn">×</button>
      </div>

      <div class="sidebar-content">
        <div class="asset-section">
          <h3>Details</h3>
          <div class="detail-item">
            <span class="label">Owner:</span>
            <span class="value">{{ asset.owner.email }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Size:</span>
            <span class="value">{{ formatFileSize(asset.file_size) }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Type:</span>
            <span class="value">{{ asset.mime_type }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Created:</span>
            <span class="value">{{ formatDate(asset.created_on) }}</span>
          </div>
        </div>

        <div class="asset-section">
          <h3>Sharing</h3>
          <div class="sharing-options">
            <label>
              <input v-model="asset.is_public" type="checkbox" />
              Public
            </label>
          </div>
        </div>

        <div class="asset-section">
          <h3>Versions</h3>
          <div class="version-list">
            <div v-if="versions.length === 0" class="empty">
              <p>No versions yet</p>
            </div>
            <div v-for="version in versions" :key="version.id" class="version-item">
              <span class="version-label">v{{ version.version_number }}</span>
              <span class="version-date">{{ formatDate(version.created_on) }}</span>
            </div>
          </div>
        </div>

        <div class="asset-section">
          <h3>Tags</h3>
          <div class="tags-input">
            <input v-model="newTag" placeholder="Add a tag" @keydown.enter="addTag" />
            <button @click="addTag" class="btn-small">Add</button>
          </div>
          <div class="tags-list">
            <span v-for="tag in asset.tags" :key="tag" class="tag">
              {{ tag }}
              <button @click="removeTag(tag)" class="remove-tag">×</button>
            </span>
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <button @click="handleDelete" class="btn-danger">Delete</button>
        <button @click="emit('close')" class="btn-secondary">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps({
  asset: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['close', 'update', 'delete']);

const newTag = ref('');
const versions = ref([]);

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString();
};

const addTag = () => {
  if (newTag.value && !props.asset.tags.includes(newTag.value)) {
    props.asset.tags.push(newTag.value);
    emit('update', props.asset.id, { tags: props.asset.tags });
    newTag.value = '';
  }
};

const removeTag = (tag) => {
  props.asset.tags = props.asset.tags.filter((t) => t !== tag);
  emit('update', props.asset.id, { tags: props.asset.tags });
};

const handleDelete = () => {
  if (confirm('Are you sure you want to delete this asset?')) {
    emit('delete', props.asset.id);
  }
};
</script>

<style scoped lang="scss">
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  justify-content: flex-end;
  z-index: 100;
}

.sidebar {
  background: white;
  width: 350px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #eee;

  h2 {
    margin: 0;
    font-size: 1.2rem;
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

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.asset-section {
  margin-bottom: 2rem;

  h3 {
    font-size: 0.9rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #666;
    margin: 0 0 1rem;
  }
}

.detail-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.8rem;

  .label {
    color: #999;
    font-size: 0.9rem;
  }

  .value {
    color: #333;
    font-weight: 500;
  }
}

.sharing-options {
  label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;

    input {
      cursor: pointer;
    }
  }
}

.version-list {
  .version-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    background: #f9f9f9;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;

    .version-label {
      font-weight: 600;
      color: #333;
    }

    .version-date {
      color: #999;
    }
  }

  .empty {
    text-align: center;
    color: #999;
    padding: 1rem;
  }
}

.tags-input {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;

  input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 4px;

    &:focus {
      outline: none;
      border-color: #3366cc;
    }
  }

  .btn-small {
    padding: 0.5rem 1rem;
    background: #3366cc;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;

    &:hover {
      background: #2953a0;
    }
  }
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;

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

.sidebar-footer {
  display: flex;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #eee;

  button {
    flex: 1;
    padding: 0.75rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;

    &.btn-danger {
      background: #e74c3c;
      color: white;

      &:hover {
        background: #c0392b;
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
