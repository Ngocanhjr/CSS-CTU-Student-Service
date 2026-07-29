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
    validity_statuses: [],
    rag_statuses: [],
    asset_types: [],
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
