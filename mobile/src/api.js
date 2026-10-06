import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'propkeep_token';
const API_KEY = 'propkeep_api';

/** Live PropKeep backend (PythonAnywhere). Override on login if needed. */
export const DEFAULT_API_URL = (
  Constants.expoConfig?.extra?.apiUrl || 'https://narenthar.pythonanywhere.com'
).replace(/\/$/, '');

export async function getApiUrl() {
  const saved = await SecureStore.getItemAsync(API_KEY);
  if (saved) return saved.replace(/\/$/, '');
  return DEFAULT_API_URL;
}

export async function setApiUrl(url) {
  await SecureStore.setItemAsync(API_KEY, (url || '').trim().replace(/\/$/, ''));
}

export async function getToken() {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token) {
  if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}

async function request(path, { method = 'GET', body, token } = {}) {
  const base = await getApiUrl();
  const headers = { 'Content-Type': 'application/json' };
  const auth = token || (await getToken());
  if (auth) headers.Authorization = `Token ${auth}`;
  const res = await fetch(`${base}/api/mobile${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text || 'Invalid response' };
  }
  if (!res.ok) {
    const detail =
      (data && (data.detail || JSON.stringify(data))) || `Request failed (${res.status})`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  login: (username, password) => request('/auth/login/', { method: 'POST', body: { username, password } }),
  logout: () => request('/auth/logout/', { method: 'POST' }),
  me: () => request('/auth/me/'),
  options: () => request('/options/'),
  listings: (q = '') => request(`/listings/${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  listing: (id) => request(`/listings/${id}/`),
  enquire: (id, body) => request(`/listings/${id}/`, { method: 'POST', body }),
  joinListing: (id, message) =>
    request(`/listings/${id}/`, { method: 'POST', body: { action: 'join', message } }),
  dashboard: () => request('/dashboard/'),
  properties: () => request('/properties/'),
  createProperty: (body) => request('/properties/', { method: 'POST', body }),
  property: (id) => request(`/properties/${id}/`),
  updateProperty: (id, body) => request(`/properties/${id}/`, { method: 'PATCH', body }),
  vacate: (id, planned_vacate_date) =>
    request(`/properties/${id}/vacate/`, { method: 'POST', body: { planned_vacate_date } }),
  tenants: () => request('/tenants/'),
  createTenant: (body) => request('/tenants/', { method: 'POST', body }),
  updateTenant: (id, body) => request(`/tenants/${id}/`, { method: 'PATCH', body }),
  createTenantLogin: (id, body) => request(`/tenants/${id}/login/`, { method: 'POST', body }),
  reviewJoin: (id, action) => request(`/join-requests/${id}/`, { method: 'POST', body: { action } }),
  payments: () => request('/payments/'),
  createPayment: (body) => request('/payments/', { method: 'POST', body }),
  inbox: () => request('/inbox/'),
  markInbox: () => request('/inbox/', { method: 'POST', body: { mark_all: true } }),
  remind: (tenant_ids, message) =>
    request('/rent-reminder/', { method: 'POST', body: { tenant_ids, message } }),
  portal: () => request('/tenant-portal/'),
  enquiries: () => request('/enquiries/'),
  buildings: () => request('/buildings/'),
  broadcast: (body) => request('/broadcast/', { method: 'POST', body }),
};
