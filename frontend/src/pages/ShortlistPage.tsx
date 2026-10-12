import { StudioHeading } from "../components/StudioHeading";
import { GlowingEffect } from "../components/ui/glowing-effect";
import { usePageActive } from "../components/WorkspacePages";
import { useEffect, useState } from "react";
import {
  ArrowRightOutlined,
  ColumnWidthOutlined,
  SearchOutlined,
  StarOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Input,
  Modal,
  Skeleton,
  Tag,
} from "antd";
import { useNavigate } from "react-router-dom";
import { api, ApiFailure, Candidate } from "../api";
import { useShortlist } from "../shortlist";
import { SaveCandidate } from "../components/SaveCandidate";

type Profile = Candidate & { highlights: string[] };
export default function ShortlistPage() {
  const pageActive = usePageActive();
  const ids = useShortlist(),
    navigate = useNavigate();
  const [profiles, setProfiles] = useState<Profile[]>([]),
    [missing, setMissing] = useState<string[]>([]);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [refresh, setRefresh] = useState(0);
  const [query, setQuery] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [comparing, setComparing] = useState(false);
  useEffect(() => {
    if (!pageActive) return;
    let active = true;
    if (!profiles.length) setLoading(true);
    setError("");
    Promise.allSettled(
      ids.map((id) => api<Profile>(`/api/candidates/${id}`)),
    ).then((results) => {
      if (!active) return;
      setProfiles(
        results.flatMap((result) =>
          result.status === "fulfilled" ? [result.value] : [],
        ),
      );
      setMissing(
        results.flatMap((result, i) =>
          result.status === "rejected" &&
          result.reason instanceof ApiFailure &&
          result.reason.status === 404
            ? [ids[i]]
            : [],
        ),
      );
      if (
        results.some(
          (result) =>
            result.status === "rejected" &&
            !(
              result.reason instanceof ApiFailure &&
              result.reason.status === 404
            ),
        )
      )
        setError("部分档案暂时无法加载，请稍后重试。");
      setSelected((previous) => previous.filter((id) => ids.includes(id)));
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [ids, refresh, pageActive]);
  const visible = profiles.filter((profile) =>
    `${profile.name} ${profile.current_title || ""} ${profile.location || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const compared = profiles.filter((profile) => selected.includes(profile.id));
  return (
    <div className="page shortlist-page">
      <StudioHeading
        number="04"
        label="THE SHORTLIST"
        title="从值得关注，"
        accent="到值得一谈。"
        description="我的收藏 / 并排看清经历，让下一步沟通更有方向。"
        action={
          <Button icon={<SearchOutlined />} onClick={() => navigate("/")}>
            继续发现人才
          </Button>
        }
      />
      <section className="selection-desk">
        <div className="selection-intro">
          <span className="eyebrow">MAKE ROOM FOR THE RIGHT PEOPLE</span>
          <h2>
            把人选放在一起，
            <br />
            <em>把差异看得更清。</em>
          </h2>
          <p>选择 2–3 位人才，对比经验、技能与履历亮点。</p>
        </div>
        <div className="selection-slots">
          {[0, 1, 2].map((index) => {
            const profile = compared[index];
            return (
              <div
                key={index}
                className={`selection-slot ${profile ? "filled" : ""}`}
              >
                <span>
                  {profile
                    ? profile.name.slice(0, 1)
                    : String(index + 1).padStart(2, "0")}
                </span>
                <strong>{profile?.name || "待选人选"}</strong>
                {profile ? (
                  <button
                    aria-label={`移除对比 ${profile.name}`}
                    onClick={() =>
                      setSelected((previous) =>
                        previous.filter((id) => id !== profile.id),
                      )
                    }
                  >
                    移除
                  </button>
                ) : (
                  <small>从下方名单选择</small>
                )}
              </div>
            );
          })}
        </div>
      </section>
      <div className="collection-note">
        <StarOutlined />
        <span>
          我的收藏 ·
          保存在当前浏览器，清除浏览器数据后会重置。人才资料以最新档案为准。
        </span>
      </div>
      {error && (
        <Alert
          showIcon
          type="warning"
          message={error}
          action={
            <Button onClick={() => setRefresh((value) => value + 1)}>
              重试
            </Button>
          }
        />
      )}
      <div className="collection-toolbar">
        <strong className="collection-total">
          {profiles.length}
          <small>位收藏</small>
        </strong>
        <Input
          aria-label="搜索收藏"
          prefix={<SearchOutlined />}
          allowClear
          placeholder="搜索姓名、职位或地点"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <span>选择 2–3 位人才进行对比</span>
        <Button
          icon={<ColumnWidthOutlined />}
          disabled={compared.length < 2}
          onClick={() => setComparing(true)}
        >
          对比人才 ({compared.length}/3)
        </Button>
      </div>
      {loading ? (
        <Skeleton active />
      ) : (
        <div className="saved-grid">
          {visible.map((profile) => (
            <article
              className={`saved-card ${selected.includes(profile.id) ? "is-selected" : ""}`}
              key={profile.id}
            >
              <GlowingEffect />
              <div className="saved-card-top">
                <Checkbox
                  aria-label={`选择 ${profile.name} 进行对比`}
                  checked={selected.includes(profile.id)}
                  disabled={
                    selected.length >= 3 && !selected.includes(profile.id)
                  }
                  onChange={(event) =>
                    setSelected((previous) =>
                      event.target.checked
                        ? [...previous, profile.id]
                        : previous.filter((id) => id !== profile.id),
                    )
                  }
                />
                <SaveCandidate id={profile.id} />
              </div>
              <div className="saved-profile">
                <span className="profile-initial">
                  {profile.name.slice(0, 1)}
                </span>
                <div>
                  <h2>{profile.name}</h2>
                  <p>{profile.current_title || "职位未填写"}</p>
                </div>
              </div>
              <div className="saved-meta">
                <span>{profile.location || "地点未填写"}</span>
                <span>{profile.years_experience} 年经验</span>
              </div>
              <div className="saved-skills">
                {profile.skills.slice(0, 4).map((skill) => (
                  <Tag key={skill}>{skill}</Tag>
                ))}
              </div>
              <p className="saved-highlight">
                {profile.highlights[0] ||
                  "查看完整档案，进一步了解候选人的工作经历。"}
              </p>
              <Button
                block
                type="text"
                onClick={() => navigate(`/candidate/${profile.id}`)}
              >
                查看完整档案 <ArrowRightOutlined />
              </Button>
            </article>
          ))}
        </div>
      )}
      {!loading && !visible.length && (
        <div className="panel collection-empty">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={query ? "没有找到符合条件的收藏" : "还没有收藏人才"}
          />
          <p>
            {query
              ? "试试其他关键词，或清空搜索。"
              : "在推荐结果或人才库中点击星标，把值得关注的人留在这里。"}
          </p>
          <Button onClick={() => (query ? setQuery("") : navigate("/"))}>
            {query ? "清空搜索" : "开始找人"}
          </Button>
        </div>
      )}
      {missing.length > 0 && (
        <div className="missing-profiles">
          <p>以下 {missing.length} 份收藏档案已不存在，可取消收藏。</p>
          {missing.map((id) => (
            <div key={id}>
              <span>已失效的档案</span>
              <SaveCandidate id={id} />
            </div>
          ))}
        </div>
      )}
      <Modal
        className="compare-modal"
        title="并排看清每一份经历"
        width={1020}
        open={pageActive && comparing}
        onCancel={() => setComparing(false)}
        footer={<Button onClick={() => setComparing(false)}>完成对比</Button>}
      >
        <p className="muted">
          根据简历中的客观信息对比；未填写的内容建议在沟通中核实。
        </p>
        <div className="comparison-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>人才信息</th>
                {compared.map((profile) => (
                  <th key={profile.id}>
                    {profile.name}
                    <small>{profile.current_title || "职位未填写"}</small>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ["所在地", (p: Profile) => p.location || "未填写"],
                ["工作经验", (p: Profile) => `${p.years_experience} 年`],
                [
                  "行业经历",
                  (p: Profile) => p.industries.join("、") || "未填写",
                ],
                ["专业技能", (p: Profile) => p.skills.join("、") || "未填写"],
                [
                  "管理经历",
                  (p: Profile) =>
                    p.management_experience
                      ? "简历中有相关经历"
                      : "待进一步核实",
                ],
                [
                  "履历亮点",
                  (p: Profile) => p.highlights.join("；") || "暂无明确记录",
                ],
              ].map(([label, render]) => (
                <tr key={label as string}>
                  <th>{label as string}</th>
                  {compared.map((profile) => (
                    <td key={profile.id}>
                      {(render as (p: Profile) => string)(profile)}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <th>进一步了解</th>
                {compared.map((profile) => (
                  <td key={profile.id}>
                    <Button
                      type="link"
                      onClick={() => navigate(`/candidate/${profile.id}`)}
                    >
                      打开档案 <ArrowRightOutlined />
                    </Button>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Modal>
    </div>
  );
}
