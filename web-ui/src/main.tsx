import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "@/context/ThemeContext"
import { ModeProvider } from "@/context/ModeContext"
import { SidebarProvider } from "@/context/SidebarContext"
import { AuthProvider } from "@/context/AuthContext"
import { DialogProvider } from "@/context/DialogContext"
import { LanguageProvider } from "@/context/LanguageContext"
import { LiveUpdatesProvider } from "@/context/LiveUpdatesContext"
import { PanelProvider } from "@/context/PanelContext"
import { Toaster } from "sonner"
import App from "./App"
import "./index.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    },
    mutations: {
      retry: 0,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <ModeProvider>
            <SidebarProvider>
              <DialogProvider>
                <LanguageProvider>
                <LiveUpdatesProvider>
                  <PanelProvider>
                    <App />
                    <Toaster richColors closeButton position="top-right" />
                  </PanelProvider>
                </LiveUpdatesProvider>
                </LanguageProvider>
              </DialogProvider>
            </SidebarProvider>
          </ModeProvider>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
