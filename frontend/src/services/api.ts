const API_BASE = import.meta.env.VITE_API_URL as string;
const API_KEY = import.meta.env.VITE_API_KEY as string;

const headers = () => ({
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
});

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { ...headers(), ...init?.headers },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
    return data as T;
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface EnrichmentNote {
    timestamp: string;
    type: "info" | "warning" | "error";
    message: string;
}

export interface EnrichmentRequest {
    requestId: string;
    identifier: string;
    status: "pending" | "processing" | "completed" | "failed";
    totalIsbns: number;
    processedIsbns: number;
    enrichmentProgress: number;
    createdAt: number;
    updatedAt: number;
    notes: EnrichmentNote[];
    inputS3Key?: string;
    outputS3Key?: string;
    inputPresignedUrl?: string;
    inputPresignedUrlExpiry?: number;
    outputPresignedUrl?: string;
    outputPresignedUrlExpiry?: number;
}

export interface GenerateDownloadResponse {
    inputPresignedUrl: string | null;
    inputPresignedUrlExpiry: number | null;
    outputPresignedUrl: string | null;
    outputPresignedUrlExpiry: number | null;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export function postJobBegin(
    identifier: string,
    csvFile: File
): Promise<{ requestId: string; status: string; message: string }> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = async () => {
            const base64 = (reader.result as string).split(",")[1];
            try {
                const result = await request<{
                    requestId: string;
                    status: string;
                    message: string;
                }>("/jobs/begin", {
                    method: "POST",
                    body: JSON.stringify({ identifier, csvFile: base64 }),
                });
                resolve(result);
            } catch (e) {
                reject(e);
            }
        };
        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsDataURL(csvFile);
    });
}

export function getStatusAll(
    filter?: string,
    status?: string
): Promise<{ requests: EnrichmentRequest[] }> {
    const params = new URLSearchParams();
    if (filter) params.set("filter", filter);
    if (status) params.set("status", status);
    const qs = params.toString();
    return request(`/jobs/status${qs ? `?${qs}` : ""}`);
}

export function getStatusSingle(id: string): Promise<EnrichmentRequest> {
    return request(`/jobs/status?id=${encodeURIComponent(id)}`);
}

export function generateDownload(id: string): Promise<GenerateDownloadResponse> {
    return request(`/jobs/generate-download?id=${encodeURIComponent(id)}`);
}