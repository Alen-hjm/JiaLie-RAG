import { usePageActive, usePageRefresh } from "../components/WorkspacePages";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowRightOutlined,
  ArrowUpOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseOutlined,
  CodeOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Drawer,
  Empty,
  Input,
  Popconfirm,
  Skeleton,
  Spin,
  Tag,
  Tooltip,
  message,
} from "antd";
import type { TextAreaRef } from "antd/es/input/TextArea";
import { useLocation, useNavigate } from "react-router-dom";
import {
  api,
  Conversation,
  ConversationResponse,
  ConversationSummary,
  Match,
} from "../api";
import { HoverEffect } from "../components/ui/card-hover-effect";
import { BackgroundBeams } from "../components/ui/background-beams";
import { TextGenerateEffect } from "../components/ui/text-generate-effect";
import { GlowingEffect } from "../components/ui/glowing-effect";
import { TalentCanvas } from "../components/TalentCanvas";
import { SaveCandidate } from "../components/SaveCandidate";
import { usePreferences } from "../preferences";

const scenarios = [
  {
    title: "寻找技术骨干",
    description: "找到技术扎实，也懂业务的核心人才。",
    tag: "技术研发",
    icon: <CodeOutlined />,
    prompt:
      "寻找一位上海的高级 Java 开发工程师，5 年以上经验，熟悉 Spring Boot、微服务和高并发系统。",
  },
  {
    title: "发现管理人才",
    description: "从团队经验中，识别真正的领导力。",
    tag: "团队管理",
    icon: <TeamOutlined />,
    prompt:
      "要替上海的字节跳动找一个质量经理，具备团队管理经验，熟悉质量体系建设。",
  },
  {
    title: "匹配细分专家",
    description: "聚焦特定领域，让专业经验精准对接。",
    tag: "行业专家",
    icon: <FileSearchOutlined />,
    prompt: "寻找半导体行业的销售经理，有 Fab 客户拓展经验，工作地点优先上海。",
  },
];
type Stats = {
  candidate_count: number;
  processing_count: number;
  failed_count: number;
};
type Health = { model_mode: string; embedding_is_placeholder: boolean };
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "请求失败，请重试";

