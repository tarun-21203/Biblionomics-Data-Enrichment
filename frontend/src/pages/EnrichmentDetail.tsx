import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import LinearProgress from "@mui/material/LinearProgress";
import Paper from "@mui/material/Paper";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import StatusBadge from "../components/StatusBadge";
import {
    getStatusSingle,
    generateDownload,
    EnrichmentRequest,
    EnrichmentNote,
} from "../services/api";

const POLL_INTERVAL = 5_000;
const URL_MIN_TTL = 60; // seconds

function isUrlValid(expiry?: number): boolean {
    if (!expiry) return false;
    return expiry > Math.floor(Date.now() / 1000) + URL_MIN_TTL;
}

const noteColor: Record<string, "info" | "warning" | "error"> = {
    info: "info",
    warning: "warning",
    error: "error",
};

export default function EnrichmentDetail() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    const [item, setItem] = useState<EnrichmentRequest | null>(null);
    const [inputUrl, setInputUrl] = useState<string | null>(null);
    const [outputUrl, setOutputUrl] = useState<string | null>(null);
    const [csvRows, setCsvRows] = useState<string[][]>([]);
    const [outputCsvRows, setOutputCsvRows] = useState<string[][]>([]);
    const [error, setError] = useState("");
    const [loadingCsv, setLoadingCsv] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const resolveUrls = useCallback(
        async (req: EnrichmentRequest) => {
            let iUrl = isUrlValid(req.inputPresignedUrlExpiry) ? req.inputPresignedUrl ?? null : null;
            let oUrl =
                req.status === "completed" && isUrlValid(req.outputPresignedUrlExpiry)
                    ? req.outputPresignedUrl ?? null
                    : null;

            const needsInput = !iUrl;
            const needsOutput = req.status === "completed" && !oUrl;

            if (needsInput || needsOutput) {
                try {
                    const dl = await generateDownload(id!);
                    if (needsInput) iUrl = dl.inputPresignedUrl;
                    if (needsOutput) oUrl = dl.outputPresignedUrl;
                } catch {
                    // non-fatal; downloads may just be unavailable
                }
            }

            setInputUrl(iUrl);
            setOutputUrl(oUrl);
            return iUrl;
        },
        [id]
    );

    const parseCsv = (text: string) =>
        text.trim().split("\n").map((line) => line.split(",").map((c) => c.trim()));

    const fetchCsv = useCallback(async (url: string) => {
        setLoadingCsv(true);
        try {
            const res = await fetch(url);
            setCsvRows(parseCsv(await res.text()));
        } catch {
            // ignore; CSV display is best-effort
        } finally {
            setLoadingCsv(false);
        }
    }, []);

    const fetchOutputCsv = useCallback(async (url: string) => {
        try {
            const res = await fetch(url);
            setOutputCsvRows(parseCsv(await res.text()));
        } catch { }
    }, []);

    const load = useCallback(async () => {
        if (!id) return;
        try {
            const req = await getStatusSingle(id);
            setItem(req);
            setError("");

            const iUrl = await resolveUrls(req);
            if (iUrl && csvRows.length === 0) fetchCsv(iUrl);
            if (req.status === "completed" && outputUrl && outputCsvRows.length === 0) fetchOutputCsv(outputUrl);

            if (req.status !== "pending" && req.status !== "processing") {
                if (pollRef.current) clearInterval(pollRef.current);
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load request");
        }
    }, [id, resolveUrls, fetchCsv, csvRows.length, fetchOutputCsv, outputUrl, outputCsvRows.length]);

    useEffect(() => {
        load();
        pollRef.current = setInterval(load, POLL_INTERVAL);
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [load]);

    function handleDownload(url: string, filename: string) {
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
    }

    if (error) {
        return (
            <Box>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/")} sx={{ mb: 2 }}>
                    Back
                </Button>
                <Alert severity="error">{error}</Alert>
            </Box>
        );
    }

    if (!item) {
        return (
            <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    const isPending = item.status === "pending" || item.status === "processing";

    return (
        <Box>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/")} sx={{ mb: 3 }}>
                Back to Dashboard
            </Button>

            {/* Header */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
                <Typography variant="h5" fontWeight={700}>
                    {item.identifier}
                </Typography>
                <StatusBadge status={item.status} />
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                {item.requestId} &nbsp;·&nbsp; Created {new Date(item.createdAt * 1000).toLocaleString()}
            </Typography>

            {/* Progress */}
            {isPending && (
                <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                        <Typography variant="body2" fontWeight={500}>
                            Enrichment Progress
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            {item.processedIsbns.toLocaleString()} / {item.totalIsbns.toLocaleString()} ISBNs
                        </Typography>
                    </Box>
                    <LinearProgress
                        variant="determinate"
                        value={item.totalIsbns ? (item.processedIsbns / item.totalIsbns) * 100 : 0}
                        sx={{ height: 8, borderRadius: 4 }}
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                        {item.totalIsbns ? Math.round((item.processedIsbns / item.totalIsbns) * 100) : 0}% complete
                    </Typography>
                </Paper>
            )}

            {/* Downloads */}
            <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
                <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    disabled={!inputUrl}
                    onClick={() => inputUrl && handleDownload(inputUrl, `${item.identifier}_input.csv`)}
                >
                    Download Input CSV
                </Button>
                {item.status === "completed" && (
                    <Button
                        variant="contained"
                        startIcon={<DownloadIcon />}
                        disabled={!outputUrl}
                        onClick={() => outputUrl && handleDownload(outputUrl, `${item.identifier}_output.csv`)}
                    >
                        Download Output CSV
                    </Button>
                )}
            </Box>

            {/* Notes */}
            {item.notes.length > 0 && (
                <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        Processing Notes
                    </Typography>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        {item.notes.map((note: EnrichmentNote, i: number) => (
                            <Alert key={i} severity={noteColor[note.type] ?? "info"} sx={{ py: 0.5 }}>
                                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                                    <Typography variant="body2">{note.message}</Typography>
                                    <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                                        {new Date(note.timestamp).toLocaleTimeString()}
                                    </Typography>
                                </Box>
                            </Alert>
                        ))}
                    </Box>
                </Paper>
            )}

            <Divider sx={{ mb: 3 }} />

            {/* Input CSV */}
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Input CSV
                <Chip label={`${Math.max(0, csvRows.length - 1)} ISBNs`} size="small" sx={{ ml: 1 }} />
            </Typography>

            {loadingCsv ? (
                <CircularProgress size={24} />
            ) : csvRows.length > 0 ? (
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400, mb: 4 }}>
                    <Table stickyHeader size="small">
                        <TableHead>
                            <TableRow>
                                {csvRows[0].map((col, i) => (
                                    <TableCell key={i} sx={{ fontWeight: 600 }}>{col}</TableCell>
                                ))}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {csvRows.slice(1).map((row, i) => (
                                <TableRow key={i}>
                                    {row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            ) : (
                <Typography color="text.secondary" variant="body2" sx={{ mb: 4 }}>
                    CSV preview unavailable
                </Typography>
            )}

            {/* Output CSV */}
            {item.status === "completed" && (
                <>
                    <Divider sx={{ mb: 3 }} />
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        Output CSV
                        <Chip label={`${Math.max(0, outputCsvRows.length - 1)} rows`} size="small" sx={{ ml: 1 }} />
                    </Typography>
                    {outputCsvRows.length > 0 ? (
                        <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
                            <Table stickyHeader size="small">
                                <TableHead>
                                    <TableRow>
                                        {outputCsvRows[0].map((col, i) => (
                                            <TableCell key={i} sx={{ fontWeight: 600 }}>{col}</TableCell>
                                        ))}
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {outputCsvRows.slice(1).map((row, i) => (
                                        <TableRow key={i}>
                                            {row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    ) : (
                        <Typography color="text.secondary" variant="body2">
                            Output CSV preview unavailable
                        </Typography>
                    )}
                </>
            )}
        </Box>
    );
}