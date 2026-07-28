import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export function useReferenceData() {
  const [documentTypes, setDocumentTypes] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [enumOptions, setEnumOptions] = useState({
    domains: [],
    audiences: [],
    ocr_statuses: [],
    review_statuses: [],
    rag_statuses: [],
  });

  useEffect(() => {
    Promise.all([api.getDocumentTypes(), api.getDepartments(), api.getEnumOptions()])
      .then(([types, depts, enums]) => {
        setDocumentTypes(types);
        setDepartments(depts);
        setEnumOptions(enums);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return { documentTypes, departments, enumOptions, loading };
}
