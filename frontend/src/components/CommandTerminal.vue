<script setup>
import { ref, onMounted, nextTick, computed, shallowRef } from 'vue'
import html2canvas from 'html2canvas'

const output = ref('')
const outputArea = ref(null)

const projects = ref([])
const currentProject = ref(null)
const showProjectSelector = ref(true)
const newProjectName = ref('')
const showDeleteConfirm = ref(false)
const projectToDelete = ref(null)
const createError = ref('')

// 生成相关状态
const promptText = ref('')
const isGenerating = ref(false)
const generateError = ref('')
const htmlUrl = ref('')
const showOutputModal = ref(false) // 是否显示输出弹窗

// 截图相关状态
const previewRef = ref(null) // 预览区域的 ref
const iframeRef = ref(null) // iframe 的 ref
const isCapturing = ref(false) // 是否正在截图
const captureError = ref('') // 截图错误信息

// 悬浮按钮状态
const isAtTop = ref(true) // 是否在顶部
const generateAreaRef = ref(null) // 生成输入区域的 ref
const projectsListRef = ref(null) // 项目卡片列表的 ref
const terminalContentRef = ref(null) // 主滚动容器的 ref

// 历史提示词记录
const promptHistory = ref([])
const showHistoryTab = ref(false) // 控制显示日志还是历史记录
// 所有项目列表 - 对象数组（用于项目卡片展示）
const allProjects = shallowRef([])

// 项目名称列表 - 字符串数组（用于项目选择界面）
const projectNames = shallowRef([])

// 缩略图宽高比缓存
const thumbnailRatios = ref({})

// 分页相关
const currentPage = ref(1)
const pageSize = 6
const totalPages = ref(1)
const total = ref(0)

// 请求锁（防止重复请求）
let isLoadingProjects = false

// 上一页 (后端分页)
const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    loadProjectCards()
  }
}

// 下一页 (后端分页)
const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    loadProjectCards()
  }
}

// 复制提示词反馈状态
const copiedProject = ref(null) // 记录哪个项目刚刚被复制了

// 项目切换动画状态
const projectTransitioning = ref(false) // 是否正在切换项目
const transitioningProject = ref(null) // 正在切换的项目名称

// 切换提示 toast
const showToast = ref(false) // 是否显示 toast
const toastMessage = ref('') // toast 消息内容
let toastTimer = null // toast 定时器

// 显示 toast 提示
const showToastMessage = (message) => {
  if (toastTimer) clearTimeout(toastTimer)
  toastMessage.value = message
  showToast.value = true
  // 2秒后自动消失
  toastTimer = setTimeout(() => {
    showToast.value = false
    toastTimer = null
  }, 2000)
}

const loadProjects = async () => {
  try {
    const res = await fetch('/api/projects')
    const data = await res.json()
    // 项目选择界面需要字符串数组
    projectNames.value = data.projects || []
    currentProject.value = data.current_project
    showProjectSelector.value = !data.current_project?.name
  } catch (e) {
    console.error('加载项目列表失败:', e)
  }
}

// 加载项目卡片数据（带详细信息，使用分页）
const loadProjectCards = async () => {
  if (isLoadingProjects) return  // 防止重复请求
  isLoadingProjects = true
  
  try {
    const res = await fetch(`/api/projects/list?page=${currentPage.value}&page_size=${pageSize}`)
    const data = await res.json()
    // 项目卡片需要对象数组
    allProjects.value = data.projects || []
    total.value = data.total || 0
    totalPages.value = data.total_pages || 1
  } catch (e) {
    console.error('加载项目卡片失败:', e)
    allProjects.value = []
  } finally {
    isLoadingProjects = false
  }
}

// 切换到其他项目
const switchToProject = async (name) => {
  if (projectTransitioning.value) return // 防止重复点击
  if (name === currentProject.value?.name) return // 不能切换到当前项目
  
  // 开始过渡动画
  projectTransitioning.value = true
  transitioningProject.value = name
  
  // 同时触发平滑滚动到顶部
  const container = terminalContentRef.value
  if (container) {
    container.scrollTo({ top: 0, behavior: 'smooth' })
  }
  
  // 等待动画完成后执行切换
  setTimeout(async () => {
    await selectProject(name)
    // 切换完成后显示 toast
    showToastMessage(`切换到 "${name}" 项目`)
    // 清除动画状态
    projectTransitioning.value = false
    transitioningProject.value = null
  }, 500)
}

// 加载历史提示词记录
const loadPromptHistory = async () => {
  if (!currentProject.value?.name) {
    promptHistory.value = []
    return
  }
  
  try {
    const res = await fetch('/api/prompts')
    const data = await res.json()
    promptHistory.value = data.prompts || []
  } catch (e) {
    console.error('加载提示词历史记录失败:', e)
    promptHistory.value = []
  }
}

