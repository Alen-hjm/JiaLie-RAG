import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  message,
} from "antd";
import {
  ApiOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { api, AppSettings } from "../api";
import { usePageActive } from "./WorkspacePages";

const chatPresets = {
  deepseek: {
    label: "DeepSeek",
    mode: "deepseek",
    url: "https://api.deepseek.com",
    model: "deepseek-chat",
  },
  dashscope: {
    label: "阿里云百炼",
    mode: "openai",
    url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
  },
  siliconflow: {
    label: "硅基流动",
    mode: "openai",
    url: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V3",
  },
  zhipu: {
    label: "智谱",
    mode: "openai",
    url: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-plus",
  },
  openai: {
    label: "OpenAI",
    mode: "openai",
    url: "https://api.openai.com/v1",
    model: "",
  },
  custom: { label: "自定义兼容接口", mode: "openai", url: "", model: "" },
  mock: {
    label: "离线演示",
    mode: "mock",
    url: "https://api.deepseek.com",
    model: "deepseek-chat",
  },
};
const embeddingPresets = {
  siliconflow: {
    label: "硅基流动",
    provider: "siliconflow",
    url: "https://api.siliconflow.cn/v1",
    model: "BAAI/bge-m3",
    dimensions: 1024,
  },
  dashscope: {
    label: "阿里云百炼",
    provider: "dashscope",
    url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "text-embedding-v3",
    dimensions: 1024,
  },
  zhipu: {
    label: "智谱",
    provider: "zhipu",
    url: "https://open.bigmodel.cn/api/paas/v4",
    model: "embedding-3",
    dimensions: 1024,
  },
  openai: {
    label: "OpenAI",
    provider: "openai",
    url: "https://api.openai.com/v1",
    model: "text-embedding-3-small",
    dimensions: 1536,
  },
  custom: {
    label: "自定义兼容接口",
    provider: "custom",
    url: "",
    model: "",
    dimensions: 1536,
  },
  hash: {
    label: "离线演示（无语义检索）",
    provider: "hash",
    url: "",
    model: "deterministic-hash-v1",
    dimensions: 1536,
  },
};
type Values = {
  chatPreset: keyof typeof chatPresets;
  embeddingPreset: keyof typeof embeddingPresets;
  base_url: string;
  chat_model: string;
  api_key?: string;
  embedding_base_url: string;
  embedding_model: string;
  embedding_api_key?: string;
  embedding_dimensions: number;
};
type Report = {
  ok: boolean;
  detail: {
    chat: { ok: boolean; message: string };
    embedding: { ok: boolean; message: string; placeholder: boolean };
  };
};
const urlRule = {
  validator: async (_: unknown, value: string) => {
    try {
      const u = new URL(value);
      if (
        !["https:", "http:"].includes(u.protocol) ||
        u.username ||
        u.password ||
        u.search ||
        u.hash
      )
        throw Error();
    } catch {
      throw Error("请输入完整服务地址，不含密钥、查询参数或 /chat/completions");
    }
    if (/\/(chat\/completions|embeddings)\/?$/.test(value))
      throw Error("填写服务根地址，例如 https://example.com/v1");
  },
};

export function ModelConnection() {
  const [form] = Form.useForm<Values>(),
    active = usePageActive();
  const [saved, setSaved] = useState<AppSettings>(),
    [busy, setBusy] = useState<"load" | "test" | "save" | null>("load"),
    [error, setError] = useState("");
  const [report, setReport] = useState<Report>(),
    [tested, setTested] = useState(false);
  const chat = Form.useWatch("chatPreset", form),
    embedding = Form.useWatch("embeddingPreset", form);
  const apply = (data: AppSettings) => {
    setSaved(data);
    const chatPreset =
      data.model_mode === "mock"
        ? "mock"
        : (Object.keys(chatPresets) as (keyof typeof chatPresets)[]).find(
            (key) =>
              key !== "mock" &&
              key !== "custom" &&
              chatPresets[key].url === data.base_url,
          ) || "custom";
    const embeddingPreset =
      data.embedding_is_placeholder && data.embedding_provider === "hash"
        ? "hash"
        : (
            Object.keys(embeddingPresets) as (keyof typeof embeddingPresets)[]
          ).find(
            (key) =>
              key !== "hash" &&
              key !== "custom" &&
              embeddingPresets[key].url === data.embedding_base_url &&
              embeddingPresets[key].provider === data.embedding_provider,
          ) || "custom";
    form.setFieldsValue({
      chatPreset,
      embeddingPreset,
      base_url: data.base_url,
      chat_model: data.chat_model,
      api_key: "",
      embedding_base_url: data.embedding_base_url,
      embedding_model: data.embedding_model,
      embedding_dimensions: data.embedding_dimensions,
      embedding_api_key: "",
    });
  };
  const load = async () => {
    setBusy("load");
    setError("");
    try {
      apply(await api<AppSettings>("/api/settings"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "配置读取失败");
    } finally {
      setBusy(null);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (!active) {
      form.setFieldsValue({ api_key: "", embedding_api_key: "" });
      setTested(false);
      setReport(undefined);
    }
  }, [active, form]);
  const payload = (v: Values) => ({
    model_mode: chatPresets[v.chatPreset].mode,
    base_url: v.base_url,
    chat_model: v.chat_model,
    api_key: v.api_key || undefined,
    embedding_provider: embeddingPresets[v.embeddingPreset].provider,
    embedding_mode: v.embeddingPreset === "hash" ? "hash" : "real",
    embedding_base_url: v.embedding_base_url,
    embedding_model: v.embedding_model,
    embedding_dimensions: v.embedding_dimensions,
    embedding_api_key: v.embedding_api_key || undefined,
  });
  const test = async () => {
    try {
      const values = await form.validateFields();
      setBusy("test");
      setError("");
      setReport(undefined);
      setTested(false);
      const result = await api<Report>("/api/settings/test-connection", {
        method: "POST",
        body: JSON.stringify(payload(values)),
      });
      setReport(result);
      setTested(
        (values.chatPreset === "mock" || result.detail.chat.ok) &&
          (values.embeddingPreset === "hash" || result.detail.embedding.ok),
      );
    } catch (e) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    try {
      const values = await form.validateFields();
      setBusy("save");
      setError("");
      apply(
        await api<AppSettings>("/api/settings", {
          method: "PUT",
          body: JSON.stringify(payload(values)),
        }),
      );
      setTested(false);
      message.success("服务配置已保存，密钥输入已清空");
    } catch (e) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setBusy(null);
    }
  };
  const changed = () => {
    setTested(false);
    setReport(undefined);
  };
  return (
    <section className="model-connection">
      <div className="connection-intro">
        <span>
          <ApiOutlined /> 服务管理
        </span>
        <h2>连接你的智能招聘引擎。</h2>
        <p>
          支持多家服务和自定义 OpenAI
          兼容接口。对话负责理解需求，检索负责理解简历；两者可独立选择。预设模型可修改，请以服务商账户实际可用模型为准。
        </p>
        <div>
          <Tag>
            {saved?.model_mode === "mock"
              ? "对话：离线演示"
              : saved
                ? `对话：${saved.chat_model}`
                : "正在读取配置"}
          </Tag>
          <Tag>
            {saved?.embedding_is_placeholder
              ? "检索：演示模式"
              : saved
                ? `检索：${saved.embedding_model}`
                : ""}
          </Tag>
        </div>
      </div>
      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button onClick={load} disabled={!!busy}>
              重新读取
            </Button>
          }
        />
      )}
      <Form
        form={form}
        layout="vertical"
        disabled={!!busy || !saved}
        onValuesChange={changed}
        autoComplete="off"
      >
        <div className="connection-columns">
          <section className="connection-panel">
            <span className="connection-step">01 / 理解招聘需求</span>
            <h3>对话服务</h3>
            <Form.Item
              name="chatPreset"
              label="服务商"
              rules={[{ required: true }]}
            >
              <Select
                aria-label="服务商"
                options={Object.entries(chatPresets).map(([value, p]) => ({
                  value,
                  label: p.label,
                }))}
                onChange={(key) => {
                  const p = chatPresets[key as keyof typeof chatPresets];
                  form.setFieldsValue({
                    base_url: p.url,
                    chat_model: p.model,
                    api_key: "",
                  });
                  changed();
                }}
              />
            </Form.Item>
            {chat !== "mock" && (
              <>
                <Form.Item
                  name="base_url"
                  label="服务地址"
                  rules={[
                    { required: true, message: "请输入服务地址" },
                    urlRule,
                  ]}
                >
                  <Input placeholder="https://example.com/v1" />
                </Form.Item>
                <Form.Item
                  name="chat_model"
                  label="模型名称"
                  rules={[
                    {
                      required: true,
                      whitespace: true,
                      message: "请输入模型名称",
                    },
                  ]}
                >
                  <Input placeholder="填写服务商提供的模型 ID" />
                </Form.Item>
                <Form.Item
                  name="api_key"
                  label="API Key"
                  extra={
                    saved?.api_key_configured
                      ? "服务器已有密钥。留空保留，更换服务商时请填写对应密钥。"
                      : "密钥仅发送到服务端保存，不写入浏览器存储。"
                  }
                  rules={[
                    {
                      required: !saved?.api_key_configured,
                      message: "请输入对话服务密钥",
                    },
                  ]}
                >
                  <Input.Password
                    autoComplete="new-password"
                    placeholder={
                      saved?.api_key_configured
                        ? "已配置 · 留空保留"
                        : "输入服务商密钥"
                    }
                  />
                </Form.Item>
              </>
            )}
            {chat === "mock" && (
              <p className="connection-help">
                离线演示仅用于体验流程，不代表真实模型能力。
              </p>
            )}
          </section>
          <section className="connection-panel">
            <span className="connection-step">02 / 理解简历经历</span>
            <h3>语义检索服务</h3>
            <Form.Item
              name="embeddingPreset"
              label="检索服务商"
              rules={[{ required: true }]}
            >
              <Select
                aria-label="检索服务商"
                options={Object.entries(embeddingPresets).map(([value, p]) => ({
                  value,
                  label: p.label,
                }))}
                onChange={(key) => {
                  const p =
                    embeddingPresets[key as keyof typeof embeddingPresets];
                  form.setFieldsValue({
                    embedding_base_url: p.url,
                    embedding_model: p.model,
                    embedding_dimensions: p.dimensions,
                    embedding_api_key: "",
                  });
                  changed();
                }}
              />
            </Form.Item>
            {embedding !== "hash" && (
              <>
                <Form.Item
                  name="embedding_base_url"
                  label="检索服务地址"
                  rules={[
                    { required: true, message: "请输入检索服务地址" },
                    urlRule,
                  ]}
                >
                  <Input placeholder="https://example.com/v1" />
                </Form.Item>
                <Form.Item
                  name="embedding_model"
                  label="检索模型名称"
                  rules={[
                    {
                      required: true,
                      whitespace: true,
                      message: "请输入检索模型名称",
                    },
                  ]}
                >
                  <Input />
                </Form.Item>
                <Form.Item
                  name="embedding_api_key"
                  label="检索 API Key"
                  extra={
                    saved?.embedding_key_configured
                      ? "服务器已有检索密钥，留空保留。"
                      : "独立填写检索密钥，系统不会自动复用对话密钥。"
                  }
                  rules={[
                    {
                      required: !saved?.embedding_key_configured,
                      message: "请输入检索服务密钥",
                    },
                  ]}
                >
                  <Input.Password
                    autoComplete="new-password"
                    placeholder={
                      saved?.embedding_key_configured
                        ? "已配置 · 留空保留"
                        : "输入检索服务密钥"
                    }
                  />
                </Form.Item>
                <details className="connection-advanced">
                  <summary>自定义模型选项</summary>
                  <Form.Item
                    name="embedding_dimensions"
                    label="模型输出维度"
                    extra="标准预设已自动填写；自定义模型请使用服务商说明中的原生维度。"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={1} max={4096} />
                  </Form.Item>
                  <p>
                    自定义兼容服务需支持
                    /embeddings；系统使用模型原生输出，不额外发送 dimensions
                    参数。
                  </p>
                </details>
              </>
            )}
            {embedding === "hash" && (
              <p className="connection-help">
                当前为无语义的演示检索。正式使用需要配置真实检索模型，DeepSeek
                对话接口不能代替检索接口。
              </p>
            )}
          </section>
        </div>
        <div className="connection-actions">
          <span>先检查连接，再应用配置；测试只发送一段示例文字。</span>
          <Button
            icon={<ReloadOutlined />}
            loading={busy === "test"}
            onClick={test}
          >
            测试连接
          </Button>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            disabled={!tested || !!busy}
            loading={busy === "save"}
            onClick={save}
          >
            保存接入配置
          </Button>
        </div>
      </Form>
      {report && (
        <div className="connection-report" aria-live="polite">
          <Alert
            showIcon
            type={report.detail.chat.ok ? "success" : "warning"}
            message={report.detail.chat.message}
          />
          <Alert
            showIcon
            type={report.detail.embedding.ok ? "success" : "warning"}
            message={report.detail.embedding.message}
          />
        </div>
      )}
      {saved?.vectors.needs_reindex && (
        <Alert
          type="warning"
          showIcon
          message="已有简历需要更新检索索引"
          description={
            <span>
              请由服务负责人在后端目录执行{" "}
              <code>python -m scripts.reindex_embeddings --force</code>
              。完成后点击重新读取。索引更新成功后再进行真实检索验收。
              <Button type="link" disabled={!!busy} onClick={load}>
                重新读取
              </Button>
            </span>
          }
        />
      )}
      <p className="connection-footnote">
        此配置对整个工作台生效，请由服务负责人维护。密钥保存在服务端，页面不回显。
      </p>
    </section>
  );
}
