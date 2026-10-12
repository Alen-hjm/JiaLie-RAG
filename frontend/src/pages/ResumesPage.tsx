import { StudioHeading } from "../components/StudioHeading";
import { GlowingEffect } from "../components/ui/glowing-effect";
import { usePageActive, usePageRefresh } from "../components/WorkspacePages";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRightOutlined,
  DeleteOutlined,
  ReloadOutlined,
  SearchOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Empty,
  Input,
  message,
  Popconfirm,
  Progress,
  Select,
  Skeleton,
  Tag,
} from "antd";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, Candidate } from "../api";
import { SaveCandidate } from "../components/SaveCandidate";

type Row = {
  document_id: string;
  filename: string;
  status: string;
  error_message?: string;
  created_at: string;
  task?: { id: string; progress: number; message: string };
  candidate?: Candidate;
};
const labels: Record<string, [string, string]> = {
  queued: ["等待整理", "default"],
  processing: ["正在解析", "processing"],
  vectorizing: ["正在整理", "processing"],
  completed: ["可检索", "success"],
  failed: ["需处理", "error"],
};
export default function ResumesPage() {
  const pageActive = usePageActive();
  const route = useLocation();
  const uploadZone = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (pageActive && new URLSearchParams(route.search).has("import")) {
      uploadZone.current?.scrollIntoView({
        block: "center",
        behavior: "instant",
      });
      uploadZone.current?.focus({ preventScroll: true });
    }
  }, [pageActive, route.key]);
  const [params, setParams] = useSearchParams(),
    navigate = useNavigate(),
    input = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<Row[]>([]),
    [query, setQuery] = useState(""),
    [city, setCity] = useState<string>(),
    [experience, setExperience] = useState<string>();
  const status = params.get("status") || "all";
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [uploading, setUploading] = useState(false),
    [report, setReport] = useState("");
  const [retrying, setRetrying] = useState<string>(),
    [dragging, setDragging] = useState(false);
  const load = async () => {
    try {
      const data = await api<{ items: Row[] }>("/api/candidates");
      setRows(data.items);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "人才库暂时无法加载，请重试");
    } finally {
      setLoading(false);
    }
  };
  usePageRefresh(() => {
    void load();
  });
  useEffect(() => {
    if (
      !pageActive ||
      !rows.some((row) =>
        ["queued", "processing", "vectorizing"].includes(row.status),
      )
    )
      return;
    const timer = setInterval(() => void load(), 2500);
    return () => clearInterval(timer);
  }, [rows, pageActive]);
  const cities = useMemo(
    () => [
      ...new Set(
        rows
          .map((row) => row.candidate?.location)
          .filter((value): value is string => !!value),
      ),
    ],
    [rows],
  );
  const filtered = rows.filter(
    (row) =>
      `${row.candidate?.name || ""} ${row.candidate?.current_title || ""} ${row.filename} ${row.candidate?.skills.join(" ") || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (!city || row.candidate?.location === city) &&
      (!experience ||
        (experience === "senior"
          ? (row.candidate?.years_experience || 0) >= 10
          : (row.candidate?.years_experience || 0) >= 5)) &&
      (status === "all" ||
        (status === "processing"
          ? ["queued", "processing", "vectorizing"].includes(row.status)
          : row.status === status)),
  );
  const uploadFiles = async (files: File[]) => {
    if (!files.length || uploading) return;
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    setUploading(true);
    setReport("");
    try {
      const result = await api<{
        accepted: unknown[];
        duplicates: unknown[];
        rejected: unknown[];
      }>("/api/resumes/import", { method: "POST", body: form });
      setReport(
        `已接收 ${result.accepted.length} 份 · 已存在 ${result.duplicates.length} 份 · 未接收 ${result.rejected.length} 份${result.rejected.length ? "。请确认文件为未加密的 PDF 或 DOCX，且不超过 20 MB。" : ""}`,
      );
      await load();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "上传未完成，请重试");
    } finally {
      setUploading(false);
      setDragging(false);
    }
  };
  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    void uploadFiles(files);
  };
  const retry = async (taskId: string) => {
    setRetrying(taskId);
    try {
      await api(`/api/import-tasks/${taskId}/retry`, { method: "POST" });
      message.success("已重新开始处理");
      await load();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "暂时无法重试");
    } finally {
      setRetrying(undefined);
    }
  };
  const remove = async (id: string) => {
    try {
      await api(`/api/candidates/${id}`, { method: "DELETE" });
      message.success("人才档案与相关记录已删除");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "删除失败，请刷新确认");
    } finally {
      await load();
    }
  };
  const setStatus = (value: string) =>
    setParams(value === "all" ? {} : { status: value }, { replace: true });
  return (
    <div className="page library-page">
      <StudioHeading
        number="03"
        label="TALENT ARCHIVE"
        title="经历有迹，"
        accent="人才可寻。"
        description="人才库 / 收藏经验的价值，发现下一次匹配的可能。"
      />
      <div className="archive-intro">
        <section className="archive-cover">
          <div className="archive-label">
            <span>你的专属人才档案室</span>
            <span>PRIVATE COLLECTION</span>
          </div>
          <div className="archive-count">
            <strong>
              {loading
                ? "—"
                : rows
                    .filter((row) => row.status === "completed")
                    .length.toString()
                    .padStart(2, "0")}
            </strong>
            <div>
              <h2>份档案，可供检索</h2>
              <p>从姓名、技能到行业，找到你关心的经历。</p>
            </div>
          </div>
          <div className="archive-foot">
            <span>{cities.length} 个城市</span>
            <span>
              {
                rows.filter((row) =>
                  ["queued", "processing", "vectorizing"].includes(row.status),
                ).length
              }{" "}
              份整理中
            </span>
            <span>
              {rows.filter((row) => row.status === "failed").length} 份需处理
            </span>
          </div>
        </section>
        <input
          hidden
          multiple
          ref={input}
          type="file"
          accept=".pdf,.docx"
          onChange={upload}
        />
        <button
          ref={uploadZone}
          disabled={uploading}
          className={`upload-zone ${dragging ? "dragging" : ""} ${params.has("import") ? "highlighted" : ""}`}
          onClick={() => input.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            void uploadFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <GlowingEffect />
          <span className="upload-symbol">
            <UploadOutlined />
          </span>
          <span>
            <strong>
              {uploading ? "正在接收简历，请稍候…" : "把新的人才，带进工作空间"}
            </strong>
            <small>
              拖放文件到这里，或点击上传 · PDF / DOCX · 单份不超过 20 MB
            </small>
          </span>
          <span className="upload-label">
            批量导入 <ArrowRightOutlined />
          </span>
        </button>
      </div>
      {report && (
        <Alert
          showIcon
          type="info"
          message={report}
          closable
          onClose={() => setReport("")}
        />
      )}{" "}
      {error && (
        <Alert
          showIcon
          type="warning"
          message={error}
          action={<Button onClick={load}>重试</Button>}
        />
      )}
      <section className="panel library-panel">
        <div className="archive-directory-title">
          <h2>
            人才名册 <span>/ DIRECTORY</span>
          </h2>
          <span>从经历出发，找到合适的人</span>
        </div>
        <div className="library-tabs">
          {[
            { value: "all", label: "全部人才", count: rows.length },
            {
              value: "completed",
              label: "可检索",
              count: rows.filter((row) => row.status === "completed").length,
            },
            {
              value: "processing",
              label: "处理中",
              count: rows.filter((row) =>
                ["queued", "processing", "vectorizing"].includes(row.status),
              ).length,
            },
            {
              value: "failed",
              label: "需处理",
              count: rows.filter((row) => row.status === "failed").length,
            },
          ].map((tab) => (
            <button
              key={tab.value}
              className={status === tab.value ? "active" : ""}
              onClick={() => setStatus(tab.value)}
            >
              {tab.label}
              <span>{tab.count}</span>
            </button>
          ))}
        </div>
        <div className="library-filters">
          <Input
            prefix={<SearchOutlined />}
            allowClear
            aria-label="搜索人才"
            placeholder="搜索姓名、职位、技能或文件名"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Select
            aria-label="按城市筛选"
            placeholder="所有城市"
            allowClear
            value={city}
            onChange={setCity}
            options={cities.map((value) => ({ value, label: value }))}
          />
          <Select
            aria-label="按经验筛选"
            placeholder="工作经验"
            allowClear
            value={experience}
            onChange={setExperience}
            options={[
              { value: "experienced", label: "5 年及以上" },
              { value: "senior", label: "10 年及以上" },
            ]}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={load}
            aria-label="刷新人才库"
          />
        </div>
        <div className="talent-table">
          <div className="talent-table-head">
            <span>候选人 / 简历</span>
            <span>所在地</span>
            <span>工作经验</span>
            <span>处理状态</span>
            <span>操作</span>
          </div>
          {loading ? (
            <Skeleton active />
          ) : (
            filtered.map((row) => (
              <div className="talent-table-row" key={row.document_id}>
                <div className="talent-identity">
                  <span className="profile-initial">
                    {(row.candidate?.name || row.filename).slice(0, 1)}
                  </span>
                  <div>
                    {row.candidate ? (
                      <button
                        onClick={() =>
                          navigate(`/candidate/${row.candidate!.id}`)
                        }
                      >
                        {row.candidate.name}
                      </button>
                    ) : (
                      <strong>{row.filename}</strong>
                    )}
                    <small>
                      {row.candidate?.current_title || row.filename}
                    </small>
                    {!!row.candidate?.skills.length && (
                      <div className="archive-skills">
                        {row.candidate.skills.slice(0, 3).map((skill) => (
                          <span key={skill}>{skill}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <span className="talent-location">
                  {row.candidate?.location || "未填写"}
                </span>
                <span className="talent-experience">
                  {row.candidate ? `${row.candidate.years_experience} 年` : "—"}
                </span>
                <div className="talent-state">
                  <Tag color={labels[row.status]?.[1]}>
                    {labels[row.status]?.[0] || "整理中"}
                  </Tag>
                  {row.task &&
                    ["processing", "vectorizing"].includes(row.status) && (
                      <Progress percent={row.task.progress} size="small" />
                    )}
                  {row.status === "failed" && <small>请检查文件后重试</small>}
                </div>
                <div className="talent-operations">
                  {row.status === "failed" && row.task && (
                    <Button
                      size="small"
                      loading={retrying === row.task.id}
                      onClick={() => retry(row.task!.id)}
                    >
                      重试
                    </Button>
                  )}
                  {row.candidate && (
                    <>
                      <SaveCandidate id={row.candidate.id} compact />
                      <Popconfirm
                        title="删除人才档案及其原始简历？"
                        onConfirm={() => remove(row.candidate!.id)}
                      >
                        <Button
                          type="text"
                          aria-label={`删除人才 ${row.candidate.name}`}
                          icon={<DeleteOutlined />}
                        />
                      </Popconfirm>
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        {!loading && !filtered.length && (
          <div className="library-empty">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                rows.length ? "没有符合当前筛选的人才" : "还没有人才档案"
              }
            />
            <Button
              onClick={() => {
                if (rows.length) {
                  setQuery("");
                  setCity(undefined);
                  setExperience(undefined);
                  setStatus("all");
                } else input.current?.click();
              }}
            >
              {rows.length ? "清空筛选" : "导入第一份简历"}
            </Button>
          </div>
        )}
        <div className="library-table-footer">
          <span>
            显示 {filtered.length} / {rows.length} 份简历
          </span>
          <span>请仅导入已获得处理授权的简历</span>
        </div>
      </section>
    </div>
  );
}
