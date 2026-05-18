import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import { postJobBegin } from "../services/api";

export default function Submit() {
    const navigate = useNavigate();
    const fileInput = useRef<HTMLInputElement>(null);
    const [identifier, setIdentifier] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [requestId, setRequestId] = useState("");

    async function handleSubmit() {
        if (!file) return;
        setLoading(true);
        setError("");
        try {
            const res = await postJobBegin(identifier.trim(), file);
            setRequestId(res.requestId);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Submission failed");
        } finally {
            setLoading(false);
        }
    }

    if (requestId) {
        return (
            <Box sx={{ maxWidth: 520, mx: "auto", textAlign: "center", mt: 8 }}>
                <CheckCircleOutlineIcon color="success" sx={{ fontSize: 64, mb: 2 }} />
                <Typography variant="h5" fontWeight={700} gutterBottom>
                    Submitted Successfully
                </Typography>
                <Typography color="text.secondary" gutterBottom>
                    Your enrichment request has been queued.
                </Typography>
                <Button
                    variant="contained"
                    sx={{ mt: 3 }}
                    onClick={() => navigate(`/enrichment/${requestId}`)}
                >
                    View Status
                </Button>
            </Box>
        );
    }

    return (
        <Box sx={{ maxWidth: 520, mx: "auto" }}>
            <Button
                startIcon={<ArrowBackIcon />}
                onClick={() => navigate("/")}
                sx={{ mb: 3 }}
            >
                Back to Dashboard
            </Button>

            <Typography variant="h5" fontWeight={700} gutterBottom>
                New Enrichment Request
            </Typography>

            <Paper variant="outlined" sx={{ p: 3, mt: 2 }}>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    <TextField
                        label="Identifier (optional)"
                        placeholder="e.g. Q1 2026 Book List"
                        value={identifier}
                        onChange={(e) => setIdentifier(e.target.value)}
                        fullWidth
                    />

                    <Box>
                        <input
                            ref={fileInput}
                            type="file"
                            accept=".csv"
                            style={{ display: "none" }}
                            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                        />
                        <Button
                            variant="outlined"
                            startIcon={<UploadFileIcon />}
                            onClick={() => fileInput.current?.click()}
                            fullWidth
                            sx={{ py: 1.5 }}
                        >
                            {file ? file.name : "Choose CSV File"}
                        </Button>
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                            CSV must have an ISBN header with one ISBN per row
                        </Typography>
                    </Box>

                    {error && <Alert severity="error">{error}</Alert>}

                    <Button
                        variant="contained"
                        size="large"
                        disabled={!file || loading}
                        onClick={handleSubmit}
                        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
                    >
                        {loading ? "Submitting…" : "Submit"}
                    </Button>
                </Box>
            </Paper>
        </Box>
    );
}