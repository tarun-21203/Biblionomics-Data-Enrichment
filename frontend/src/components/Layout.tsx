import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Container from "@mui/material/Container";
import Box from "@mui/material/Box";
import { Link } from "react-router-dom";

export default function Layout({ children }: { children: React.ReactNode }) {
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
                        BIBLIOnomics Enrichment
                    </Typography>
                </Toolbar>
            </AppBar>
            <Container maxWidth="lg" sx={{ py: 4 }}>
                {children}
            </Container>
        </Box>
    );
}