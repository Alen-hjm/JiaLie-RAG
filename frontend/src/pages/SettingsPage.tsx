import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Form, Input, Select, Tag, message } from 'antd'
import { api, AppSettings } from '../api'

export default function SettingsPage(){
  const [form]=Form.useForm(); const [settings,setSettings]=useState<AppSettings>(); const [testing,setTesting]=useState(false)
  // embedding_base_url / embedding_model / embedding_dimensions 故意不预填：
  // 留空 = 使用服务商预设。若把"解析后的值"回填再保存，就会把当天的预设
  // 固化进 .env，之后切换服务商时仍会拿旧模型名去调新服务商。
  const load=()=>api<AppSettings>('/api/settings').then(x=>{setSettings(x);form.setFieldsValue({model_mode:x.model_mode,base_url:x.base_url,chat_model:x.chat_model,timeout_seconds:x.timeout_seconds,embedding_provider:x.embedding_provider,embedding_mode:x.embedding_mode,embedding_base_url:'',embedding_model:'',embedding_dimensions:undefined,rerank_mode:x.rerank_mode,rerank_top_n:x.rerank_top_n})})
  useEffect(()=>{void load().catch(e=>message.error(e instanceof Error?e.message:'设置加载失败'))},[])
  const save=async(v:any)=>{try{const x=await api<AppSettings>('/api/settings',{method:'PUT',body:JSON.stringify(v)});setSettings(x);form.resetFields(['api_key','embedding_api_key']);message.success('设置已保存到本机 .env')}catch(e){message.error(e instanceof Error?e.message:'保存失败')}}
  const test=async()=>{setTesting(true);try{const x=await api<{ok:boolean;message:string}>('/api/settings/test-connection',{method:'POST'});message[x.ok?'success':'error'](x.message)}catch(e){message.error(e instanceof Error?e.message:'连接测试失败')}finally{setTesting(false)}}
  const status=settings?.model_mode==='mock'?['processing','Mock 离线模式']:settings?.api_key_configured?['success','API Key 已配置']:['warning','待配置聊天 API Key']
  const vectors=settings?.vectors
  const dims=vectors?Object.entries(vectors.dimension_counts||{}).map(([k,v])=>`${k} 维 × ${v}`).join('，')||'无':'—'
  return <div className="page settings-page">
    <header className="page-head"><div><p className="eyebrow">MODEL SETTINGS</p><h1>设置</h1><p>配置聊天模型与向量服务，两者互相独立。</p></div></header>

    <Card className="settings-card" title="① 向量检索（RAG 的语义层）" style={{marginBottom:16}}>
      {settings?.embedding_is_placeholder
        ? <Alert type="warning" showIcon style={{marginBottom:14}}
            message="当前使用占位向量（哈希），语义分不具实际意义"
            description={<>向量是由文本哈希得到的确定性数值，<b>与语义无关</b>。此时 45% 的「语义相关」权重实际是噪声，排序主要靠结构化条件与关键词。配置真实向量服务后执行 <code>python -m scripts.reindex_embeddings</code> 重建索引即可。</>}/>
        : <Alert type="success" showIcon style={{marginBottom:14}} message={`向量服务已启用：${settings?.embedding_provider} / ${settings?.embedding_model}`}/>}
      {vectors?.needs_reindex && <Alert type="error" showIcon style={{marginBottom:14}} message="存在需要重建的向量" description={`共 ${vectors.total_chunks} 个文本块：缺少向量 ${vectors.missing_vectors} 个，维度与当前配置不一致 ${vectors.mismatched_vectors} 个。请执行 python -m scripts.reindex_embeddings。`}/>}
      <Descriptions size="small" column={{xs:1,sm:2,md:3}} style={{marginBottom:12}}>
        <Descriptions.Item label="当前向量后端"><Tag color={settings?.embedding_is_placeholder?'warning':'success'}>{settings?.embedding_label}</Tag></Descriptions.Item>
        <Descriptions.Item label="维度">{settings?.embedding_dimensions}</Descriptions.Item>
        <Descriptions.Item label="已入库文本块">{vectors?.total_chunks ?? 0}</Descriptions.Item>
        <Descriptions.Item label="实际存储维度">{dims}</Descriptions.Item>
        <Descriptions.Item label="向量 Key">{settings?.embedding_key_configured?`已配置 ${settings.embedding_key_masked}`:'未配置'}</Descriptions.Item>
        <Descriptions.Item label="模式">{settings?.embedding_mode}</Descriptions.Item>
      </Descriptions>
      <Form form={form} layout="vertical" onFinish={save}>
        <div className="settings-grid">
          <Form.Item label="向量服务商" name="embedding_provider" extra="hash = 离线占位；拿到 Key 后改为 siliconflow / zhipu / dashscope">
            <Select options={[{value:'hash',label:'hash（本地占位，无需 Key）'},{value:'siliconflow',label:'siliconflow · BAAI/bge-m3'},{value:'zhipu',label:'zhipu · embedding-3'},{value:'dashscope',label:'dashscope · text-embedding-v3'},{value:'openai',label:'openai · text-embedding-3-small'}]}/>
          </Form.Item>
          <Form.Item label="向量 API Key" name="embedding_api_key" extra="独立于聊天 Key，只保存在本机 .env">
            <Input.Password placeholder={settings?.embedding_key_masked||'sk-...'} />
          </Form.Item>
          <Form.Item label="向量模式" name="embedding_mode"><Select options={[{value:'auto',label:'auto（有 Key 走真实，无 Key 占位）'},{value:'real',label:'real（必须真实，失败即报错）'},{value:'hash',label:'hash（强制占位）'}]}/></Form.Item>
          <Form.Item label="向量模型" name="embedding_model" extra="留空 = 使用服务商默认模型"><Input placeholder={settings?.embedding_model}/></Form.Item>
          <Form.Item label="向量维度" name="embedding_dimensions" extra="0 = 使用服务商原生维度，改动后必须重建向量"><Input type="number" /></Form.Item>
          <Form.Item label="向量 Base URL" name="embedding_base_url" extra="留空 = 使用服务商默认地址"><Input placeholder={settings?.embedding_base_url}/></Form.Item>
        </div>

        <div className="section-label"><p className="eyebrow">RERANK</p><h2>② 最终重排（决定 20% 的 rerank_score）</h2></div>
        {settings?.rerank_mode==='llm' && settings?.rerank_effective==='rule'
          ? <Alert type="warning" showIcon style={{marginBottom:14}} message="已选择 llm，但当前聊天模型不可用，实际仍按 rule 打分"/>
          : <Alert type="info" showIcon style={{marginBottom:14}}
              message={settings?.rerank_mode==='llm'?'LLM 批量打分：一次调用给 top-N 候选人打 0-100 分':'规则打分：按证据关键词覆盖率，免费、离线、可复现'}
              description="评测结论：在当前 16 人语料上，llm 略低于 rule（nDCG@5 0.85 vs 0.87），因此默认保持 rule；切换后可用同一套评测集自行复现对比。"/>}
        <div className="settings-grid">
          <Form.Item label="重排方式" name="rerank_mode">
            <Select options={[{value:'rule',label:'rule · 关键词覆盖（默认）'},{value:'llm',label:'llm · 大模型批量打分'}]}/>
          </Form.Item>
          <Form.Item label="LLM 裁判看到的候选人数" name="rerank_top_n" extra="只对总分最高的前 N 位重排，超出部分保持原顺序"><Input type="number" placeholder={String(settings?.rerank_top_n ?? 20)}/></Form.Item>
        </div>

        <div className="section-label"><p className="eyebrow">CHAT MODEL</p><h2>③ 聊天与结构化抽取</h2></div>
        <div className="settings-status"><span>当前模型状态</span><Tag color={status?.[0]}>{status?.[1]}</Tag>{settings?.api_key_masked&&<small>{settings.api_key_masked}</small>}</div>
        <div className="settings-grid">
          <Form.Item label="模型模式" name="model_mode"><Select options={[{value:'deepseek',label:'DeepSeek（真实聊天）'},{value:'mock',label:'Mock（离线演示）'},{value:'openai',label:'OpenAI-compatible'}]}/></Form.Item>
          <Form.Item label="聊天 API Key" name="api_key" extra="只保存在本机 .env，页面不会回显完整 Key"><Input.Password placeholder={settings?.api_key_masked||'sk-...'} /></Form.Item>
          <Form.Item label="Base URL" name="base_url"><Input /></Form.Item>
          <Form.Item label="对话模型" name="chat_model"><Input /></Form.Item>
          <Form.Item label="请求超时（秒）" name="timeout_seconds"><Input type="number" /></Form.Item>
        </div>
        <div className="settings-actions"><Button onClick={test} loading={testing}>测试连接</Button><Button type="primary" htmlType="submit">保存设置</Button></div>
      </Form>
    </Card>

    <div className="privacy-strip">真实简历在调用云端向量服务时会把原文发送给第三方服务商。上传前请确认已取得候选人授权；含第三方候选人信息的简历建议仅在本地使用占位向量或本地模型。</div>
  </div>
}
