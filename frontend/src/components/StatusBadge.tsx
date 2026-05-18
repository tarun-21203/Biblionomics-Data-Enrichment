import Chip from "@mui/material/Chip";

const config: Record<
    string,
    { label: string; color: "default" | "warning" | "success" | "error" | "info" }
> = {
    pending: { label: "Pending", color: "warning" },
    processing: { label: "Processing", color: "info" },
    completed: { label: "Completed", color: "success" },
    failed: { label: "Failed", color: "error" },
};

export default function StatusBadge({ status }: { status: string }) {
    const { label, color } = config[status] ?? { label: status, color: "default" };
    return <Chip label={label} color={color} size="small" />;
}