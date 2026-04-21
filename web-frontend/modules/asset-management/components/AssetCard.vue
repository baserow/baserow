<template>
  <div class="asset-card" @click="emit('click')">
    <div class="asset-preview">
      <img v-if="isImage" :src="asset.file" :alt="asset.name" class="asset-image" />
      <div v-else class="asset-icon">
        <i :class="getFileIcon(asset.mime_type)"></i>
      </div>
      <div class="asset-overlay">
        <button @click.stop="emit('download')" class="btn-icon" title="Download">
          <i class="icon icon-download"></i>
        </button>
        <button @click.stop="emit('share')" class="btn-icon" title="Share">
          <i class="icon icon-share"></i>
        </button>
        <button @click.stop="emit('delete')" class="btn-icon btn-danger" title="Delete">
          <i class="icon icon-trash"></i>
        </button>
      </div>
    </div>
    <div class="asset-info">
      <h3 class="asset-name">{{ asset.name }}</h3>
      <p class="asset-size">{{ formatFileSize(asset.file_size) }}</p>
      <div class="asset-stats">
        <span><i class="icon icon-eye"></i> {{ asset.view_count }}</span>
        <span><i class="icon icon-download"></i> {{ asset.download_count }}</span>
      </div>
      <div v-if="asset.tags.length" class="asset-tags">
        <span v-for="tag in asset.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps({
  asset: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['click', 'download', 'share', 'delete']);

const isImage = computed(() => {
  return props.asset.mime_type.startsWith('image/');
});

const getFileIcon = (mimeType) => {
  const iconMap = {
    'application/pdf': 'icon-file-pdf',
    'application/zip': 'icon-file-zip',
    'video/mp4': 'icon-file-video',
    'audio/mpeg': 'icon-file-audio',
    'application/msword': 'icon-file-word',
  };

  return iconMap[mimeType] || 'icon-file';
};

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};
</script>

<style scoped lang="scss">
.asset-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    transform: translateY(-4px);

    .asset-overlay {
      opacity: 1;
    }
  }
}

.asset-preview {
  position: relative;
  width: 100%;
  height: 200px;
  background: linear-gradient(135deg, #f5f5f5, #e9e9e9);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.asset-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-icon {
  font-size: 3rem;
  color: #999;
}

.asset-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  opacity: 0;
  transition: opacity 0.2s;
}

.btn-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;

  i {
    font-size: 1.2rem;
    color: #333;
  }

  &:hover {
    transform: scale(1.1);
    background: #f0f0f0;
  }

  &.btn-danger {
    i {
      color: #e74c3c;
    }
  }
}

.asset-info {
  padding: 1rem;
}

.asset-name {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #333;
}

.asset-size {
  font-size: 0.85rem;
  color: #999;
  margin: 0;
}

.asset-stats {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #666;

  span {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
}

.asset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.5rem;

  .tag {
    display: inline-block;
    background: #f0f0f0;
    color: #666;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
  }
}
</style>
