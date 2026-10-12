import { StudioHeading } from "../components/StudioHeading";
import { GlowingEffect } from "../components/ui/glowing-effect";
import { usePageActive, usePageRefresh } from "../components/WorkspacePages";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRightOutlined,
  DeleteOutlined,
  EnvironmentOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Skeleton,
  Tag,
  message,
} from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import { api, Match, Requirements } from "../api";
import { SaveCandidate } from "../components/SaveCandidate";

type Job = {
  id: string;
  company?: string;
  title: string;
  location?: string;
  created_at: string;
  match_count: number;
  requirements?: Requirements;
  conversation_id?: string;
};
type JobForm = {
  title: string;
  company?: string;
  location?: string;
  minimum_years?: number;
  skills?: string;
};
export default function JobsPage() {
  const pageActive = usePageActive();
  const navigate = useNavigate(),
    route = useLocation(),
    [form] = Form.useForm<JobForm>();
  const [jobs, setJobs] = useState<Job[]>([]),
    [query, setQuery] = useState(""),
    [industry, setIndustry] = useState<string>(),
    [status, setStatus] = useState<string>("all"),
    [sort, setSort] = useState("recent");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [createOpen, setCreateOpen] = useState(false),
    [saving, setSaving] = useState(false);
  const [active, setActive] = useState<Job>(),
    [matches, setMatches] = useState<Match[]>([]),
    [matching, setMatching] = useState(false),
    [detailLoading, setDetailLoading] = useState(false),
    [detailError, setDetailError] = useState("");
  const load = async () => {
    setError("");
    try {
      const result = await api<{ items: Job[] }>("/api/jobs");
      setJobs(result.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "岗位暂时无法加载");
    } finally {
      setLoading(false);
    }
  };
  usePageRefresh(() => {
    void load();
  });
  useEffect(() => {
    const id = (route.state as { jobId?: string } | null)?.jobId;
    if (pageActive && id && jobs.length) {
      setActive(jobs.find((job) => job.id === id));
      navigate("/jobs", { replace: true, state: null });
    }
  }, [jobs, route.state, pageActive]);
  useEffect(() => {
    if (!active) return;
    let current = true;
    setDetailLoading(true);
    setMatches([]);
    setDetailError("");
    api<{ items: Match[] }>(`/api/jobs/${active.id}/matches`)
      .then((result) => {
        if (current) setMatches(result.items);
      })
      .catch((e) => {
        if (current)
          setDetailError(e instanceof Error ? e.message : "推荐暂时无法加载");
      })
      .finally(() => {
        if (current) setDetailLoading(false);
      });
    return () => {
      current = false;
    };
  }, [active?.id]);
  const industries = useMemo(
    () => [
      ...new Set(jobs.flatMap((job) => job.requirements?.industries || [])),
    ],
    [jobs],
  );
  const filtered = jobs.filter(
    (job) =>
      `${job.company || ""} ${job.title} ${job.location || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (!industry || job.requirements?.industries.includes(industry)) &&
      (status === "all" ||
        (status === "ready" ? job.match_count > 0 : job.match_count === 0)),
  );
  filtered.sort((a, b) =>
    sort === "matches"
      ? b.match_count - a.match_count
      : new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const create = async (values: JobForm) => {
    setSaving(true);
    try {
      const created = await api<Job>("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          company: values.company?.trim() || "",
          title: values.title.trim(),
          requirements: {
            company: values.company?.trim() || "",
            title: values.title.trim(),
            industries: [],
            locations: values.location?.trim() ? [values.location.trim()] : [],
            minimum_years: values.minimum_years || 0,
            skills: (values.skills || "")
              .split(/[，,、\n]/)
              .map((value) => value.trim())
              .filter(Boolean),
            management_required: false,
            must_have: [],
            preferred: [],
            performance_expectations: [],
          },
        }),
      });
      setCreateOpen(false);
      form.resetFields();
      message.success("岗位已保存，可以开始匹配人才");
      setActive({
        ...created,
        company: values.company,
        location: values.location,
      });
      await load();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };
  const remove = async (id: string) => {
    try {
      await api(`/api/jobs/${id}`, { method: "DELETE" });
      if (active?.id === id) setActive(undefined);
      message.success("岗位已删除");
      await load();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "删除失败");
    }
  };
  const run = async () => {
    if (!active || matching || detailLoading) return;
    setMatching(true);
    setDetailError("");
    try {
      const result = await api<{ items: Match[]; hint?: string }>(
        `/api/jobs/${active.id}/search`,
        { method: "POST", body: JSON.stringify({ limit: 20 }) },
      );
      setMatches(result.items);
      setActive({ ...active, match_count: result.items.length });
      await load();
      if (!result.items.length)
        message.info("暂时没有合适人选，可补充简历或调整招聘需求");
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : "匹配暂时未完成，请重试");
    } finally {
      setMatching(false);
    }
  };
  return (
    <div className="page jobs-page">
      <StudioHeading
        number="02"
        label="ROLE COLLECTION"
        title="一份需求，"
        accent="一次精准相遇。"
        description="招聘岗位 / 把招聘条件整理成可持续推进的需求档案。"
        action={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            新建岗位
          </Button>
        }
      />
      <div className="role-workspace">
        <aside className="role-index">
          <span className="eyebrow">THE BRIEF COMES FIRST</span>
          <h2>
            先理解岗位，
            <br />
            <em>再发现人才。</em>
          </h2>
          <p>明确技能、地点与经验，让每次匹配都有方向。</p>
          <div className="role-total">
            <strong>{jobs.length.toString().padStart(2, "0")}</strong>
            <span>份招聘需求</span>
          </div>
          <button
            className="role-prompt"
            onClick={() => navigate("/", { state: { newSearch: Date.now() } })}
          >
            用一句话描述需求 <ArrowRightOutlined />
          </button>
          {error && (
            <Alert
              type="warning"
              showIcon
              message={error}
              action={<Button onClick={load}>重试</Button>}
            />
          )}
          <div className="jobs-summary">
            <button
              className={status === "all" ? "active" : ""}
              onClick={() => setStatus("all")}
            >
              全部岗位 <b>{jobs.length}</b>
            </button>
            <button
              className={status === "ready" ? "active" : ""}
              onClick={() => setStatus("ready")}
            >
              已有推荐 <b>{jobs.filter((job) => job.match_count > 0).length}</b>
            </button>
            <button
              className={status === "waiting" ? "active" : ""}
              onClick={() => setStatus("waiting")}
            >
              等待匹配 <b>{jobs.filter((job) => !job.match_count).length}</b>
            </button>
          </div>
        </aside>
        <section className="role-catalog">
          <div className="catalog-heading">
            <h2>岗位档案</h2>
            <span>需求 · 经验 · 推荐</span>
          </div>
          <div className="job-filter">
            <Input
              aria-label="搜索岗位"
              prefix={<SearchOutlined />}
              allowClear
              placeholder="搜索公司、岗位或地点"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Select
              aria-label="按行业筛选"
              allowClear
              placeholder="所有行业"
              value={industry}
              onChange={setIndustry}
              options={industries.map((value) => ({ value, label: value }))}
            />
            <Select
              aria-label="岗位排序"
              value={sort}
              onChange={setSort}
              options={[
                { value: "recent", label: "最近创建" },
                { value: "matches", label: "推荐人数" },
              ]}
            />
            <span>{filtered.length} 个岗位</span>
          </div>
          {loading ? (
            <Skeleton active />
          ) : (
            <div className="project-grid">
              {filtered.map((job, index) => (
                <article className="project-card role-dossier" key={job.id}>
                  <GlowingEffect />
                  <span className="dossier-number">
                    {String(index + 1).padStart(2, "0")}
                    <small>ROLE</small>
                  </span>
                  <div className="dossier-content">
                    <div className="project-card-top">
                      <span className="company-initial">
                        {(job.company || job.title).slice(0, 1)}
                      </span>
                      <Tag color={job.match_count ? "blue" : "default"}>
                        {job.match_count ? "已有推荐" : "等待匹配"}
                      </Tag>
                      <Popconfirm
                        title="删除岗位及其问答记录？"
                        onConfirm={() => remove(job.id)}
                      >
                        <Button
                          type="text"
                          aria-label={`删除岗位 ${job.title}`}
                          icon={<DeleteOutlined />}
                        />
                      </Popconfirm>
                    </div>
                    <span className="project-company">
                      {job.company || "自主招聘需求"}
                    </span>
                    <h2>
                      <button onClick={() => setActive(job)}>
                        {job.title}
                      </button>
                    </h2>
                    <p className="project-location">
                      <EnvironmentOutlined /> {job.location || "地点不限"}
                      <span>·</span>
                      {job.requirements?.minimum_years
                        ? `${job.requirements.minimum_years} 年以上`
                        : "经验不限"}
                    </p>
                    {!!job.requirements?.skills?.length && (
                      <div className="project-skills">
                        {(job.requirements?.skills || [])
                          .slice(0, 3)
                          .map((skill) => (
                            <Tag key={skill}>{skill}</Tag>
                          ))}
                      </div>
                    )}
                    <div className="project-card-footer">
                      <span>
                        <b>{job.match_count}</b> 位候选人
                      </span>
                      <div className="dossier-actions">
                        <Button type="primary" onClick={() => setActive(job)}>
                          {job.match_count ? "查看推荐" : "开始匹配"}{" "}
                          <ArrowRightOutlined />
                        </Button>
                        {job.conversation_id && (
                          <Button
                            type="text"
                            onClick={() =>
                              navigate("/", {
                                state: { conversationId: job.conversation_id },
                              })
                            }
                          >
                            继续问答
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                  <small className="project-date">
                    创建于{" "}
                    {new Date(job.created_at).toLocaleDateString("zh-CN")}
                  </small>
                </article>
              ))}
            </div>
          )}
          {!loading && !filtered.length && (
            <div className="panel collection-empty">
              <Empty
                description={
                  jobs.length ? "没有符合条件的岗位" : "从一份招聘需求开始"
                }
              />
              <Button
                onClick={() => {
                  if (jobs.length) {
                    setQuery("");
                    setIndustry(undefined);
                    setStatus("all");
                  } else setCreateOpen(true);
                }}
              >
                {jobs.length ? "清空筛选" : "创建第一个岗位"}
              </Button>
            </div>
          )}
        </section>
      </div>
      <Modal
        title="新建招聘岗位"
        open={pageActive && createOpen}
        onCancel={() => !saving && setCreateOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="保存岗位"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={create}>
          <Form.Item
            name="title"
            label="岗位名称"
            rules={[
              { required: true, whitespace: true, message: "请输入岗位名称" },
            ]}
          >
            <Input placeholder="例如：高级产品经理" maxLength={255} />
          </Form.Item>
          <div className="settings-grid">
            <Form.Item name="company" label="招聘公司">
              <Input placeholder="选填" maxLength={255} />
            </Form.Item>
            <Form.Item name="location" label="工作地点">
              <Input placeholder="选填，例如上海" />
            </Form.Item>
          </div>
          <Form.Item name="minimum_years" label="最低工作经验">
            <InputNumber min={0} max={50} addonAfter="年" placeholder="不限" />
          </Form.Item>
          <Form.Item name="skills" label="核心技能">
            <Input.TextArea
              placeholder="选填，用逗号分隔，如项目管理、客户拓展"
              autoSize={{ minRows: 2, maxRows: 4 }}
            />
          </Form.Item>
        </Form>
      </Modal>
      <Drawer
        title="岗位详情"
        open={pageActive && !!active}
        width={640}
        onClose={() => !matching && setActive(undefined)}
        closable={!matching}
        maskClosable={!matching}
      >
        {active && (
          <>
            <div className="job-detail-heading">
              <p className="eyebrow">{active.company || "招聘岗位"}</p>
              <h2>{active.title}</h2>
              <p>
                {active.location || "地点不限"} ·{" "}
                {active.requirements?.minimum_years
                  ? `${active.requirements.minimum_years} 年以上经验`
                  : "经验不限"}
              </p>
            </div>
            <div className="job-detail-criteria">
              <h3>招聘需求</h3>
              <p>
                {active.requirements?.skills?.join("、") || "尚未指定核心技能"}
              </p>
              {active.requirements?.must_have?.map((value) => (
                <p key={value}>{value}</p>
              ))}
            </div>
            <div className="job-detail-actions">
              <Button
                type="primary"
                loading={matching}
                disabled={detailLoading}
                onClick={run}
              >
                {matches.length ? "重新匹配人才" : "开始匹配人才"}
              </Button>
              {active.conversation_id && (
                <Button
                  disabled={matching}
                  onClick={() =>
                    navigate("/", {
                      state: { conversationId: active.conversation_id },
                    })
                  }
                >
                  继续问答 <ArrowRightOutlined />
                </Button>
              )}
            </div>
            {detailError && (
              <Alert type="warning" showIcon message={detailError} />
            )}
            <h3 className="detail-results-title">
              推荐人才 <span>{matches.length}</span>
            </h3>
            {detailLoading ? (
              <Skeleton active />
            ) : matches.length ? (
              matches.map((match) => (
                <article className="job-person" key={match.id}>
                  <div>
                    <span className="profile-initial">
                      {match.candidate.name.slice(0, 1)}
                    </span>
                    <span>
                      <strong>{match.candidate.name}</strong>
                      <small>
                        {match.candidate.current_title} ·{" "}
                        {match.candidate.location} ·{" "}
                        {match.candidate.years_experience} 年经验
                      </small>
                    </span>
                    <SaveCandidate id={match.candidate.id} compact />
                  </div>
                  <p>
                    {match.strengths.slice(0, 2).join("；") ||
                      "打开档案查看相关经历"}
                  </p>
                  <Button
                    type="link"
                    onClick={() => navigate(`/candidate/${match.candidate.id}`)}
                  >
                    查看简历依据 <ArrowRightOutlined />
                  </Button>
                </article>
              ))
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无推荐，点击上方按钮开始匹配"
              />
            )}
          </>
        )}
      </Drawer>
    </div>
  );
}
