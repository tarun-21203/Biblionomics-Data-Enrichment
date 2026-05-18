import { useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import { getConfig, saveConfig } from "../services/config";

interface Props {
    open: boolean;
    onClose: () => void;
}

export default function SetEndpointModal({ open, onClose }: Props) {
    const current = getConfig();
    const [apiUrl, setApiUrl] = useState(current.apiUrl);
    const [apiKey, setApiKey] = useState(current.apiKey);

    function handleSave() {
        saveConfig({ apiUrl: apiUrl.trim(), apiKey: apiKey.trim() });
        onClose();
        window.location.reload();
    }

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>API Endpoint Settings</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{ mt: 1 }}>
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
                        type="password"
                        fullWidth
                    />
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button
                    onClick={handleSave}
                    variant="contained"
                    disabled={!apiUrl.trim() || !apiKey.trim()}
                >
                    Save & Reload
                </Button>
            </DialogActions>
        </Dialog>
    );
}