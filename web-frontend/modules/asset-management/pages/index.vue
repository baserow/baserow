<template>
  <div class="asset-management">
    <div class="asset-header">
      <h1>Asset Management</h1>
      <div class="asset-actions">
        <button @click="showUploadModal = true" class="btn btn-primary">
          <i class="icon icon-upload"></i>
          Upload Asset
        </button>
        <button @click="showCategoryModal = true" class="btn btn-secondary">
          <i class="icon icon-plus"></i>
          New Category
        </button>
      </div>
    </div>

    <div class="asset-toolbar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search assets..."
        class="search-input"
      />
      <select v-model="selectedCategory" class="filter-select">
        <option value="">All Categories</option>
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">
          {{ cat.name }}
        </option>
      </select>
      <select v-model="sortBy" class="filter-select">
        <option value="date_desc">Newest First</option>
        <option value="date_asc">Oldest First</option>
        <option value="name">Name (A-Z)</option>
        <option value="size">Size (Large to Small)</option>
      </select>
    </div>

    <div v-if="loading" class="loading-spinner">
      <p>Loading assets...</p>
    </div>

    <div v-else-if="filteredAssets.length === 0" class="empty-state">
      <p>No assets found. Upload one to get started!</p>
    </div>

    <div v-else class="asset-grid">
      <AssetCard
        v-for="asset in filteredAssets"
        :key="asset.id"
        :asset="asset"
        @click="selectAsset(asset)"
        @delete="deleteAsset(asset.id)"
        @download="downloadAsset(asset.id)"
        @share="shareAsset(asset.id)"
      />
    </div>

    <!-- Asset Detail Sidebar -->
    <AssetDetailSidebar
      v-if="currentAsset"
      :asset="currentAsset"
      @close="currentAsset = null"
      @update="handleAssetUpdate"
      @delete="handleAssetDelete"
    />

    <!-- Upload Modal -->
    <AssetUploadModal
      v-if="showUploadModal"
      @close="showUploadModal = false"
      @upload="handleAssetUpload"
    />

    <!-- Category Modal -->
    <CategoryModal
      v-if="showCategoryModal"
      @close="showCategoryModal = false"
      @create="handleCategoryCreate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAssetStore } from '../store/assets';
import AssetCard from '../components/AssetCard.vue';
import AssetDetailSidebar from '../components/AssetDetailSidebar.vue';
import AssetUploadModal from '../components/AssetUploadModal.vue';
import CategoryModal from '../components/CategoryModal.vue';

const route = useRoute();
const router = useRouter();
const assetStore = useAssetStore();

const workspaceId = computed(() => route.params.workspaceId);
const searchQuery = ref('');
const selectedCategory = ref('');
const sortBy = ref('date_desc');
const showUploadModal = ref(false);
const showCategoryModal = ref(false);

const assets = computed(() => assetStore.getAssets);
const categories = computed(() => assetStore.getCategories);
const currentAsset = computed(() => assetStore.getCurrentAsset);
const loading = computed(() => assetStore.isLoading);

const filteredAssets = computed(() => {
  let result = assets.value;

  if (selectedCategory.value) {
    result = result.filter((a) => a.category?.id === selectedCategory.value);
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(
      (a) =>
        a.name.toLowerCase().includes(query) ||
        a.description.toLowerCase().includes(query) ||
        a.tags.some((t) => t.toLowerCase().includes(query))
    );
  }

  // Sort
  switch (sortBy.value) {
    case 'date_asc':
      result.sort((a, b) => new Date(a.created_on).getTime() - new Date(b.created_on).getTime());
      break;
    case 'name':
      result.sort((a, b) => a.name.localeCompare(b.name));
      break;
    case 'size':
      result.sort((a, b) => b.file_size - a.file_size);
      break;
    default:
      result.sort((a, b) => new Date(b.created_on).getTime() - new Date(a.created_on).getTime());
  }

  return result;
});

const loadAssets = async () => {
  assetStore.setLoading(true);
  try {
    const { $assetService } = useNuxtApp();
    const data = await $assetService.listAssets(workspaceId.value);
    assetStore.setAssets(data);
  } catch (error) {
    assetStore.setError('Failed to load assets');
    console.error(error);
  } finally {
    assetStore.setLoading(false);
  }
};

const loadCategories = async () => {
  try {
    const { $assetService } = useNuxtApp();
    const data = await $assetService.listCategories(workspaceId.value);
    assetStore.setCategories(data);
  } catch (error) {
    console.error('Failed to load categories', error);
  }
};

const selectAsset = (asset) => {
  assetStore.setCurrentAsset(asset);
};

const deleteAsset = async (assetId) => {
  try {
    const { $assetService } = useNuxtApp();
    await $assetService.deleteAsset(workspaceId.value, assetId);
    assetStore.removeAsset(assetId);
  } catch (error) {
    assetStore.setError('Failed to delete asset');
    console.error(error);
  }
};

const downloadAsset = async (assetId) => {
  try {
    const { $assetService } = useNuxtApp();
    const response = await $assetService.downloadAsset(workspaceId.value, assetId);
    window.location.href = response.download_url;
  } catch (error) {
    assetStore.setError('Failed to download asset');
    console.error(error);
  }
};

const shareAsset = async (assetId) => {
  // Handle asset sharing
  console.log('Share asset:', assetId);
};

const handleAssetUpload = async (formData) => {
  try {
    const { $assetService } = useNuxtApp();
    const asset = await $assetService.createAsset(workspaceId.value, formData);
    assetStore.addAsset(asset);
    showUploadModal.value = false;
  } catch (error) {
    assetStore.setError('Failed to upload asset');
    console.error(error);
  }
};

const handleAssetUpdate = async (assetId, data) => {
  try {
    const { $assetService } = useNuxtApp();
    const asset = await $assetService.updateAsset(workspaceId.value, assetId, data);
    assetStore.updateAsset(asset);
  } catch (error) {
    assetStore.setError('Failed to update asset');
    console.error(error);
  }
};

const handleAssetDelete = (assetId) => {
  deleteAsset(assetId);
  assetStore.setCurrentAsset(null);
};

const handleCategoryCreate = async (data) => {
  try {
    const { $assetService } = useNuxtApp();
    const category = await $assetService.createCategory(workspaceId.value, data);
    assetStore.addCategory(category);
    showCategoryModal.value = false;
  } catch (error) {
    assetStore.setError('Failed to create category');
    console.error(error);
  }
};

onMounted(() => {
  loadAssets();
  loadCategories();
});
</script>

<style scoped lang="scss">
.asset-management {
  padding: 2rem;
  height: 100%;
  overflow-y: auto;
}

.asset-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;

  h1 {
    font-size: 2rem;
    font-weight: 600;
    margin: 0;
  }

  .asset-actions {
    display: flex;
    gap: 1rem;
  }
}

.asset-toolbar {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;

  .search-input,
  .filter-select {
    padding: 0.5rem 1rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 0.9rem;

    &:focus {
      outline: none;
      border-color: #3366cc;
      box-shadow: 0 0 0 2px rgba(51, 102, 204, 0.1);
    }
  }

  .search-input {
    flex: 1;
  }
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1.5rem;
}

.loading-spinner,
.empty-state {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &.btn-primary {
    background-color: #3366cc;
    color: white;

    &:hover {
      background-color: #2953a0;
    }
  }

  &.btn-secondary {
    background-color: #f0f0f0;
    color: #333;

    &:hover {
      background-color: #e0e0e0;
    }
  }
}
</style>
