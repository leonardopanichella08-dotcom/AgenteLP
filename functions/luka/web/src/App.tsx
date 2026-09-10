import { Route, Routes } from "react-router-dom";
import { AppProvider } from "./state";
import { Shell } from "./components/Shell";
import LukaPage from "./pages/LukaPage";
import DashboardPage from "./pages/DashboardPage";
import ConnectionsPage from "./pages/ConnectionsPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <AppProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<LukaPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<LukaPage />} />
        </Route>
      </Routes>
    </AppProvider>
  );
}
