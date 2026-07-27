import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export function useReferenceData() {
  const [documentTypes, setDocumentTypes] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.getDocumentTypes(),
      api.getDepartments(),
    ])
      .then(([types, depts]) => {
        setDocumentTypes(types)
        setDepartments(depts)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return { documentTypes, departments, loading, error }
}