// 跳转到指定页 (后端分页)
const goToPage = (page) => {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  loadProjectCards()  // 重新请求后端获取当前页数据
  // 滚动到项目列表顶部
  const container = projectsListRef.value
  if (container) {
    container.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

const selectProject = async (name) => {
  try {
    const res = await fetch(`/api/projects/${name}/select`, { method: 'POST' })
    const data = await res.json()
    currentProject.value = data.current_project
    showProjectSelector.value = false
    output.value = `=== 已进入项目: ${name} ===\n`
    
    // 检测是否有 index.html，有则自动渲染
    if (data.has_html) {
      htmlUrl.value = '/api/html?' + Date.now()
    } else {
      htmlUrl.value = ''
    }
    
    // 加载历史提示词记录
    await loadPromptHistory()
    // 加载项目卡片数据（带详细信息）
    await loadProjectCards()
  } catch (e) {
    output.value += `Error: ${e.message}\n`
  }
}

const createProject = async () => {
  if (!newProjectName.value.trim()) return
  createError.value = ''
  
  try {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newProjectName.value })
    })
    if (res.ok) {
      newProjectName.value = ''
      createError.value = ''
      await loadProjects()
    } else {
      const data = await res.json()
      createError.value = data.detail || '创建失败'
    }
  } catch (e) {
    createError.value = e.message
  }
}

// 监听输入，清空错误提示
const onNameInput = () => {
  createError.value = ''
}

const confirmDelete = (name) => {
  projectToDelete.value = name
  showDeleteConfirm.value = true
}

const deleteProject = async () => {
  if (!projectToDelete.value) return
  
  try {
    const res = await fetch(`/api/projects/${projectToDelete.value}`, { method: 'DELETE' })
    if (res.ok) {
      showDeleteConfirm.value = false
      projectToDelete.value = null
      await loadProjects()
    } else {
      const data = await res.json()
      output.value += `Error: ${data.detail}\n`
    }
  } catch (e) {
    output.value += `Error: ${e.message}\n`
  }
}

const cancelDelete = () => {
  showDeleteConfirm.value = false
  projectToDelete.value = null
}

const exitProject = async () => {
  if (isGenerating.value) return // 生成中禁止退出
  
  try {
    await fetch('/api/projects/exit', { method: 'POST' })
    currentProject.value = null
    showProjectSelector.value = true
    output.value = ''
    htmlUrl.value = ''
  } catch (e) {
    output.value += `Error: ${e.message}\n`
  }
}

// 悬浮按钮滚动功能
const toggleScroll = () => {
  const container = terminalContentRef.value
  if (!container) return
  
  if (isAtTop.value) {
    // 滚动到项目卡片列表
    const projectsListElement = projectsListRef.value
    if (projectsListElement) {
      const targetTop = projectsListElement.offsetTop - 20
      container.scrollTo({ top: targetTop, behavior: 'smooth' })
    }
    isAtTop.value = false
  } else {
    // 返回顶部
    container.scrollTo({ top: 0, behavior: 'smooth' })
    isAtTop.value = true
  }
}

// 生成网页
const generateWebpage = async () => {
  if (!promptText.value.trim()) return
  if (isGenerating.value) return
  
  isGenerating.value = true
  generateError.value = ''
  
  output.value += `=== 开始生成网页 ===\n输入需求：${promptText.value}\n\n`
  scrollToBottom()
  
  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: promptText.value })
    })
    const data = await res.json()
    
    if (data.success) {
      output.value += `✅ 网页生成成功！\n`
      // 刷新 iframe 加载新内容
      htmlUrl.value = data.html_url + '?' + Date.now()
      // 清空输入框
      promptText.value = ''
      // 刷新历史记录
      await loadPromptHistory()
    } else {
      output.value += `❌ ${data.message}\n`
      if (data.output) {
        output.value += `输出：${data.output}\n`
      }
      generateError.value = data.message || '生成失败'
      // 失败时弹出日志
      showOutputModal.value = true
    }
  } catch (e) {
    output.value += `❌ Error: ${e.message}\n`
    generateError.value = e.message
    // 错误时弹出日志
    showOutputModal.value = true
  }
  
  isGenerating.value = false
  scrollToBottom()
}

// 打开输出弹窗
const openOutputModal = () => {
  showOutputModal.value = true
}

// 关闭输出弹窗
const closeOutputModal = () => {
  showOutputModal.value = false
}

// 刷新预览
const refreshPreview = async () => {
  // 先检查文件是否存在
  try {
    const checkResponse = await fetch('/api/html?' + Date.now())
    if (!checkResponse.ok) {
      return  // 404，不做任何反应
    }
  } catch (e) {
    return  // 请求失败，不做任何反应
  }

  // 文件存在，刷新 iframe
  htmlUrl.value = ''
  setTimeout(() => {
    htmlUrl.value = '/api/html?' + Date.now()
    showToastMessage('刷新成功')
  }, 100)
}

