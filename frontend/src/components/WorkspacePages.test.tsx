// @vitest-environment jsdom
import { useEffect, useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { WorkspacePages, usePageActive } from "./WorkspacePages";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("preserves drafts and route queries while isolating the inactive page", () => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const unmounted = vi.fn();
  function Library() {
    const [draft, setDraft] = useState("");
    const location = useLocation(),
      active = usePageActive();
    useEffect(() => () => unmounted(), []);
    return (
      <div data-testid="library" data-active={active}>
        <input
          aria-label="筛选"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <span data-testid="query">{location.search}</span>
      </div>
    );
  }
  function Harness() {
    const navigate = useNavigate();
    return (
      <>
        <button onClick={() => navigate("/jobs")}>岗位</button>
        <button onClick={() => navigate(-1)}>返回</button>
        <WorkspacePages
          paths={["/resumes", "/jobs"]}
          render={(location) => (
            <Routes location={location}>
              <Route path="/resumes" element={<Library />} />
              <Route path="/jobs" element={<p>岗位内容</p>} />
            </Routes>
          )}
        />
      </>
    );
  }
  render(
    <MemoryRouter initialEntries={["/resumes?status=failed"]}>
      <Harness />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByRole("textbox", { name: "筛选" }), {
    target: { value: "上海" },
  });
  fireEvent.click(screen.getByText("岗位"));
  expect(screen.queryByRole("textbox", { name: "筛选" })).toBeNull();
  expect(screen.getByTestId("library").getAttribute("data-active")).toBe(
    "false",
  );
  expect(screen.getByTestId("query").textContent).toBe("?status=failed");
  fireEvent.click(screen.getByText("返回"));
  expect(
    (screen.getByRole("textbox", { name: "筛选" }) as HTMLInputElement).value,
  ).toBe("上海");
  expect(unmounted).not.toHaveBeenCalled();
});
