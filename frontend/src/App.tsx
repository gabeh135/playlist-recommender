import { BrowserRouter, Routes, Route } from "react-router-dom"
import { useUser } from "./hooks/useUser"
import LoadingScreen from "./components/LoadingScreen"
import Layout from "./components/Layout/Layout"
import Collection from "./pages/Collection"
import Generate from "./pages/Generate"
import SortLibrary from "./pages/SortLibrary"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function App() {
  const userId = useUser()

  if (!userId) {
    return <LoadingScreen />
  }

  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Collection />} />
            <Route path="generate" element={<Generate />} />
            <Route path="sort" element={<SortLibrary />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  )
}
