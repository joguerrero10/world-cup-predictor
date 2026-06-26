import axios from "axios"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export const client = axios.create({
  baseURL: API_URL,
  timeout: 120_000,
  headers: { "Content-Type": "application/json" },
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.detail ??
      err.response?.data?.message ??
      err.message ??
      "Error de red"
    return Promise.reject(new Error(String(msg)))
  }
)