export default function SearchPage() {
  const pageActive = usePageActive();
  const reduced = useReducedMotion();
  const [motionPaused, setMotionPaused] = useState(false);
  const preferences = usePreferences();
  const navigate = useNavigate(),
    location = useLocation();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation>();
  const [input, setInput] = useState(""),
    [loading, setLoading] = useState(false);
  const [pendingUser, setPendingUser] = useState<string | null>(null),
    [elapsed, setElapsed] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false),
    [historyQuery, setHistoryQuery] = useState("");
  const [stats, setStats] = useState<Stats>();
  const [health, setHealth] = useState<Health>();
  const [loadError, setLoadError] = useState(""),
    [listLoading, setListLoading] = useState(true);
  const textarea = useRef<TextAreaRef>(null),
    threadEnd = useRef<HTMLDivElement>(null),
    busy = useRef(false);
  const refresh = async () => {
    if (!items.length) setListLoading(true);
    setLoadError("");
    try {
      const [history, counts, status] = await Promise.all([
        api<{ items: ConversationSummary[] }>("/api/conversations"),
        api<Stats>("/api/dashboard"),
        api<Health>("/api/health"),
      ]);
      setItems(history.items);
      setStats(counts);
      setHealth(status);
    } catch (error) {
      setLoadError(errorText(error));
    } finally {
      setListLoading(false);
    }
  };
  usePageRefresh(() => {
    void refresh();
  });
  useEffect(() => {
    if (!loading || !pageActive) {
      setElapsed(0);
      return;
    }
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [loading, pageActive]);
  useEffect(() => {
    if (pageActive && (conversation || pendingUser))
      threadEnd.current?.scrollIntoView({ block: "end" });
  }, [conversation, pendingUser]);
  const open = async (id: string) => {
    if (busy.current) return;
    busy.current = true;
    setLoading(true);
    try {
      setConversation(await api<Conversation>(`/api/conversations/${id}`));
      setInput("");
      setHistoryOpen(false);
    } catch (error) {
      message.error(errorText(error));
    } finally {
      busy.current = false;
      setLoading(false);
    }
  };
  const reset = () => {
    if (busy.current) {
      message.info("当前请求完成后即可新建搜索");
      return;
    }
    setConversation(undefined);
    setInput("");
    setPendingUser(null);
    window.scrollTo({ top: 0, behavior: "instant" });
    requestAnimationFrame(() =>
      textarea.current?.focus({ preventScroll: true }),
    );
  };
  useEffect(() => {
    const state = location.state as {
      conversationId?: string;
      newSearch?: number;
      prompt?: string;
    } | null;
    if (!pageActive || !state) return;
    if (state.conversationId) void open(state.conversationId);
    else if (state.newSearch) reset();
    else if (state.prompt) {
      setConversation(undefined);
      setInput(state.prompt);
      textarea.current?.focus();
    }
    navigate("/", { replace: true, state: null });
  }, [location.state]);
  const remove = async (id: string) => {
    if (busy.current) return;
    try {
      await api(`/api/conversations/${id}`, { method: "DELETE" });
      setItems((previous) => previous.filter((item) => item.id !== id));
      if (conversation?.id === id) setConversation(undefined);
      message.success("会话已删除");
    } catch (error) {
      message.error(errorText(error));
    }
  };
  const send = async (value = input) => {
    const text = value.trim();
    if (!text || busy.current) return;
    busy.current = true;
    setInput("");
    setLoading(true);
    setPendingUser(text);
    try {
      const active =
        conversation ||
        (await api<Conversation>("/api/conversations", { method: "POST" }));
      setConversation(active);
      await api(`/api/conversations/${active.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: text }),
      });
      const fresh = await api<Conversation>(`/api/conversations/${active.id}`);
      setConversation(fresh);
      setItems((previous) => [
        {
          id: fresh.id,
          title: fresh.title,
          requirements: fresh.requirements,
          updated_at: fresh.updated_at,
        },
        ...previous.filter((item) => item.id !== fresh.id),
      ]);
    } catch (error) {
      message.error(errorText(error));
      setInput(value);
    } finally {
      busy.current = false;
      setLoading(false);
      setPendingUser(null);
    }
  };
  const fill = (value: string) => {
    setInput(value);
    textarea.current?.focus({ cursor: "end" });
  };
  const active = !!conversation || !!pendingUser;
  const filtered = items.filter((item) =>
    `${item.title} ${item.requirements?.company || ""}`
      .toLowerCase()
      .includes(historyQuery.toLowerCase()),
  );
  return (
    <div className={`page search-page ${active ? "has-conversation" : ""}`}>
      <div className="search-topline">
        <span>
          <i /> TALENT INTELLIGENCE
        </span>
        <Button
          type="text"
          icon={<HistoryOutlined />}
          onClick={() => setHistoryOpen(true)}
        >
          历史会话 <span className="count-pill">{items.length}</span>
        </Button>
      </div>
      {loadError && (
        <Alert
          type="warning"
          showIcon
          message={`工作台数据暂未加载：${loadError}`}
          action={
            <Button size="small" onClick={refresh}>
              重试
            </Button>
          }
        />
      )}
      <div className={active ? "conversation-stage" : "discovery-stage"}>
        {!active && <BackgroundBeams paused={motionPaused || !pageActive} />}
        {!active ? (
          <>
            <section className="search-hero">
              <div className="hero-copy">
                <div className="hero-pill">
                  <ThunderboltOutlined /> 从需求出发 · 以经历为据
                </div>
                <h1>
                  <TextGenerateEffect
                    phrases={["看见人才，", "更看见可能。"]}
                  />
                </h1>
                <p>从一句招聘需求开始，在真实经历中找到合适的人。</p>
                <span className="hero-editorial">好的匹配，始于理解。</span>
              </div>
              <TalentCanvas
                onStart={() => fill("我想寻找一位 ")}
                onLibrary={() => navigate("/resumes")}
              />
            </section>
          </>
        ) : (
          <div className="conversation-heading">
            <div>
              <p className="eyebrow">TALENT CONVERSATION</p>
              <h1>{conversation?.title || "正在创建人才搜索"}</h1>
            </div>
            <Button icon={<PlusOutlined />} disabled={loading} onClick={reset}>
              新搜索
            </Button>
          </div>
        )}
        {active && (
          <section
            className="chat-thread"
            aria-label="招聘问答"
            aria-live="polite"
          >
            {(conversation?.messages || []).map((item, index) => (
              <div
                className={`chat-message ${item.role}`}
                key={item.id || index}
              >
                <div className="message-label">
                  {item.role === "user" ? (
                    "你"
                  ) : (
                    <>
                      <span className="assistant-star">✦</span> 嘉猎助手
                    </>
                  )}
                </div>
                <div className="bubble">{item.content}</div>
                {item.role === "assistant" && item.response?.items && (
                  <Recommendation
                    response={item.response}
                    navigate={navigate}
                    onFollowUp={send}
                    loading={loading}
                  />
                )}
              </div>
            ))}
            {pendingUser && (
              <div className="chat-message user">
                <div className="message-label">你</div>
                <div className="bubble">{pendingUser}</div>
              </div>
            )}
            {loading && (
              <div className="search-progress">
                <Spin size="small" />
                <span>
                  {pendingUser
                    ? [
                        "正在理解岗位需求",
                        "正在检索人才与证据",
                        "正在整理候选人推荐",
                      ][Math.min(Math.floor(elapsed / 6), 2)]
                    : "正在读取会话"}
                  <small>
                    {" "}
                    {elapsed}s ·{" "}
                    {pendingUser ? "完成后可查看匹配依据" : "请稍候"}
                  </small>
                </span>
              </div>
            )}
            <div ref={threadEnd} />
          </section>
        )}
        <section
          className={`search-composer ${active ? "is-sticky" : ""}`}
          aria-label="人才搜索输入"
        >
          <GlowingEffect />
          <div className="composer-input">
            <span className="composer-spark" aria-hidden="true">
              ✦
            </span>
            <Input.TextArea
              ref={textarea}
              aria-label="描述招聘需求"
              value={input}
              autoSize={{ minRows: active ? 2 : 3, maxRows: 7 }}
              disabled={loading}
              onChange={(event) => setInput(event.target.value)}
              onPressEnter={(event) => {
                if (
                  (preferences.sendShortcut === "modifier"
                    ? event.ctrlKey || event.metaKey
                    : !event.shiftKey) &&
                  !event.nativeEvent.isComposing &&
                  event.keyCode !== 229
                ) {
                  event.preventDefault();
                  void send();
                }
              }}
              placeholder={
                active
                  ? "继续细化需求，例如：只看上海，或放宽经验年限…"
                  : "试试：帮我找一位上海的质量经理，有团队管理经验…"
              }
            />
          </div>
          <div className="composer-footer">
            <Tooltip title="结合当前会话理解招聘条件，从已导入简历中检索。">
              <span className="retrieval-mode">
                <span className="status-dot" />
                人才库检索
              </span>
            </Tooltip>
            <div>
              <span className="keyboard-hint">
                {preferences.sendShortcut === "modifier"
                  ? "Ctrl / ⌘ + Enter 发送 · Enter 换行"
                  : "Enter 发送 · Shift + Enter 换行"}
              </span>
              <Button
                type="primary"
                aria-label="开始找人"
                icon={<ArrowUpOutlined />}
                disabled={!input.trim()}
                loading={loading}
                onClick={() => send()}
              >
                {active ? "发送" : "开始找人"}
              </Button>
            </div>
          </div>
        </section>
        {!active && (
          <div className="stage-bottom">
            <span>DESCRIBE THE ROLE. DISCOVER THE PERSON.</span>
            <button
              onClick={() => setMotionPaused((value) => !value)}
              disabled={!!reduced}
              aria-pressed={motionPaused || !!reduced}
            >
              {reduced
                ? "已跟随系统减少动态"
                : motionPaused
                  ? "播放光效"
                  : "暂停光效"}
              <span aria-hidden="true">
                {motionPaused || reduced ? "▷" : "Ⅱ"}
              </span>
            </button>
          </div>
        )}
      </div>
      {!active && (
        <>
          <div className="search-trust">
            <SafetyCertificateOutlined /> 仅检索授权简历<span>·</span>
            推荐结论可追溯<span>·</span>敏感属性不参与排名
          </div>
          <section className="scenario-section">
            <div className="section-heading">
              <h2>为下一次招聘，打开思路</h2>
              <span>选择场景，补充你的具体需求</span>
            </div>
            <HoverEffect
              items={scenarios}
              onSelect={(index) => fill(scenarios[index].prompt)}
            />
          </section>
          <section className="workspace-overview">
            <div className="section-heading">
              <h2>你的招聘工作空间</h2>
              <button onClick={() => navigate("/dashboard")}>
                查看招聘概览 <ArrowRightOutlined />
              </button>
            </div>
            <div className="overview-grid">
              <button
                className="library-overview"
                onClick={() => navigate("/resumes")}
              >
                <div className="overview-icon">
                  <TeamOutlined />
                </div>
                <div>
                  <span>
                    {stats?.candidate_count
                      ? "你的专属人才库"
                      : "建立你的专属人才库"}
                  </span>
                  <strong>
                    {stats ? stats.candidate_count.toLocaleString() : "—"}
                    <small>份可检索档案</small>
                  </strong>
                </div>
                <ArrowRightOutlined />
                <p>
                  {stats?.processing_count
                    ? `${stats.processing_count} 份简历正在处理`
                    : "每一份经历，都值得被发现"}
                  {stats?.failed_count
                    ? ` · ${stats.failed_count} 份需关注`
                    : ""}
                </p>
              </button>
              <div className="recent-overview">
                <div className="recent-heading">
                  <span>
                    <ClockCircleOutlined /> 最近搜索
                  </span>
                  <button onClick={() => setHistoryOpen(true)}>
                    查看全部 <ArrowRightOutlined />
                  </button>
                </div>
                {listLoading ? (
                  <Skeleton active paragraph={{ rows: 1 }} title={false} />
                ) : items.length ? (
                  items.slice(0, 2).map((item) => (
                    <button
                      className="recent-search-row"
                      key={item.id}
                      disabled={loading}
                      onClick={() => open(item.id)}
                    >
                      <span className="recent-row-icon">
                        <SearchOutlined />
                      </span>
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.requirements?.locations?.join("、") ||
                            "不限地点"}{" "}
                          ·{" "}
                          {new Date(item.updated_at).toLocaleDateString(
                            "zh-CN",
                          )}
                        </small>
                      </span>
                      <ArrowRightOutlined />
                    </button>
                  ))
                ) : (
                  <div className="recent-empty">
                    <span>下一次人才发现，从这里开始</span>
                    <small>发起搜索后，会话将在这里自动保存。</small>
                  </div>
                )}
              </div>
            </div>
          </section>
          <footer className="search-bottom">
            <span>
              JIALIE <i> / </i> 看见经验背后的价值
            </span>
            <span>
              为更好的招聘决策而设计 <span className="tiny-star">✦</span>
            </span>
          </footer>
        </>
      )}
      {health &&
        (health.model_mode === "mock" || health.embedding_is_placeholder) && (
          <div className="runtime-note">
            体验模式 · 当前结果仅用于功能体验，正式使用请联系服务负责人开通。
          </div>
        )}
      <Drawer
        title="历史会话"
        open={pageActive && historyOpen}
        onClose={() => setHistoryOpen(false)}
        width={420}
      >
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索岗位或公司"
          value={historyQuery}
          onChange={(event) => setHistoryQuery(event.target.value)}
        />
        <div className="history-list">
          {filtered.map((item) => (
            <div
              key={item.id}
              className={conversation?.id === item.id ? "active" : ""}
            >
              <button disabled={loading} onClick={() => open(item.id)}>
                <strong>{item.title}</strong>
                <small>
                  {item.requirements?.company || "未指定公司"} ·{" "}
                  {new Date(item.updated_at).toLocaleDateString("zh-CN")}
                </small>
              </button>
              <Popconfirm
                title="删除会话及对应岗位？"
                onConfirm={() => remove(item.id)}
              >
                <Button
                  disabled={loading}
                  type="text"
                  aria-label={`删除会话 ${item.title}`}
                  icon={<DeleteOutlined />}
                />
              </Popconfirm>
            </div>
          ))}
          {!filtered.length && (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={historyQuery ? "没有匹配的会话" : "还没有搜索记录"}
            />
          )}
        </div>
      </Drawer>
    </div>
  );
}

function Recommendation({
  response,
  navigate,
  onFollowUp,
  loading,
}: {
  response: ConversationResponse;
  navigate: (path: string) => void;
  onFollowUp: (text: string) => void;
  loading: boolean;
}) {
  const preferences = usePreferences();
  const [visible, setVisible] = useState<number>(preferences.resultsPerPage);
  const suggestions = [
    !response.requirements?.management_required ? "希望有团队管理经验" : "",
    (response.requirements?.minimum_years || 0) > 2
      ? `把最低经验放宽到 ${response.requirements!.minimum_years - 2} 年`
      : "",
    response.requirements?.skills?.[0]
      ? `优先有${response.requirements.skills[0]}实际项目经验的人`
      : "",
  ].filter(Boolean);
  useEffect(
    () => setVisible(preferences.resultsPerPage),
    [preferences.resultsPerPage, response],
  );
  return (
    <div className="recommendation">
      <div className="requirement-tags">
        {response.requirements?.company && (
          <Tag>{response.requirements.company}</Tag>
        )}
        {response.requirements?.title && (
          <Tag color="blue">{response.requirements.title}</Tag>
        )}
        {response.requirements?.locations?.map((value) => (
          <Tag key={value}>{value}</Tag>
        ))}
      </div>
      <div className="recommendation-list">
        {(response.items || []).slice(0, visible).map((match, index) => (
          <MatchCard
            key={match.id}
            match={match}
            index={index}
            navigate={navigate}
          />
        ))}
      </div>
      {(response.items?.length || 0) > visible && (
        <Button
          className="more-candidates"
          onClick={() =>
            setVisible((count) => count + preferences.resultsPerPage)
          }
        >
          查看更多候选人（还有 {(response.items?.length || 0) - visible} 位）
        </Button>
      )}
      {response.items?.length === 0 && (
        <div className="no-matches">
          <SearchOutlined />
          <b>暂时没有符合条件的人才</b>
          <span>可以尝试放宽地点、年限，或导入更多简历。</span>
        </div>
      )}
      <div className="followups">
        {!!suggestions.length && <span>继续细化需求</span>}
        {suggestions.map((value) => (
          <Button
            disabled={loading}
            key={value}
            onClick={() => onFollowUp(value)}
          >
            {value}
            <ArrowRightOutlined />
          </Button>
        ))}
      </div>
    </div>
  );
}

function MatchCard({
  match,
  index,
  navigate,
}: {
  match: Match;
  index: number;
  navigate: (path: string) => void;
}) {
  const reduced = useReducedMotion();
  const preferences = usePreferences();
  const [expanded, setExpanded] = useState(preferences.expandEvidence);
  useEffect(
    () => setExpanded(preferences.expandEvidence),
    [preferences.expandEvidence],
  );
  return (
    <article className="talent-match">
      <div className="talent-match-header">
        <div className="candidate-avatar">
          {match.candidate.name.slice(0, 1)}
        </div>
        <div>
          <span className="match-rank">
            CANDIDATE {String(index + 1).padStart(2, "0")}
          </span>
          <h3>{match.candidate.name}</h3>
          <p>
            {match.candidate.current_title || "职位未识别"} ·{" "}
            {match.candidate.location || "所在地未识别"} ·{" "}
            {match.candidate.years_experience} 年经验
          </p>
        </div>
        <SaveCandidate id={match.candidate.id} />
        <div className="match-score">
          <strong>
            {Math.round(match.total_score)}
            <small>分</small>
          </strong>
          <span>匹配参考</span>
        </div>
      </div>
      <div className="tag-line">
        {match.candidate.skills.slice(0, 5).map((value) => (
          <Tag key={value}>{value}</Tag>
        ))}
      </div>
      <div className="match-insights">
        <div>
          <b>
            <CheckCircleFilled /> 匹配亮点
          </b>
          <p>{match.strengths.slice(0, 2).join("；") || "存在相关检索证据"}</p>
        </div>
        <div>
          <b>
            <WarningOutlined /> 待核实信息
          </b>
          <p>
            {match.gaps.slice(0, 2).join("；") ||
              "暂未发现关键缺口，建议结合面试核实"}
          </p>
        </div>
      </div>
      <div className="match-actions">
        <button onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
          {expanded ? <CloseOutlined /> : <FileSearchOutlined />}
          {expanded
            ? "收起原文证据"
            : `查看原文证据 (${match.evidence.length})`}
        </button>
        <Button
          type="text"
          onClick={() => navigate(`/candidate/${match.candidate.id}`)}
        >
          完整人才档案 <ArrowRightOutlined />
        </Button>
      </div>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="evidence-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: reduced ? 0 : 0.3,
              ease: [0.16, 1, 0.3, 1],
            }}
            style={{ overflow: "hidden" }}
          >
            {match.evidence.length ? (
              match.evidence.map((evidence, i) => (
                <blockquote key={`${evidence.chunk_id}-${i}`}>
                  <small>
                    {evidence.section}
                    {evidence.page_number
                      ? ` · 第 ${evidence.page_number} 页`
                      : ""}
                  </small>
                  {evidence.quote}
                </blockquote>
              ))
            ) : (
              <p className="muted">暂无可展示的原文引用。</p>
            )}
            <small className="muted">
              匹配度用于辅助筛选，不代表录用结论。
            </small>
          </motion.div>
        )}
      </AnimatePresence>
    </article>
  );
}
