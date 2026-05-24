import { useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import { getConfig, saveConfig } from "../services/config";
import { getBiblioToken, getGoogleApiKey, setTokens } from "../services/api";
import InputAdornment from "@mui/material/InputAdornment";

interface Props {
    open: boolean;
    onClose: () => void;
}

export default function SetEndpointModal({ open, onClose }: Props) {
    const current = getConfig();
    const [apiUrl, setApiUrl] = useState(current.apiUrl);
    const [apiKey, setApiKey] = useState(current.apiKey);
    const [biblionomicsApiKey, setBiblioApiKeyState] = useState(current.biblioToken);
    const [googleApiKey, setGoogleApiKeyState] = useState(current.googleApiKey);
    const [saving, setSaving] = useState(false);
    const [fetching, setFetching] = useState(false);
    const [fetchingGoogle, setFetchingGoogle] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleGetToken() {
        setFetching(true);
        setError(null);
        try {
            const res = await getBiblioToken();
            setBiblioApiKeyState(res.biblionomicsApiKey);
        } catch (e) {
            setError("Unable to fetch token: " + (e instanceof Error ? e.message : String(e)));
        }
        setFetching(false);
    }

    async function handleGetGoogleApiKey() {
        setFetchingGoogle(true);
        setError(null);
        try {
            const res = await getGoogleApiKey();
            setGoogleApiKeyState(res.key);
        } catch (e) {
            setError("Unable to fetch Google API key: " + (e instanceof Error ? e.message : String(e)));
        }
        setFetchingGoogle(false);
    }

    async function handleSave() {
        setSaving(true);
        setError(null);
        saveConfig({ apiUrl: apiUrl.trim(), apiKey: apiKey.trim(), biblioToken: biblionomicsApiKey.trim(), googleApiKey: googleApiKey.trim() });
        if (biblionomicsApiKey.trim() || googleApiKey.trim()) {
            try {
                await setTokens(biblionomicsApiKey.trim() || undefined, googleApiKey.trim() || undefined);
            } catch (e) {
                setError("Unable to save config: " + (e instanceof Error ? e.message : String(e)));
                setSaving(false);
                return;
            }
        }
        onClose();
        window.location.reload();
    }

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>API Endpoint Settings</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{ mt: 1 }}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <TextField
                        label="API URL"
                        value={apiUrl}
                        onChange={(e) => setApiUrl(e.target.value)}
                        placeholder="https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev"
                        fullWidth
                    />
                    <TextField
                        label="API Key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        fullWidth
                    />
                    <TextField
                        label="Biblionomics API Key"
                        value={biblionomicsApiKey}
                        onChange={(e) => setBiblioApiKeyState(e.target.value)}
                        fullWidth
                        helperText="Leave blank to keep the existing key unchanged."
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Button
                                        size="small"
                                        onClick={handleGetToken}
                                        disabled={fetching || saving}
                                    >
                                        {fetching ? <CircularProgress size={14} /> : "Get Key on Cloud"}
                                    </Button>
                                </InputAdornment>
                            ),
                        }}
                    />
                    <TextField
                        label="Google Books API Key"
                        value={googleApiKey}
                        onChange={(e) => setGoogleApiKeyState(e.target.value)}
                        fullWidth
                        helperText="Leave blank to keep the existing key unchanged."
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Button
                                        size="small"
                                        onClick={handleGetGoogleApiKey}
                                        disabled={fetchingGoogle || saving}
                                    >
                                        {fetchingGoogle ? <CircularProgress size={14} /> : "Get Key on Cloud"}
                                    </Button>
                                </InputAdornment>
                            ),
                        }}
                    />
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button
                    onClick={handleSave}
                    variant="contained"
                    disabled={!apiUrl.trim() || !apiKey.trim() || saving}
                    startIcon={saving ? <CircularProgress size={16} color="inherit" /> : null}
                >
                    Save & Reload
                </Button>
            </DialogActions>
        </Dialog>
    );
}