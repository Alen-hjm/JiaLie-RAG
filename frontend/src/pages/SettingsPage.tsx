import { StudioHeading } from "../components/StudioHeading";
import { ModelConnection } from "../components/ModelConnection";
import { useState } from "react";
import { Button, Radio, Switch, message } from "antd";
import {
  CheckOutlined,
  FileSearchOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import {
  defaultPreferences,
  Preferences,
  readPreferences,
  savePreferences,
} from "../preferences";

export default function SettingsPage() {
  const [section, setSection] = useState<"preferences" | "connection">(
    "preferences",
  );
  const [saved, setSaved] = useState(readPreferences);
  const [draft, setDraft] = useState<Preferences>(saved);
  const dirty = JSON.stringify(saved) !== JSON.stringify(draft);
  const save = () => {
    try {
      savePreferences(draft);
      setSaved({ ...draft });
      message.success("使用偏好已保存");
    } catch {
      message.error("浏览器暂时无法保存，请检查是否禁用了本地存储后重试。");
    }
  };
  return (
    <div className="page settings-page customer-settings">
      <StudioHeading
        number="05"
        label="YOUR WAY OF WORKING"
        title="适合你的，"
        accent="工作节奏。"
        description="工作台设置 / 只调整看得见、用得上的习惯。"
      />
      <div className="settings-tabs" role="tablist" aria-label="设置分类">
        <button
          role="tab"
          aria-selected={section === "preferences"}
          onClick={() => setSection("preferences")}
        >
          使用偏好
        </button>
        <button
          role="tab"
          aria-selected={section === "connection"}
          onClick={() => setSection("connection")}
        >
          模型接入 <span>服务管理</span>
        </button>
      </div>
      {section === "connection" ? (
        <ModelConnection />
      ) : (
        <>
          <div className="settings-workspace">
            <aside className="preference-preview">
              <span className="eyebrow">LIVE PREVIEW / 即时预览</span>
              <h2>
                让工具，
                <br />
                跟上你的习惯。
              </h2>
              <div className="preview-message">
                <span>✦</span>
                <p>帮我寻找一位有团队管理经验的产品经理…</p>
                <kbd>
                  {draft.sendShortcut === "enter"
                    ? "Enter ↵"
                    : "Ctrl / ⌘ + Enter ↵"}
                </kbd>
              </div>
              <div className="preview-result">
                <div>
                  <span>推荐展示</span>
                  <strong>
                    {draft.resultsPerPage}
                    <small>位 / 次</small>
                  </strong>
                </div>
                <div className="preview-lines">
                  <i />
                  <i />
                  <i />
                </div>
                <p>
                  {draft.expandEvidence
                    ? "原文证据将随推荐一起展开"
                    : "需要时，点击查看原文证据"}
                </p>
              </div>
              <span className="preview-scope">
                <SettingOutlined /> 当前浏览器生效 · 保存后应用
              </span>
            </aside>
            <div className="preferences-controls">
              <section className="panel preferences-panel">
                <div className="preferences-section-title">
                  <span>
                    <MessageOutlined />
                  </span>
                  <div>
                    <h2>对话习惯</h2>
                    <p>选择你习惯的发送方式，避免长段需求误发送。</p>
                  </div>
                </div>
                <div className="preference-row">
                  <div>
                    <h3>发送消息快捷键</h3>
                    <p>输入框下方会显示当前使用的快捷键。</p>
                  </div>
                  <Radio.Group
                    aria-label="发送消息快捷键"
                    value={draft.sendShortcut}
                    onChange={(event) =>
                      setDraft({ ...draft, sendShortcut: event.target.value })
                    }
                  >
                    <Radio value="enter">
                      Enter 发送<small>Shift + Enter 换行</small>
                    </Radio>
                    <Radio value="modifier">
                      Ctrl / ⌘ + Enter 发送<small>Enter 直接换行</small>
                    </Radio>
                  </Radio.Group>
                </div>
              </section>
              <section className="panel preferences-panel">
                <div className="preferences-section-title">
                  <span>
                    <FileSearchOutlined />
                  </span>
                  <div>
                    <h2>推荐结果</h2>
                    <p>用更舒服的方式浏览人才，随时回到简历核实。</p>
                  </div>
                </div>
                <div className="preference-row">
                  <div>
                    <h3>每次展示的候选人数</h3>
                    <p>只影响展示数量，不改变匹配结果；其余推荐可继续展开。</p>
                  </div>
                  <Radio.Group
                    optionType="button"
                    buttonStyle="solid"
                    aria-label="每次展示的候选人数"
                    value={draft.resultsPerPage}
                    onChange={(event) =>
                      setDraft({ ...draft, resultsPerPage: event.target.value })
                    }
                    options={[
                      { label: "5 位", value: 5 },
                      { label: "10 位", value: 10 },
                    ]}
                  />
                </div>
                <div className="preference-row">
                  <div>
                    <h3>自动展开简历证据</h3>
                    <p>打开会话时，直接展示推荐所依据的原文。</p>
                  </div>
                  <Switch
                    aria-label="自动展开简历证据"
                    checked={draft.expandEvidence}
                    onChange={(value) =>
                      setDraft({ ...draft, expandEvidence: value })
                    }
                  />
                </div>
              </section>
              <div className="preferences-actions">
                <Button
                  type="text"
                  onClick={() => setDraft({ ...defaultPreferences })}
                >
                  恢复默认
                </Button>
                <span>
                  {dirty ? (
                    "有尚未保存的修改"
                  ) : (
                    <>
                      <CheckOutlined /> 偏好已同步
                    </>
                  )}
                </span>
                <Button type="primary" disabled={!dirty} onClick={save}>
                  保存偏好
                </Button>
              </div>
            </div>
          </div>
          <aside className="preferences-note">
            <SafetyCertificateOutlined />
            <div>
              <strong>安心使用，专注招聘</strong>
              <p>
                仅导入已获授权的简历。推荐用于辅助筛选，最终判断由你做出。服务由工作台统一维护，无需额外配置。
              </p>
              <small>偏好保存在当前浏览器；清除浏览器数据后将恢复默认。</small>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
