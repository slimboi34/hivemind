/**
 * Temporary store for the files and requirement waiting to be uploaded
 * Lets the home page navigate straight away when the engine is started; the API calls then happen on the Process route (MainView)
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
