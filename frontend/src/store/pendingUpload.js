/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  seedText: '',
  isPending: false
})

// Files and pasted text are both optional: a run can start from the question alone.
export function setPendingUpload(files, requirement, seedText = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.seedText = seedText
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    seedText: state.seedText,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.seedText = ''
  state.isPending = false
}

export default state
