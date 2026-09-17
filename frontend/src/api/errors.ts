export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const LOGIN_URL = `/admin/login/?next=${encodeURIComponent('/')}`
