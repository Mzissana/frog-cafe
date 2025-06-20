import axios from "axios";

const API_BASE_URL = "https://frog-cafe-production.up.railway.app/";
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  maxRedirects: 0,
});

api.interceptors.request.use((config) => {
  console.log("Request interceptor called");
  const token = localStorage.getItem("token");

  if (token) {
    console.log("Token found in localStorage");
    console.log("Adding token to request:", token.substring(0, 10) + "...");
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    console.log("No token found in localStorage");
  }

  console.log("Request config:", {
    url: config.url,
    method: config.method,
    headers: config.headers,
  });

  return config;
});

api.interceptors.response.use(
  (response) => {
    console.log("Response received:", {
      status: response.status,
      url: response.config.url,
    });
    return response;
  },
  async (error) => {
    console.error("API Error:", {
      status: error.response?.status,
      url: error.config?.url,
      message: error.response?.data?.detail || error.message,
    });
    const { config, response } = error;

    if (response && (response.status === 301 || response.status === 302)) {
      const newUrl = response.headers.location;
      return api.request({
        ...config,
        url: newUrl,
      });
    }

    return Promise.reject(error);
  }
);

// Auth endpoints
export const login = ({ username, password }) =>
  api.post("/api/auth/login", {
    username,
    password,
  });

// Menu endpoints
export const getMenu = () => api.get("/api/menu/");
export const createMenuItem = (data) => api.post("/api/menu", data);
export const updateMenuItem = (id, data) => api.put(`/api/menu/${id}`, data);
export const deleteMenuItem = (id) => api.delete(`/api/menu/${id}`);

// Cart endpoints
export const getCart = (orderId) => api.get(`/api/cart/${orderId}`);
export const addToCart = (orderId, menuItems) =>
  api.post(`/api/cart/${orderId}`, { menu_items: menuItems });
export const removeFromCart = (orderId, menuItemId) =>
  api.delete(`/api/cart/${orderId}/${menuItemId}`);

// Orders endpoints
export const createOrder = (data) => api.post("/api/orders/", data);
export const getOrders = () => api.get("/api/orders/");
export const updateOrderStatus = (id, status) =>
  api.put(`/api/orders/${id}/status`, { status_id: status });
export const deleteOrder = (id) => api.delete(`/api/orders/${id}`);
export const clearOrders = () => api.delete("/api/orders/");

// Toads endpoints
export const getToads = () => api.get("/api/toads");
export const updateToadStatus = (id, isTaken) =>
  api.put(`/api/toads/${id}`, { is_taken: isTaken });

// TV Display endpoints
export const getDisplayData = () => api.get("/api/tv/orders");
export const getTVOrders = () => api.get("/api/tv/orders");

export default api;
