import service from './index'

/**
 * Whether God's Eye View is reachable, its version and usable tools
 */
export const getGodsEyeStatus = () => {
  return service.get('/api/godseye/status', { timeout: 15000 })
}

/**
 * Build a markdown situation brief for an area
 * @param {Object} data - { area, sections? }
 */
export const getGodsEyeBrief = (data) => {
  return service.post('/api/godseye/brief', data, { timeout: 120000 })
}
