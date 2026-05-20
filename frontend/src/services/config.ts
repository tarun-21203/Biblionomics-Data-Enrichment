const STORAGE_KEY = "biblionomics_config";

export interface AppConfig {
    apiUrl: string;
    apiKey: string;
    biblioToken: string;
}

export function getConfig(): AppConfig {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return JSON.parse(stored);
    } catch { }
    return {
        apiUrl: import.meta.env.VITE_API_URL ?? "",
        apiKey: import.meta.env.VITE_API_KEY ?? "",
        biblioToken: "",
    };
}

export function saveConfig(config: AppConfig): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function isConfigured(): boolean {
    const { apiUrl, apiKey } = getConfig();
    return apiUrl.length > 0 && apiKey.length > 0;
}