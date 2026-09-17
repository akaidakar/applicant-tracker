// The pages import from here and never know which client they got.
// VITE_DEMO=1 (the GitHub Pages build) swaps Django for an in-browser copy.
import * as demo from './demo'
import * as http from './http'

export { ApiError, LOGIN_URL } from './errors'

export const DEMO = import.meta.env.VITE_DEMO === '1'

const client = DEMO ? demo : http

export const listApplications = client.listApplications
export const getApplication = client.getApplication
export const addNote = client.addNote
export const changeStage = client.changeStage
export const resetDemo = demo.reset
