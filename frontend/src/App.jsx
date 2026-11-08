import { useCallback, useEffect, useState } from "react";
import SolanaWalletProvider from "./components/SolanaWalletProvider";
import Masthead from "./components/Masthead";
import HomePage from "./pages/HomePage";
import ProjectPage from "./pages/ProjectPage";
import "./App.css";

function parseRoute() {
  const hash = window.location.hash.replace(/^#/, "");
  const match = hash.match(/^\/memorial\/([^/?#]+)/);
  return match
    ? { name: "project", id: decodeURIComponent(match[1]) }
    : { name: "home" };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [focusDocumentId, setFocusDocumentId] = useState(null);

  useEffect(() => {
    const onHashChange = () => {
      setRoute(parseRoute());
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const openProject = useCallback((projectId, documentId = null) => {
    setFocusDocumentId(documentId);
    window.location.hash = `/memorial/${projectId}`;
  }, []);

  const goHome = useCallback(() => {
    setFocusDocumentId(null);
    if (window.location.hash === "#/" || window.location.hash === "") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      window.location.hash = "/";
    }
  }, []);

  const goArchive = useCallback(() => {
    const scroll = () =>
      document.getElementById("archive")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (route.name === "home") {
      scroll();
    } else {
      window.location.hash = "/";
      window.setTimeout(scroll, 120);
    }
  }, [route.name]);

  return (
    <SolanaWalletProvider>
      <div className="app-shell">
        <Masthead route={route} onHome={goHome} onArchive={goArchive} />

        {route.name === "project" ? (
          <ProjectPage
            key={route.id}
            projectId={route.id}
            focusDocumentId={focusDocumentId}
            onHome={goHome}
          />
        ) : (
          <HomePage onOpenProject={openProject} />
        )}

        <footer className="colophon">
          <div className="colophon-mark">
            <img src="/ObiTree_Logo.jpg" alt="" aria-hidden="true" />
          </div>
          <div className="colophon-copy">
            <p className="colophon-title">Orbitree</p>
            <p>
              A family chronicle is never finished. Every clipping is a page, every page is a
              block, and every signature keeps the record honest.
            </p>
          </div>
        </footer>
      </div>
    </SolanaWalletProvider>
  );
}
