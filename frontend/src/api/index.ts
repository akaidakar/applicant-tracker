// The pages import from here. Splitting the client into its own module keeps
// fetch details (CSRF header, error shape) out of the components.
export { ApiError, LOGIN_URL } from './errors'
export { addNote, changeStage, getApplication, listApplications } from './http'
