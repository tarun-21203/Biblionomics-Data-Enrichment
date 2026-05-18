import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import LinearProgress from "@mui/material/LinearProgress";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import StatusBadge from "../components/StatusBadge";
import { getStatusAll, EnrichmentRequest } from "../services/api";

const POLL_INTERVAL = 10_000;

export default function Dashboard() {
    const navigate = useNavigate();
    const [requests, setRequests] = useState<EnrichmentRequest[]>([]);
    const [filter, setFilter] = useState("");
    const [statusFilter, setStatusFilter] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const data = await getStatusAll(filter || undefined, statusFilter || undefined);
            setRequests(data.requests);
            setError("");
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load requests");
        } finally {
            setLoading(false);
        }
    }, [filter, statusFilter]);

    useEffect(() => {
        load();
        const id = setInterval(load, POLL_INTERVAL);
        return () => clearInterval(id);
    }, [load]);

    return (
        <Box>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
                <Typography variant="h5" fontWeight={700}>
                    Enrichment Requests
                </Typography>
                <Box sx={{ display: "flex", gap: 1 }}>
                    <Tooltip title="Refresh">
                        <IconButton onClick={load}>
                            <RefreshIcon />
                        </IconButton>
                    </Tooltip>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => navigate("/submit")}
                    >
                        New Enrichment
                    </Button>
                </Box>
            </Box>

            <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
                <TextField
                    label="Search"
                    size="small"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    placeholder="Filter by name or ID"
                    sx={{ width: 300 }}
                />
                <FormControl size="small" sx={{ width: 180 }}>
                    <InputLabel>Status</InputLabel>
                    <Select
                        value={statusFilter}
                        label="Status"
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="pending">Pending</MenuItem>
                        <MenuItem value="processing">Processing</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="failed">Failed</MenuItem>
                    </Select>
                </FormControl>
            </Box>

            {loading && <LinearProgress sx={{ mb: 2 }} />}
            {error && (
                <Typography color="error" sx={{ mb: 2 }}>
                    {error}
                </Typography>
            )}

            <TableContainer component={Paper} variant="outlined">
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Identifier</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Progress</TableCell>
                            <TableCell align="right">ISBNs</TableCell>
                            <TableCell>Created</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {requests.length === 0 && !loading ? (
                            <TableRow>
                                <TableCell colSpan={5} align="center" sx={{ py: 6, color: "text.secondary" }}>
                                    No requests found
                                </TableCell>
                            </TableRow>
                        ) : (
                            requests.map((r) => (
                                <TableRow
                                    key={r.requestId}
                                    hover
                                    sx={{ cursor: "pointer" }}
                                    onClick={() => navigate(`/enrichment/${r.requestId}`)}
                                >
                                    <TableCell>
                                        <Typography fontWeight={500}>{r.identifier}</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {r.requestId}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <StatusBadge status={r.status} />
                                    </TableCell>
                                    <TableCell sx={{ width: 200 }}>
                                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                            <LinearProgress
                                                variant="determinate"
                                                value={r.enrichmentProgress}
                                                sx={{ flex: 1 }}
                                            />
                                            <Typography variant="caption">{r.enrichmentProgress}%</Typography>
                                        </Box>
                                    </TableCell>
                                    <TableCell align="right">{r.totalIsbns.toLocaleString()}</TableCell>
                                    <TableCell>
                                        <Typography variant="body2">
                                            {new Date(r.createdAt).toLocaleString()}
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
}