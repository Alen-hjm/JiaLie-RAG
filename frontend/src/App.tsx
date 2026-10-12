import { lazy, Suspense, useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  ArrowRightOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  SearchOutlined,
  SettingOutlined,
  TeamOutlined,
  StarOutlined,
  LogoutOutlined,
  MenuOutlined,
  CloseOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  FileAddOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { Button, Input, Modal, Spin, message } from "antd";
import { MotionConfig } from "motion/react";
import { api } from "./api";
import { WorkspacePages } from "./components/WorkspacePages";
import { Brand } from "./components/Brand";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const loadResumes = () => import("./pages/ResumesPage");
const ResumesPage = lazy(loadResumes);
const loadSearch = () => import("./pages/SearchPage");
const SearchPage = lazy(loadSearch);
const CandidatePage = lazy(() => import("./pages/CandidatePage"));
const loadJobs = () => import("./pages/JobsPage");
const JobsPage = lazy(loadJobs);
const loadSettings = () => import("./pages/SettingsPage");
const SettingsPage = lazy(loadSettings);
const loadShortlist = () => import("./pages/ShortlistPage");
const ShortlistPage = lazy(loadShortlist);
const loadDashboard = () => import("./pages/DashboardPage");
const DashboardPage = lazy(loadDashboard);

const pageLoaders: Record<string, () => Promise<unknown>> = {
  "/": loadSearch,
  "/resumes": loadResumes,
  "/jobs": loadJobs,
  "/settings": loadSettings,
  "/shortlist": loadShortlist,
  "/dashboard": loadDashboard,
};
const warmPage = (path: string) => {
  void pageLoaders[path]?.().catch(() => {});
};
const navigation = [
  {
    path: "/",
    icon: <SearchOutlined />,
    label: "智能找人",
    en: "Talent search",
  },
  {
    path: "/dashboard",
    icon: <AppstoreOutlined />,
    label: "招聘概览",
    en: "Overview",
  },
  {
    path: "/jobs",
    icon: <FileTextOutlined />,
    label: "招聘岗位",
    en: "Job workspace",
  },
  {
    path: "/resumes",
    icon: <TeamOutlined />,
    label: "人才库",
    en: "Talent library",
  },
  {
    path: "/shortlist",
    icon: <StarOutlined />,
    label: "我的收藏",
    en: "Shortlist",
  },
  {
    path: "/settings",
    icon: <SettingOutlined />,
    label: "工作台设置",
    en: "Settings",
  },
];

function Shell({ onLogout }: { onLogout: () => Promise<void> }) {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      for (const load of Object.values(pageLoaders)) {
        if (cancelled) break;
        await load().catch(() => {});
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    }, 1200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);
  const location = useLocation(),
    navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const selected = location.pathname.startsWith("/candidate")
    ? "/resumes"
    : location.pathname;
  const current =
    navigation.find((item) => item.path === selected) || navigation[0];
  const go = (path: string) => {
    navigate(path);
    setMobileOpen(false);
    setCommandOpen(false);
    setQuery("");
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const logout = async () => {
    setLoggingOut(true);
    try {
      await onLogout();
    } finally {
      setLoggingOut(false);
    }
  };
  const filtered = navigation.filter((item) =>
    `${item.label} ${item.en}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className={`app-shell ${collapsed ? "rail-collapsed" : ""}`}>
      {mobileOpen && (
        <button
          className="nav-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-label="关闭导航"
        />
      )}
      <aside className={`side-rail ${mobileOpen ? "is-open" : ""}`}>
        <Brand />
        <Button
          className="rail-collapse"
          type="text"
          aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setCollapsed((value) => !value)}
        />
        <button className="rail-search" aria-label="快捷导航" title="快捷导航 · Ctrl / ⌘ K" onClick={() => setCommandOpen(true)}>
          <SearchOutlined />
          <span>快捷导航</span>
          <kbd>⌘ K</kbd>
        </button>
        <button
          className="new-search"
          aria-label="发起人才搜索"
          title="发起人才搜索"
          onClick={() => {
            navigate("/", { state: { newSearch: Date.now() } });
            setMobileOpen(false);
          }}
        >
          <PlusOutlined />
          <span>发起人才搜索</span>
          <ArrowRightOutlined />
        </button>
        <div className="rail-label">
          工作空间 <span>WORKSPACE</span>
        </div>
        <nav className="main-nav" aria-label="主导航">
          {navigation.slice(0, 5).map((item) => (
            <button
              key={item.path}
              aria-label={item.label}
              title={item.label}
              onPointerEnter={() => warmPage(item.path)}
              onFocus={() => warmPage(item.path)}
              className={selected === item.path ? "selected" : ""}
              onClick={() => go(item.path)}
              aria-current={selected === item.path ? "page" : undefined}
            >
              {item.icon}
              <span>{item.label}</span>
              {selected === item.path && <i />}
            </button>
          ))}
        </nav>
        <div className="rail-label system-label">
          管理 <span>MANAGE</span>
        </div>
        <nav className="main-nav" aria-label="管理导航">
          {navigation.slice(5).map((item) => (
            <button
              key={item.path}
              aria-label={item.label}
              title={item.label}
              onPointerEnter={() => warmPage(item.path)}
              onFocus={() => warmPage(item.path)}
              className={selected === item.path ? "selected" : ""}
              onClick={() => go(item.path)}
              aria-current={selected === item.path ? "page" : undefined}
            >
              {item.icon}
              <span>{item.label}</span>
              {selected === item.path && <i />}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <div className="private-space">
            <SafetyCertificateOutlined />
            <strong>你的专属人才空间</strong>
            <p>基于授权简历 · 让推荐有据可循</p>
            <button onClick={() => go("/settings")}>
              调整使用偏好 <ArrowRightOutlined />
            </button>
          </div>
          <div className="rail-profile">
            <div className="user-avatar">A</div>
            <div>
              <strong>我的账号</strong>
              <small>个人工作空间</small>
            </div>
            <Button
              type="text"
              title="退出登录"
              aria-label="退出登录"
              loading={loggingOut}
              icon={<LogoutOutlined />}
              onClick={logout}
            />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-bar">
          <div>
            <Button
              className="mobile-toggle"
              type="text"
              aria-label={mobileOpen ? "关闭导航" : "打开导航"}
              icon={mobileOpen ? <CloseOutlined /> : <MenuOutlined />}
              onClick={() => setMobileOpen(!mobileOpen)}
            />
            <span>工作空间</span>
            <span className="crumb-divider">/</span>
            <strong>{current.label}</strong>
          </div>
          <div className="workspace-meta">
            <Button
              aria-label="导入简历"
              className="toolbar-import"
              icon={<FileAddOutlined />}
              onPointerEnter={() => warmPage("/resumes")}
              onClick={() =>
                navigate("/resumes?import=1", {
                  state: { importAt: Date.now() },
                })
              }
            >
              导入简历
            </Button>
            <Button
              aria-label="新搜索"
              type="primary"
              icon={<PlusOutlined />}
              onClick={() =>
                navigate("/", { state: { newSearch: Date.now() } })
              }
            >
              新搜索
            </Button>
            <span className="space-badge">
              <span className="status-dot" />
              专属工作台
            </span>
            <span className="top-avatar">A</span>
          </div>
        </header>
        <main id="main-content">
          <WorkspacePages
            paths={Object.keys(pageLoaders)}
            render={(snapshot) => (
              <Routes location={snapshot}>
                <Route path="/" element={<SearchPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/resumes" element={<ResumesPage />} />
                <Route path="/jobs" element={<JobsPage />} />
                <Route path="/shortlist" element={<ShortlistPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/candidate/:id" element={<CandidatePage />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
            )}
          />
        </main>
      </div>
      <Modal
        title="快捷导航"
        open={commandOpen}
        onCancel={() => setCommandOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Input
          autoFocus
          size="large"
          prefix={<SearchOutlined />}
          placeholder="搜索页面，如人才库、设置…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={() => filtered[0] && go(filtered[0].path)}
        />
        <div className="command-results">
          {filtered.map((item) => (
            <button key={item.path} onClick={() => go(item.path)}>
              {item.icon}
              <span>
                {item.label}
                <small>{item.en}</small>
              </span>
              <ArrowRightOutlined />
            </button>
          ))}
          {!filtered.length && (
            <p className="muted">没有找到页面，试试其他关键词。</p>
          )}
        </div>
        <p className="command-tip">Ctrl / ⌘ K 打开 · Esc 关闭</p>
      </Modal>
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState<"loading" | "in" | "out">("loading");
  useEffect(() => {
    api("/api/auth/me")
      .then(() => setAuth("in"))
      .catch(() => setAuth("out"));
  }, []);
  const logout = async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
      setAuth("out");
      message.success("已安全退出");
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : "退出失败，请重试",
      );
    }
  };
  if (auth === "loading")
    return (
      <div className="boot-screen">
        <Brand />
        <Spin />
        <p>正在进入人才工作空间…</p>
      </div>
    );
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <Suspense
          fallback={
            <div className="boot-screen">
              <Spin />
            </div>
          }
        >
          {auth === "in" ? (
            <Shell onLogout={logout} />
          ) : (
            <LoginPage onSuccess={() => setAuth("in")} />
          )}
        </Suspense>
      </BrowserRouter>
    </MotionConfig>
  );
}
