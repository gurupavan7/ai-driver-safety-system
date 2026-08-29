import axios from "axios";

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const API = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export const getHealth = () => API.get("/health");
export const getStatus = () => API.get("/status");
export const getRisk = () => API.get("/risk");
export const getEvents = (limit = 20) => API.get(`/events?limit=${limit}`);
export const getAnalytics = (limit = 300) =>
  API.get(`/analytics?limit=${limit}`);
export const getHistory = (limit = 300) =>
  API.get(`/history?limit=${limit}`);

export const analyzeVideo = (file, onUploadProgress) => {
  const formData = new FormData();
  formData.append("file", file);

  return API.post("/video/analyze", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    timeout: 0,
    onUploadProgress,
  });
};

export const downloadSessionReport = () =>
  API.get("/reports/session", {
    responseType: "blob",
    timeout: 0,
  });

export const downloadVideoReport = (analysis) =>
  API.post("/reports/video", analysis, {
    responseType: "blob",
    timeout: 0,
  });

export const saveBlobAsFile = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  URL.revokeObjectURL(url);
};

export default API;