// 截图并保存缩略图
const captureThumbnail = async () => {
  if (!iframeRef.value || isCapturing.value) return
  
  isCapturing.value = true
  captureError.value = ''
  
  try {
    // 获取 iframe 的 contentDocument
    const iframe = iframeRef.value
    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document
    
    if (!iframeDoc || !iframeDoc.body) {
      throw new Error('无法访问 iframe 内容，请确保页面已加载')
    }
    
    // 等待 iframe 内容完全加载
    await new Promise(resolve => setTimeout(resolve, 3000))
    
    // 动态注入 html2canvas 到 iframe 内部
    const script = document.createElement('script')
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'
    script.onload = async () => {
      try {
        // 获取 iframe 内容的实际尺寸
        const body = iframeDoc.body
        const scrollWidth = body.scrollWidth
        const scrollHeight = body.scrollHeight
        
        // 在 iframe 内部执行截图
        const iframeHtml2canvas = iframe.contentWindow.html2canvas
        const canvas = await iframeHtml2canvas(body, {
          useCORS: true,
          allowTaint: true,
          backgroundColor: '#ffffff',
          scale: 1,
          width: scrollWidth,
          height: scrollHeight,
          windowWidth: scrollWidth,
          scrollX: 0,
          scrollY: 0,
          x: 0,
          y: 0
        })
        
        // 转换为 blob 并上传
        canvas.toBlob(async (blob) => {
          const formData = new FormData()
          formData.append('thumbnail', blob, '.thumbnail.png')
          
          const res = await fetch('/api/projects/thumbnail', {
            method: 'POST',
            body: formData
          })
          
          if (res.ok) {
            output.value += `✅ 缩略图已保存！\n`
            showToastMessage('截图成功')
          } else {
            throw new Error('保存失败')
          }

          isCapturing.value = false
          scrollToBottom()
        }, 'image/png')
        
      } catch (e) {
        captureError.value = e.message
        output.value += `❌ 截图失败: ${e.message}\n`
        isCapturing.value = false
        scrollToBottom()
      }
    }
    script.onerror = () => {
      throw new Error('加载 html2canvas 失败')
    }
    iframeDoc.body.appendChild(script)
    
  } catch (e) {
    captureError.value = e.message
    output.value += `❌ 截图失败: ${e.message}\n`
    isCapturing.value = false
    scrollToBottom()
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (outputArea.value) {
      outputArea.value.scrollTop = outputArea.value.scrollHeight
    }
  })
}

// 复制项目提示词
const copyProjectPrompt = async (projectName, prompt) => {
  try {
    await navigator.clipboard.writeText(prompt || '')
    // 设置复制成功状态
    copiedProject.value = projectName
    // 1.5秒后清除状态
    setTimeout(() => {
      if (copiedProject.value === projectName) {
        copiedProject.value = null
      }
    }, 1500)
  } catch (e) {
    console.error('复制失败:', e)
  }
}

// 预览项目 HTML
const previewProject = async (projectName) => {
  try {
    // 先静默切换到该项目
    await fetch(`/api/projects/${projectName}/select`, { method: 'POST' })
    // 然后在新标签页打开
    window.open(`/api/html?${Date.now()}`, '_blank')
  } catch (e) {
    console.error('预览失败:', e)
  }
}

// 处理缩略图加载，计算宽高比
const onThumbnailLoad = (e, project) => {
  const img = e.target
  const { naturalWidth, naturalHeight } = img
  const ratio = naturalWidth / naturalHeight
  
  // 16:9 = 1.777...
  const isWide = ratio > 16 / 9
  
  // 缓存比例信息
  thumbnailRatios.value[project.name] = { 
    ratio, 
    isWide
  }
  
  // 隐藏占位符
  img.nextElementSibling.style.display = 'none'
}

// 缩略图加载失败（统一处理函数）
const onThumbnailError = (e) => {
  e.target.style.display = 'none'
  e.target.nextElementSibling.style.display = 'flex'
}

// 获取缩略图 URL
// 缩略图 URL 缓存（避免重复请求）
const thumbnailUrlCache = new Map()

const getThumbnailUrl = (project) => {
  // 从缓存获取固定 URL
  if (thumbnailUrlCache.has(project.name)) {
    return thumbnailUrlCache.get(project.name)
  }
  // 首次请求带时间戳获取最新图片
  const url = `/api/projects/${project.name}/thumbnail`
  thumbnailUrlCache.set(project.name, url)
  return url
}

// 获取缩略图样式
const getThumbnailStyle = (project) => {
  const ratioData = thumbnailRatios.value[project.name]
  if (!ratioData) return {}
  
  if (ratioData.isWide) {
    // 横长竖短（宽 > 高，比例 > 16:9）→ 居中显示
    return { objectPosition: 'center' }
  } else {
    // 横短竖长（比例 <= 16:9）→ 顶部对齐
    return { objectPosition: 'top center' }
  }
}

