import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
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

export default API;
