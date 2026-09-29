import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Importar siempre con "@/…" en vez de "../../../".
      // Con estructura por features y 6 personas, las rutas relativas
      // se rompen cada vez que un archivo cambia de carpeta.
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
});
