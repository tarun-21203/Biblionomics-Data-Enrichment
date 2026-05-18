import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Container from "@mui/material/Container";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import SettingsIcon from "@mui/icons-material/Settings";
import { Link } from "react-router-dom";
import SetEndpointModal from "./SetEndpointModal";

export default function Layout({ children }: { children: React.ReactNode }) {
    const [modalOpen, setModalOpen] = useState(false);

    return (
        <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
            <AppBar position="static" elevation={1}>
                <Toolbar>
                    <Typography
                        variant="h6"
                        component={Link}
                        to="/"
                        sx={{ textDecoration: "none", color: "inherit", fontWeight: 700 }}
                    >
                        Biblionomics Data Enrichment
                    </Typography>
                    <Box sx={{ flexGrow: 1 }} />
                    <Tooltip title="Set API endpoint">
                        <IconButton color="inherit" onClick={() => setModalOpen(true)}>
                            <SettingsIcon />
                        </IconButton>
                    </Tooltip>
                </Toolbar>
            </AppBar>
            <Container maxWidth="lg" sx={{ py: 4 }}>
                {children}
            </Container>
            <SetEndpointModal open={modalOpen} onClose={() => setModalOpen(false)} />
        </Box>
    );
}