import { StudioHeading } from "../components/StudioHeading";
import { GlowingEffect } from "../components/ui/glowing-effect";
import { usePageRefresh } from "../components/WorkspacePages";
import { useState } from "react";
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileAddOutlined,
  FileTextOutlined,
  PlusOutlined,
  StarOutlined,
  TeamOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Empty, Skeleton } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useShortlist } from "../shortlist";

type Stats = {
  candidate_count: number;
  processing_count: number;
  failed_count: number;
};
type Job = {
  id: string;
  company?: string;
  title: string;
  location?: string;
  created_at: string;
  match_count: number;
  conversation_id?: string;
};
export default function DashboardPage() {
  const navigate = useNavigate(),
    saved = useShortlist();
  const [stats, setStats] = useState<Stats>(),
    [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState("");
  const load = async () => {
    setError("");
    try {
      const [s, j] = await Promise.all([
        api<Stats>("/api/dashboard"),
        api<{ items: Job[] }>("/api/jobs"),
      ]);
      setStats(s);
      setJobs(j.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "暂时无法加载，请重试");
    }
  };
  usePageRefresh(() => {
    void load();
  });
  const waiting = jobs.filter((job) => !job.match_count).length;
  return (
    <div className="page dashboard-page">
      <StudioHeading
        number="01"
        label="DAILY BRIEF"
        title="把发现，"
        accent="变成下一步。"
        description="招聘概览 / 你的岗位、人才与待办，在这里汇合。"
      />
      <section className="brief-layout">
        <div className="brief-cover">
          <GlowingEffect />
          <div className="brief-cover-top">
            <span>你的招聘简报</span>
            <span>
              {new Date().toLocaleDateString("zh-CN", {
                month: "long",
                day: "numeric",
              })}
            </span>
          </div>
          <div className="brief-cover-main">
            <span className="brief-large">
              {stats
                ? (waiting || jobs.length).toString().padStart(2, "0")
                : "—"}
            </span>
            <div>
              <h2>
                {waiting
                  ? "份需求，等待遇见合适的人。"
                  : jobs.length
                    ? "份岗位，已有可查看的推荐。"
                    : "从第一份招聘需求开始。"}
              </h2>
              <p>
                {stats
                  ? jobs.length
                    ? waiting
                      ? "从尚未匹配的岗位开始，继续推进你的招聘。"
                      : "回到推荐依据，筛选值得进一步沟通的人选。"
                    : "保存第一份需求，开启你的招聘工作空间。"
                  : "正在整理工作空间中的招聘进展…"}
              </p>
            </div>
          </div>
          <div className="brief-cover-footer">
            <Button onClick={() => navigate("/jobs")}>
              查看招聘岗位 <ArrowRightOutlined />
            </Button>
            <button
              onClick={() =>
                navigate("/", { state: { newSearch: Date.now() } })
              }
            >
              发起新搜索 <PlusOutlined />
            </button>
          </div>
        </div>
        <div className="brief-resource">
          <span className="eyebrow">YOUR TALENT FOUNDATION</span>
          <div>
            <strong>{stats?.candidate_count ?? "—"}</strong>
            <span>份经历，已准备好被发现</span>
          </div>
          <p>所有推荐都从你的授权简历中寻找依据。</p>
          <button onClick={() => navigate("/resumes")}>
            浏览人才库 <ArrowRightOutlined />
          </button>
        </div>
      </section>
      {error && (
        <Alert
          type="warning"
          message={error}
          showIcon
          action={<Button onClick={load}>重试</Button>}
        />
      )}
      <section className="metric-grid brief-metrics" aria-label="招聘概览数据">
        {[
          {
            icon: <TeamOutlined />,
            label: "可检索人才",
            value: stats?.candidate_count,
            description: "已整理的人才档案",
            path: "/resumes",
          },
          {
            icon: <FileTextOutlined />,
            label: "招聘岗位",
            value: stats ? jobs.length : undefined,
            description: "最近保存的岗位",
            path: "/jobs",
          },
          {
            icon: <StarOutlined />,
            label: "我的收藏",
            value: saved.length,
            description: "当前浏览器中的关注名单",
            path: "/shortlist",
          },
          {
            icon: <WarningOutlined />,
            label: "需要关注",
            value: stats?.failed_count,
            description: "尚未成功处理的简历",
            path: "/resumes?status=failed",
          },
        ].map((item) => (
          <button
            className="metric-card"
            key={item.label}
            onClick={() => navigate(item.path)}
          >
            <GlowingEffect />
            <span className="metric-label">
              {item.icon}
              {item.label}
              <ArrowRightOutlined />
            </span>
            <strong>{item.value === undefined ? "—" : item.value}</strong>
            <small>{item.description}</small>
          </button>
        ))}
      </section>
      <div className="overview-columns">
        <section className="panel overview-jobs">
          <div className="section-heading">
            <div>
              <p className="eyebrow">PICK UP WHERE YOU LEFT OFF</p>
              <h2>
                正在推进 <span className="section-index">/ 01</span>
              </h2>
            </div>
            <Button type="text" onClick={() => navigate("/jobs")}>
              所有岗位 <ArrowRightOutlined />
            </Button>
          </div>
          {!stats && !error ? (
            <Skeleton active />
          ) : jobs.length ? (
            jobs.slice(0, 5).map((job, i) => (
              <button
                className="project-row"
                key={job.id}
                onClick={() => navigate("/jobs", { state: { jobId: job.id } })}
              >
                <span className="project-index">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{job.title}</strong>
                  <small>
                    {job.company || "公司未填写"} · {job.location || "地点不限"}
                  </small>
                </span>
                <span
                  className={`project-status ${job.match_count ? "ready" : ""}`}
                >
                  {job.match_count ? `${job.match_count} 位推荐` : "等待匹配"}
                </span>
                <ArrowRightOutlined />
              </button>
            ))
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="还没有招聘岗位"
            >
              <Button onClick={() => navigate("/")}>描述第一份招聘需求</Button>
            </Empty>
          )}
        </section>
        <aside className="next-step-panel">
          <p className="eyebrow">NEXT BEST STEP</p>
          <h2>
            下一步行动 <span className="section-index">/ 02</span>
          </h2>
          {stats?.failed_count ? (
            <button
              className="next-step"
              onClick={() => navigate("/resumes?status=failed")}
            >
              <WarningOutlined />
              <span>
                <strong>处理 {stats.failed_count} 份异常简历</strong>
                <small>重试导入，让人才库保持完整。</small>
              </span>
              <ArrowRightOutlined />
            </button>
          ) : null}
          {stats?.processing_count ? (
            <div className="next-step">
              <ClockCircleOutlined />
              <span>
                <strong>{stats.processing_count} 份简历正在整理</strong>
                <small>处理完成后，即可用于搜索。</small>
              </span>
            </div>
          ) : null}
          <button
            className="next-step"
            onClick={() => navigate(saved.length ? "/shortlist" : "/resumes")}
          >
            <StarOutlined />
            <span>
              <strong>
                {saved.length ? "回访你收藏的人才" : "丰富你的专属人才库"}
              </strong>
              <small>
                {saved.length
                  ? "并排比较经历，确定沟通优先级。"
                  : "导入简历，为下一次招聘做好准备。"}
              </small>
            </span>
            <ArrowRightOutlined />
          </button>
          <button
            className="next-step"
            onClick={() => navigate("/resumes?import=1")}
          >
            <FileAddOutlined />
            <span>
              <strong>导入新收到的简历</strong>
              <small>支持多份 PDF、DOCX 一起上传。</small>
            </span>
            <ArrowRightOutlined />
          </button>
          {stats && !stats.failed_count && !stats.processing_count && (
            <div className="quiet-status">
              <CheckCircleOutlined /> 人才库已整理完成
            </div>
          )}
        </aside>
      </div>
      <div className="overview-footer">
        <span>从需求出发，以经历为依据。</span>
        <p>所有数字来自当前工作空间；收藏只在当前浏览器中保存。</p>
      </div>
    </div>
  );
}