// 处理滚动事件
const handleScroll = () => {
  const container = terminalContentRef.value
  if (container) {
    isAtTop.value = container.scrollTop <= 10
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<template>
  <div class="terminal">
    <!-- 项目选择界面 -->
    <div v-if="showProjectSelector" class="project-selector">
      <div class="selector-scroll-container" ref="selectorScrollRef">
        <div class="selector-content">
          <div class="selector-header">
            <h2>一句话生成网页原型</h2>
            <p class="selector-subtitle">选择或新建项目，开始创作原型吧！</p>
          </div>
          
          <div class="project-list">
            <div 
              v-for="project in projectNames" 
              :key="project"
              class="project-item"
              @click="selectProject(project)"
            >
              <span class="icon-container">📁</span>
              <span class="project-name">{{ project }}</span>
              <button 
                class="delete-btn" 
                @click.stop="confirmDelete(project)"
                title="删除项目"
              >
                🗑️
              </button>
            </div>
          </div>
          
          <div v-if="projectNames.length === 0" class="no-projects">
            暂无可用项目
          </div>
          
          <div class="create-project">
            <h3>新建项目</h3>
            <div class="input-group">
              <input 
                v-model="newProjectName" 
                @keydown.enter="createProject"
                @input="onNameInput"
                placeholder="输入新项目名称..."
                :class="{ 'input-error': createError }"
              >
              <button @click="createProject">创建</button>
            </div>
            <p v-if="createError" class="error-message">{{ createError }}</p>
          </div>
        </div>
      </div>
      
      <!-- 删除确认对话框 -->
      <div v-if="showDeleteConfirm" class="modal-overlay">
        <div class="modal">
          <h3>确认删除</h3>
          <p>确定要删除项目 <strong>{{ projectToDelete }}</strong> 吗？此操作不可恢复。</p>
          <div class="modal-actions">
            <button class="cancel-btn" @click="cancelDelete">取消</button>
            <button class="confirm-delete-btn" @click="deleteProject">确认删除</button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 终端界面 -->
    <template v-else>
      <!-- 切换提示 Toast -->
      <Transition name="toast">
        <div v-if="showToast" class="toast-message">
          {{ toastMessage }}
        </div>
      </Transition>

      <!-- 页面内容区 -->
      <div class="terminal-content" ref="terminalContentRef" @scroll="handleScroll">
        <!-- 预览区域 -->
        <div class="preview-area" ref="previewRef">
          <!-- 有html时渲染预览 -->
          <template v-if="htmlUrl">
            <!-- 预览容器 -->
            <div class="preview-container" :class="{ 'capturing': isCapturing }">
              <iframe 
                ref="iframeRef"
                :src="htmlUrl" 
                class="preview-iframe" 
                title="原型展示"
              ></iframe>
            </div>
          </template>
          <!-- 没有html时显示友好提示 -->
          <div v-else class="empty-preview">
            <div class="empty-preview-content">
              <span class="empty-preview-icon">✨</span>
              <p>开始创作吧！</p>
            </div>
          </div>
        </div>
        
      <!-- 生成输入区域 -->
      <div class="generate-area" ref="generateAreaRef">
        <div class="generate-input-group">
          <span class="generate-icon">✨</span>
          <input 
            v-model="promptText" 
            @keydown.enter="generateWebpage"
            placeholder="描述你想要生成的网页..."
            :disabled="isGenerating"
            class="generate-input"
          >
          <button 
            @click="generateWebpage" 
            :disabled="isGenerating || !promptText.trim()"
            class="generate-btn"
          >
            <span v-if="!isGenerating">生 成</span>
            <span v-else class="loading-btn">
              <span class="loading-spinner"></span>
              生成中...
            </span>
          </button>
          <button 
            class="refresh-btn"
            @click="refreshPreview"
          >
            刷 新
          </button>
          <button 
            @click="openOutputModal"
            class="output-btn"
            title="查看日志"
          >
            日 志
          </button>
          <button 
            class="capture-btn"
            @click="captureThumbnail"
            :disabled="isCapturing"
          >
            <span v-if="!isCapturing">截 图</span>
            <span v-else>截图中...</span>
          </button>
          <button 
            class="exit-btn-red" 
            @click="exitProject" 
            title="退出当前项目"
            :disabled="isGenerating"
            :class="{ 'disabled': isGenerating }"
          >
            退 出
          </button>
        </div>
        <p v-if="generateError" class="error-message">{{ generateError }}</p>
      </div>
      
      <!-- 悬浮滚动按钮 -->
      <div class="scroll-float-btn" @click="toggleScroll">
        {{ isAtTop ? '更 多 项 目' : '当 前 项 目' }}
      </div>
      
      <!-- 项目卡片列表 -->
      <div class="projects-list-container" ref="projectsListRef">
        <div class="projects-list-content">
          <template v-if="allProjects.length > 0">
            <div class="projects-grid">
              <div
                v-for="project in allProjects"
                :key="project.name"
                class="project-card"
                :class="{ 'transitioning': transitioningProject === project.name }"
                @click="switchToProject(project.name)"
              >
                <!-- 缩略图 (16:9) -->
                <div class="project-card-thumbnail">
                  <img
                    v-if="project.has_html"
                    :src="getThumbnailUrl(project)"
                    alt="项目缩略图"
                    :style="getThumbnailStyle(project)"
                    @load="e => onThumbnailLoad(e, project)"
                    @error="onThumbnailError"
                  >
                  <div class="thumbnail-placeholder">
                    <span class="thumbnail-emoji">✨</span>
                  </div>
                  <!-- 按钮覆盖层（仅在有 index.html 时显示） -->
                  <div v-if="project.has_html" class="thumbnail-overlay">
                    <div class="thumbnail-buttons">
                      <button
                        class="thumbnail-btn preview-btn"
                        title="在新标签页打开"
                        @click.stop="previewProject(project.name)"
                      >
                        预览原型页
                      </button>
                      <button
                        class="thumbnail-btn copy-btn"
                        :class="{ 'copied': copiedProject === project.name }"
                        @click.stop="copyProjectPrompt(project.name, project.first_prompt)"
                        title="复制提示词"
                      >
                        复制提示词
                      </button>
                    </div>
                  </div>
                </div>
                <!-- 项目信息 -->
                <div class="project-card-info">
                  <div class="project-card-name">{{ project.name }}</div>
                  <div class="project-card-desc" :title="project.first_prompt || '暂无描述'">
                    {{ project.first_prompt || '暂无描述' }}
                  </div>
                  <div class="project-card-time">{{ project.first_prompt_time || project.created_time }}</div>
                </div>
              </div>
            </div>
            <!-- 分页 -->
            <div v-if="totalPages > 1" class="pagination">
              <button 
                class="pagination-btn"
                :disabled="currentPage <= 1"
                @click="goToPage(currentPage - 1)"
              >
                上一页
              </button>
              <span class="pagination-info">
                {{ currentPage }} / {{ totalPages }}
              </span>
              <button 
                class="pagination-btn"
                :disabled="currentPage >= totalPages"
                @click="goToPage(currentPage + 1)"
              >
                下一页
              </button>
            </div>
          </template>
          <template v-else>
            <div class="projects-empty">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="currentColor">
                <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
              </svg>
              <p>暂无其他项目</p>
            </div>
          </template>
        </div>
      </div>
      </div>
      
      <!-- 输出弹窗 -->
      <Teleport to="body">
        <div v-if="showOutputModal" class="output-modal-overlay" @click.self="closeOutputModal">
          <div class="output-modal">
            <div class="output-modal-header">
              <span>日志</span>
              <button class="output-modal-close" @click="closeOutputModal">×</button>
            </div>
            <div class="output-modal-tabs">
              <button 
                :class="{ 'active': !showHistoryTab }" 
                @click="showHistoryTab = false"
              >日志</button>
              <button 
                :class="{ 'active': showHistoryTab }" 
                @click="showHistoryTab = true"
              >
                历史记录
                <span v-if="promptHistory.length" class="history-count">{{ promptHistory.length }}</span>
              </button>
            </div>
            <div class="output-modal-content">
              <!-- 日志内容 -->
              <div v-if="!showHistoryTab" ref="outputArea">{{ output }}</div>
              <!-- 历史记录内容 -->
              <div v-else class="history-content">
                <div v-if="promptHistory.length === 0" class="no-history">
                  <p>暂无历史记录</p>
                </div>
                <div 
                  v-for="(item, index) in promptHistory" 
                  :key="index"
                  class="history-item"
                >
                  <span class="history-num">{{ index + 1 }}</span>
                  <span class="history-text">{{ item }}</span>
                </div>
              </div>
            </div>
            <div class="output-modal-footer">
              <button class="output-modal-confirm" @click="closeOutputModal">关闭</button>
            </div>
          </div>
        </div>
      </Teleport>
    </template>
  </div>
</template>

<style scoped>
.terminal {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.refresh-btn {
  padding: 10px 20px;
  border: 1px solid rgba(86, 156, 214, 0.5);
  border-radius: 30px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  background-color: rgba(86, 156, 214, 0.85);
  color: white;
  white-space: nowrap;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
}

.refresh-btn:hover {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

.capture-btn {
  padding: 10px 20px;
  border: 1px solid rgba(34, 197, 94, 0.5);
  border-radius: 30px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  background-color: rgba(34, 197, 94, 0.85);
  color: white;
  white-space: nowrap;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
}

.capture-btn:hover {
  background-color: rgba(34, 197, 94, 1);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.5);
  transform: translateY(-1px);
}

.capture-btn:hover:not(:disabled) {
  background-color: #1ea550;
}

.capture-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.preview-container {
  position: relative;
  flex: 1;
  overflow: hidden;
}

.preview-container.capturing {
  cursor: wait;
}

.preview-container.capturing .preview-iframe {
  pointer-events: none;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background-color: white;
}

/* 空预览状态 */
.empty-preview {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #1e1e1e;
}

.empty-preview-content {
  text-align: center;
  color: #808080;
}

.empty-preview-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
}

.empty-preview-content p {
  font-size: 18px;
  margin: 0;
}

/* 生成输入区域 */
.generate-area {
  height: 80px; /* 固定高度 */
  padding: 15px 20px;
  background-color: #252526;
  border-top: 1px solid #333;
  flex-shrink: 0; /* 防止压缩 */
}

/* 悬浮滚动按钮 */
.scroll-float-btn {
  position: fixed;
  right: 20px;
  bottom: 100px;
  padding: 10px 20px;
  background-color: rgba(94, 92, 92, 0.4);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 30px;
  color: #ffffff;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
  z-index: 1000;
}

.scroll-float-btn:hover {
  background-color: rgba(70, 70, 70, 0.8);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
}

.scroll-float-btn:active {
  transform: translateY(0);
}

.generate-input-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.generate-icon {
  font-size: 18px;
}

.generate-input {
  flex: 1;
  padding: 10px 15px;
  background-color: #2d2d30;
  border: 1px solid #333;
  border-radius: 4px;
  color: #d4d4d4;
  font-family: inherit;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.generate-input:focus {
  border-color: #569cd6;
}

.generate-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.generate-btn {
  padding: 10px 20px;
  background-color: rgba(86, 156, 214, 0.85);
  color: white;
  border: 1px solid rgba(86, 156, 214, 0.5);
  border-radius: 30px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  white-space: nowrap;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
}

.generate-btn:hover:not(:disabled) {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 输出按钮 */
.output-btn {
  padding: 10px 20px;
  background-color: rgba(86, 156, 214, 0.85);
  color: white;
  border: 1px solid rgba(86, 156, 214, 0.5);
  border-radius: 30px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  white-space: nowrap;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
}

.output-btn:hover {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

.loading-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.exit-btn-red {
  padding: 10px 20px;
  background-color: rgba(241, 76, 76, 0.85);
  color: white;
  border: 1px solid rgba(241, 76, 76, 0.5);
  border-radius: 30px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  white-space: nowrap;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(241, 76, 76, 0.3);
}

.exit-btn-red:hover:not(:disabled) {
  background-color: rgba(241, 76, 76, 1);
  box-shadow: 0 4px 12px rgba(241, 76, 76, 0.5);
  transform: translateY(-1px);
}

.exit-btn-red:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.output-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.output-modal {
  background-color: rgba(37, 37, 38, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  width: 80%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.output-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background-color: rgba(45, 45, 45, 0.8);
  border-radius: 12px 12px 0 0;
}

.output-modal-header span {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
}

.output-modal-close {
  background-color: rgba(86, 156, 214, 0.85);
  border: 1px solid rgba(86, 156, 214, 0.5);
  color: white;
  font-size: 20px;
  cursor: pointer;
  width: 32px;
  height: 32px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
}

.output-modal-close:hover {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

.output-modal-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 15px;
  line-height: 1.6;
  color: #d4d4d4;
}

.output-modal-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
  background-color: rgba(45, 45, 45, 0.8);
  border-radius: 0 0 12px 12px;
}

.output-modal-confirm {
  padding: 8px 24px;
  background-color: rgba(86, 156, 214, 0.85);
  color: white;
  border: 1px solid rgba(86, 156, 214, 0.5);
  border-radius: 18px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
}

.output-modal-confirm:hover {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

/* 标签页样式 */
.output-modal-tabs {
  display: flex;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background-color: rgba(45, 45, 45, 0.8);
}

.output-modal-tabs button {
  flex: 1;
  padding: 12px 16px;
  background: transparent;
  border: none;
  color: #808080;
  cursor: pointer;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  position: relative;
  transition: all 0.3s ease;
}

.output-modal-tabs button:hover {
  color: #d4d4d4;
  background-color: rgba(255, 255, 255, 0.05);
}

.output-modal-tabs button.active {
  color: #569cd6;
  background-color: rgba(37, 37, 38, 0.9);
  font-weight: bold;
}

.output-modal-tabs button .history-count {
  margin-left: 6px;
  padding: 2px 6px;
  background-color: #569cd6;
  color: white;
  border-radius: 10px;
  font-size: 11px;
}

.output-modal-tabs button.active .history-count {
  background-color: #4a8bc8;
}

/* 历史记录内容样式 */
.history-content {
  padding: 0;
  overflow-y: auto;
  max-height: 400px;
}

.no-history {
  padding: 40px 20px;
  text-align: center;
  color: #666;
}

.history-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 20px;
  border-bottom: 1px solid #3c3c3c;
  gap: 12px;
}

.history-item:hover {
  background-color: #2d2d2d;
}

.history-num {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  background-color: #569cd6;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 500;
}

.history-text {
  flex: 1;
  color: #d4d4d4;
  font-size: 15px;
  line-height: 1.5;
  word-break: break-all;
  white-space: pre-wrap;
}

/* 项目选择器样式 */
.project-selector {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background-color: #1e1e1e;
  position: relative;
  padding-top: 40px;
}

/* 项目选择器滚动容器 */
.selector-scroll-container {
  max-height: calc(100vh - 60px);
  overflow-y: auto;
  display: flex;
  justify-content: center;
  width: 100%;
}

/* 自定义滚动条 */
.selector-scroll-container::-webkit-scrollbar {
  width: 8px;
}

.selector-scroll-container::-webkit-scrollbar-track {
  background: #1e1e1e;
  border-radius: 4px;
}

.selector-scroll-container::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.selector-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.selector-content {
  width: 1000px;
  max-width: 95vw;
  padding: 30px;
  background-color: #252526;
  border-radius: 18px;
  border: 1px solid #333;
  display: flex;
  flex-direction: column;
}

.selector-header {
  margin-bottom: 25px;
  text-align: center;
}

.selector-header h2 {
  color: #569cd6;
  margin-bottom: 10px;
  font-size: 24px;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", sans-serif;
  font-weight: bold;
}

.selector-subtitle {
  color: #569cd6;
  font-size: 16px;
  margin: 0;
  font-family: "Microsoft YaHei", sans-serif;
  font-weight: bold;
}

.selector-content h3 {
  color: #d4d4d4;
  margin: 20px 0 15px;
  font-size: 15px;
}

/* 项目列表 - 网格布局 */
.project-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 8px;
}

/* 自定义滚动条 */
.project-list::-webkit-scrollbar {
  width: 8px;
}

.project-list::-webkit-scrollbar-track {
  background: #1e1e1e;
  border-radius: 4px;
}

.project-list::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.project-list::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 项目卡片 */
.project-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  padding: 20px 15px;
  background-color: #2d2d30;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid transparent;
  position: relative;
  min-height: 120px;
}

.project-item:hover {
  background-color: #353538;
  border-color: rgba(86, 156, 214, 0.3);
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

/* 图标容器 */
.project-item .icon-container {
  flex-shrink: 0;
  margin-right: 12px;
  font-size: 20px;
}

/* 项目名称 */
.project-item .project-name {
  flex: 1;
  font-size: 16px;
  color: #d4d4d4;
  font-weight: 500;
  text-align: center;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  box-orient: vertical;
  overflow: hidden;
  padding-right: 24px; /* 为删除按钮留空间 */
}

.project-item .delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.2s;
  border-radius: 4px;
}

.project-item:hover .delete-btn {
  opacity: 0.6;
}

.project-item .delete-btn:hover {
  opacity: 1;
  background-color: rgba(241, 76, 76, 0.2);
}

.no-projects {
  grid-column: 1 / -1;
  padding: 40px 20px;
  text-align: center;
  color: #666;
  font-size: 16px;
}

.create-project {
  margin-top: 25px;
  padding-top: 25px;
  border-top: 1px solid #333;
}

.create-project h3 {
  margin-bottom: 15px;
  color: #d4d4d4;
  font-size: 16px;
  text-align: center;
}

.create-project .input-group {
  display: flex;
  gap: 12px;
  max-width: 500px;
  margin: 0 auto;
}

.create-project input {
  flex: 1;
  padding: 12px 16px;
  background-color: #2d2d30;
  border: 1px solid #333;
  border-radius: 8px;
  color: #d4d4d4;
  outline: none;
  font-size: 15px;
}

.create-project input:focus {
  border-color: #569cd6;
}

.create-project input.input-error {
  border-color: #f14c4c;
}

.error-message {
  color: #f14c4c;
  font-size: 12px;
  margin-top: 8px;
  text-align: center;
}

.create-project button {
  padding: 12px 28px;
  background-color: rgba(86, 156, 214, 0.85);
  color: white;
  border: 1px solid rgba(86, 156, 214, 0.5);
  border-radius: 20px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(86, 156, 214, 0.3);
  white-space: nowrap;
}

.create-project button:hover {
  background-color: rgba(86, 156, 214, 1);
  box-shadow: 0 4px 12px rgba(86, 156, 214, 0.5);
  transform: translateY(-1px);
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  width: 350px;
  padding: 25px;
  background-color: rgba(37, 37, 38, 0.95);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.modal h3 {
  color: #f14c4c;
  margin-bottom: 15px;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-weight: bold;
}

.modal p {
  color: #d4d4d4;
  margin-bottom: 20px;
  line-height: 1.6;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
}

.modal p strong {
  color: #569cd6;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-weight: bold;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.modal-actions button {
  padding: 8px 16px;
  border-radius: 18px;
  cursor: pointer;
  font-family: "Microsoft YaHei Bold", "Microsoft YaHei", "SimHei", sans-serif;
  font-weight: bold;
  border: 1px solid;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.cancel-btn {
  background-color: rgba(58, 61, 65, 0.85);
  color: #d4d4d4;
  border-color: rgba(58, 61, 65, 0.5);
}

.cancel-btn:hover {
  background-color: rgba(74, 77, 82, 0.95);
  box-shadow: 0 4px 12px rgba(74, 77, 82, 0.4);
  transform: translateY(-1px);
}

.confirm-delete-btn {
  background-color: rgba(241, 76, 76, 0.85);
  color: white;
  border-color: rgba(241, 76, 76, 0.5);
}

.confirm-delete-btn:hover {
  background-color: rgba(241, 76, 76, 1);
  box-shadow: 0 4px 12px rgba(241, 76, 76, 0.5);
  transform: translateY(-1px);
}

/* 页面容器 - 垂直排列 */
.terminal-content {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 隐藏滚动条但保留滚动功能 */
.terminal-content::-webkit-scrollbar {
  display: none;
}

/* 预览区域 */
.preview-area {
  min-height: 90vh;
  display: flex;
  flex-direction: column;
  background-color: #1e1e1e;
  overflow: hidden;
  position: relative;
}

/* 项目卡片列表容器 */
.projects-list-container {
  flex: none;
  min-height: 90vh;
  background-color: #252526;
  border-top: 1px solid #333;
  display: flex;
  flex-direction: column;
}

.projects-list-content {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

/* 项目卡片网格 */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(280px, 500px));
  justify-content: center;
  gap: 12px;
}

/* 项目卡片 - 垂直布局 */
.project-card {
  background-color: #2d2d30;
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.project-card:hover {
  background-color: #353538;
  border-color: rgba(86, 156, 214, 0.3);
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
}

/* 切换提示 Toast */
.toast-message {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(45, 45, 48, 0.95);
  color: #d4d4d4;
  padding: 12px 24px;
  border-radius: 18px;
  font-size: 15px;
  z-index: 9999;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(86, 156, 214, 0.3);
}

/* Toast 过渡动画 */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

/* 项目卡片切换过渡动画 */
.project-card.transitioning {
  animation: cardExit 0.5s ease forwards;
}

@keyframes cardExit {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(0.85);
    opacity: 0;
  }
}

/* 缩略图容器 - 16:9 */
.project-card-thumbnail {
  position: relative;
  width: calc(100% - 8px);
  aspect-ratio: 16 / 9;
  border-radius: 16px;
  overflow: hidden;
  background-color: #1e1e1e;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 4px auto 0;
}

.project-card-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 默认缩略图占位符 */
.thumbnail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: #1e1e1e;
  color: #569cd6;
}

.thumbnail-emoji {
  font-size: 60px;
  line-height: 1;
}

/* 缩略图按钮覆盖层 */
.thumbnail-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.project-card-thumbnail:hover .thumbnail-overlay {
  opacity: 1;
}

.thumbnail-buttons {
  display: flex;
  gap: 8px;
}

.thumbnail-btn {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 15px;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
}

/* 预览按钮 - 蓝色白字 */
.preview-btn {
  background-color: #007AFF;
  color: white;
}

.preview-btn:hover {
  background-color: #0056b3;
}

/* 复制按钮 - 白字黑底 */
.copy-btn {
  background-color: white;
  color: #1d1d1f;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.copy-btn:hover {
  background-color: #f5f5f7;
}

/* 已复制状态按钮 */
.copy-btn.copied {
  background-color: #34c759;
  color: white;
}

/* 项目信息 */
.project-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  gap: 2px;
}

.project-card-name {
  color: #d4d4d4;
  font-size: 20px;
  font-weight: bold;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-card-desc {
  color: #b0b0b0;
  font-size: 15px;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  line-height: 1.4;
  min-height: 42px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  box-orient: vertical;
  flex: 1;
  margin-top: 2px;
}

.project-card-time {
  color: #808080;
  font-size: 13px;
  margin-top: 2px;
}

/* 分页样式 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 10px 0;
  margin-top: auto;
}

.pagination-btn {
  padding: 8px 20px;
  background-color: #3a3d41;
  color: #d4d4d4;
  border: 1px solid #4a4d52;
  border-radius: 6px;
  cursor: pointer;
  font-size: 15px;
  transition: all 0.2s ease;
}

.pagination-btn:hover:not(:disabled) {
  background-color: #4a4d52;
  border-color: #569cd6;
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  color: #b0b0b0;
  font-size: 15px;
}

/* 空状态 */
.projects-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #666;
}

.projects-empty svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.projects-empty p {
  font-size: 15px;
}

/* 项目选择器悬浮按钮 */
.selector-float-btn {
  position: fixed;
  right: 30px;
  bottom: 100px;
  padding: 10px 24px;
  background-color: rgba(86, 156, 214, 0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 20px;
  color: #ffffff;
  font-family: "Microsoft YaHei", "SimHei", sans-serif;
  font-size: 15px;
  font-weight: bold;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 15px rgba(86, 156, 214, 0.4);
  transition: all 0.3s ease;
  z-index: 1000;
}
</style>
