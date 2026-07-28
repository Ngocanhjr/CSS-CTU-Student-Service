import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export function useReferenceData() {
  const [documentTypes, setDocumentTypes] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)

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
      .catch(() => setLoading(false))
  }, [])

  return { documentTypes, departments, loading }
}
