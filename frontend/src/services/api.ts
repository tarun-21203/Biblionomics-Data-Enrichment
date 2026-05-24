import { getConfig } from "./config";

const headers = () => ({
    "Content-Type": "application/json",
    "x-api-key": getConfig().apiKey,
});

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${getConfig().apiUrl}${path}`, {
        ...init,
        headers: { ...headers(), ...init?.headers },
    });
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
        throw new Error(
            `Invalid API URL — got HTML instead of JSON (HTTP ${res.status}). Check your endpoint settings.`,
        );
    }
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
    csvFile: File,
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
    status?: string,
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

export function generateDownload(
    id: string,
): Promise<GenerateDownloadResponse> {
    return request(`/jobs/generate-download?id=${encodeURIComponent(id)}`);
}

export function jobRedo(
    requestId: string,
): Promise<{ requestId: string; status: string; message: string }> {
    return request("/jobs/redo", {
        method: "POST",
        body: JSON.stringify({ requestId }),
    });
}

export function jobDelete(requestId: string): Promise<{ message: string }> {
    return request(`/jobs/delete?id=${encodeURIComponent(requestId)}`, {
        method: "DELETE",
    });
}

export function getBiblioToken(): Promise<{ token: string }> {
    return request("/biblionomics-token");
}

export function setBiblioToken(token: string): Promise<{ message: string }> {
    return request("/biblionomics-token", {
        method: "POST",
        body: JSON.stringify({ token }),
    });
}

export function getGoogleApiKey(): Promise<{ key: string }> {
    return request("/google-api-key");
}

export function setGoogleApiKey(key: string): Promise<{ message: string }> {
    return request("/google-api-key", {
        method: "POST",
        body: JSON.stringify({ key }),
    });
}