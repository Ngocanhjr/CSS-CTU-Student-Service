import { toast } from 'react-toastify'

const options = { autoClose: 4500, closeButton: true }

export const notify = {
  success: (message) => toast.success(message, options),
  error: (message) => toast.error(message, options),
  info: (message) => toast.info(message, options),
  warning: (message) => toast.warning(message, options),
}
