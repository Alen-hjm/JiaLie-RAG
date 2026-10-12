import {
  createContext,
  ReactNode,
  Suspense,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Location, useLocation } from "react-router-dom";
import { Spin } from "antd";

const PageActive = createContext(true);
export const usePageActive = () => useContext(PageActive);

// Refresh on return without discarding the page's draft, filters or visible data.
export function usePageRefresh(refresh: () => void) {
  const active = usePageActive();
  const latest = useRef(refresh);
  latest.current = refresh;
  useEffect(() => {
    if (active) latest.current();
  }, [active]);
}

export function WorkspacePages({
  paths,
  render,
}: {
  paths: string[];
  render: (location: Location) => ReactNode;
}) {
  const location = useLocation();
  const [visited, setVisited] = useState<Record<string, Location>>({});
  const positions = useRef<Record<string, number>>({});
  if (
    paths.includes(location.pathname) &&
    visited[location.pathname] !== location
  ) {
    setVisited({ ...visited, [location.pathname]: location });
  }
  useLayoutEffect(() => {
    const key = location.pathname;
    window.scrollTo({ top: positions.current[key] || 0, behavior: "instant" });
    const save = () => {
      positions.current[key] = window.scrollY;
    };
    window.addEventListener("scroll", save, { passive: true });
    return () => window.removeEventListener("scroll", save);
  }, [location.pathname]);
  const pages = paths.includes(location.pathname)
    ? visited
    : { ...visited, [location.pathname]: location };
  return (
    <>
      {Object.entries(pages).map(([path, snapshot]) => {
        const active = path === location.pathname;
        return (
          <PageActive.Provider key={path} value={active}>
            <div
              hidden={!active}
              className="workspace-page"
              aria-hidden={!active}
            >
              <Suspense
                fallback={
                  <div className="page route-loading">
                    <Spin />
                    <p>正在打开页面…</p>
                  </div>
                }
              >
                {render(active ? location : snapshot)}
              </Suspense>
            </div>
          </PageActive.Provider>
        );
      })}
    </>
  );
}
