/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 官方云识别基准地址。开源版留空；官方分发构建时注入。 */
  readonly VITE_YIYU_OFFICIAL_CLOUD_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
