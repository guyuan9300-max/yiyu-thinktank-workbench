/**
 * 语音识别 provider 描述符。
 *
 * 决定系统设置 → 语音识别模型 section 的 dropdown 选项 + 每个 provider 暴露哪些字段。
 *
 * 新增 provider 时只需：
 * 1. 在 `SPEECH_MODEL_PROVIDERS` 里加一项
 * 2. 后端 `services/speech_recognition/registry.py` 注册具体实现
 *
 * **注意：** 后端只用 `provider` 名做路由，字段语义完全由前端这份描述符决定。
 * 后端 `credentials_json` / `extra_config_json` 是无模式的 JSON，灵活承载任何字段。
 */

export interface SpeechProviderField {
  key: string;
  label: string;
  type: 'text' | 'password' | 'textarea';
  placeholder?: string;
  helper?: string;
}

export interface SpeechProviderModelOption {
  id: string;
  label: string;
  description?: string;
}

export interface SpeechProviderExtraSelect {
  key: string;
  label: string;
  type: 'select';
  options: Array<{ value: string; label: string }>;
  defaultValue: string;
  helper?: string;
}

export interface SpeechProviderDescriptor {
  id: string;
  label: string;
  /** 该 provider 是否 I1a 阶段就支持"测试连接"+"实际转写"。占位 provider = false。 */
  supported: boolean;
  /** UI 上的副标题说明。 */
  description: string;
  /** 鉴权字段（敏感字段用 password type 做 mask）。 */
  credentialFields: SpeechProviderField[];
  /** 该 provider 下可选的具体模型 ID。 */
  models: SpeechProviderModelOption[];
  /** 额外配置项（语种、region、endpoint 覆盖等）。 */
  extraFields: SpeechProviderExtraSelect[];
  /** 如果 supported=false，UI 上显示此提示并禁用测试连接。 */
  unsupportedHint?: string;
}

export const SPEECH_MODEL_PROVIDERS: SpeechProviderDescriptor[] = [
  {
    id: 'volcano',
    label: '火山引擎（豆包语音识别）',
    supported: true,
    description: '火山引擎录音文件识别 / 一句话识别。中文场景准确率高，数据合规友好，与你已接入的豆包大模型同一账号。',
    credentialFields: [
      { key: 'app_id', label: 'App ID', type: 'text', placeholder: '在火山引擎控制台拿到的应用 App ID' },
      { key: 'access_key', label: 'Access Key', type: 'text', placeholder: '可选；长期 Access Key ID' },
      { key: 'access_token', label: 'Access Token', type: 'password', placeholder: '火山控制台 → 语音技术 → API Token' },
    ],
    models: [
      { id: 'bigmodel', label: '豆包·录音文件识别（大模型版）', description: '异步任务，最长 5h，中文准确率最高' },
      { id: 'standard', label: '录音文件识别（标准版）', description: '同上但模型较老，价格略低' },
    ],
    extraFields: [
      {
        key: 'language',
        label: '识别语种',
        type: 'select',
        options: [
          { value: 'zh-CN', label: '简体中文' },
          { value: 'en-US', label: '英文（美国）' },
          { value: 'auto', label: '自动识别' },
        ],
        defaultValue: 'zh-CN',
      },
    ],
  },
  {
    id: 'openai_whisper',
    label: 'OpenAI Whisper',
    supported: false,
    description: 'OpenAI Whisper API。海外网络可达且能接受 OpenAI 数据合规条款的场景适用。',
    credentialFields: [
      { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-...' },
      { key: 'base_url', label: 'API Base URL（可选）', type: 'text', placeholder: 'https://api.openai.com/v1' },
    ],
    models: [{ id: 'whisper-1', label: 'whisper-1' }],
    extraFields: [
      {
        key: 'language',
        label: '识别语种',
        type: 'select',
        options: [
          { value: 'zh', label: '中文' },
          { value: 'en', label: '英文' },
          { value: 'auto', label: '自动识别' },
        ],
        defaultValue: 'auto',
      },
    ],
    unsupportedHint: '暂未实现 OpenAI Whisper 的"测试连接"和实际转写，敬请期待。',
  },
  {
    id: 'aliyun_tongyi',
    label: '阿里通义听悟',
    supported: false,
    description: '阿里云通义听悟语音识别。',
    credentialFields: [
      { key: 'access_key_id', label: 'AccessKey ID', type: 'text' },
      { key: 'access_key_secret', label: 'AccessKey Secret', type: 'password' },
      { key: 'app_key', label: 'App Key', type: 'text' },
    ],
    models: [{ id: 'paraformer-v1', label: 'paraformer-v1' }],
    extraFields: [],
    unsupportedHint: '暂未实现阿里通义听悟接入，敬请期待。',
  },
  {
    id: 'xunfei',
    label: '科大讯飞',
    supported: false,
    description: '科大讯飞语音识别（开放平台）。',
    credentialFields: [
      { key: 'app_id', label: 'APP ID', type: 'text' },
      { key: 'api_key', label: 'API Key', type: 'password' },
      { key: 'api_secret', label: 'API Secret', type: 'password' },
    ],
    models: [{ id: 'iat', label: 'IAT 实时语音转写' }],
    extraFields: [],
    unsupportedHint: '暂未实现讯飞接入，敬请期待。',
  },
];

export function findSpeechProvider(id: string): SpeechProviderDescriptor | undefined {
  return SPEECH_MODEL_PROVIDERS.find((p) => p.id === id);
}
