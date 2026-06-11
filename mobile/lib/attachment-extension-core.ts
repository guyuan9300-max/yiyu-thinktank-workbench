// 附件/录音草稿文件名后缀推断 —— 纯逻辑, 无 expo 依赖, 可单测
//
// 背景: 从相册/SAF 选图时, Android 给的 file.name 不是 "xxx.jpg",
// 而是 content URI 的 document-id(如 "image:1000000019", 无点号、带冒号)。
// 旧实现 file.name.split(".").pop() 在无点号时原样返回整串当后缀,
// 拼进本地草稿路径后带非法字符 ":" → copyAsync/getInfoAsync 抛 IOException: isn't readable。

// MIME → 后缀(图片/文档/音视频都覆盖, 不再只认音频)
export const MIME_EXTENSION_MAP: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/jpg": "jpg",
  "image/png": "png",
  "image/heic": "heic",
  "image/heif": "heic",
  "image/webp": "webp",
  "image/gif": "gif",
  "application/pdf": "pdf",
  "video/mp4": "mp4",
  "video/quicktime": "mov",
  "audio/m4a": "m4a",
  "audio/mp4": "m4a",
  "audio/x-m4a": "m4a",
  "audio/mpeg": "mp3",
  "audio/mp3": "mp3",
  "audio/wav": "wav",
  "audio/x-wav": "wav",
  "audio/aac": "aac",
  "audio/ogg": "ogg",
};

// 合法后缀: 短纯字母数字(1-5 位)。content document-id(如 "image:1000000019")会被挡掉
export function isLikelyExtension(value: string | undefined | null): value is string {
  return !!value && /^[a-z0-9]{1,5}$/.test(value);
}

export function inferAttachmentExtension(file: { uri: string; name: string; type: string }): string {
  // 1) 文件名后缀 —— 必须真带点且后缀合法; 相册/SAF 给的 name 可能是无点的 content document-id, 不能当后缀
  const fromName = file.name.split(".").pop()?.trim().toLowerCase();
  if (file.name.includes(".") && isLikelyExtension(fromName)) {
    return fromName;
  }
  // 2) URI 路径后缀 —— 同样校验(避开 content:// 这类无后缀/带冒号的路径)
  const cleanUri = file.uri.split("?")[0].split("#")[0].toLowerCase();
  const fromUri = cleanUri.includes(".") ? cleanUri.split(".").pop()?.trim() : undefined;
  if (isLikelyExtension(fromUri)) {
    return fromUri;
  }
  // 3) MIME 映射
  const mime = file.type.split(";")[0].trim().toLowerCase();
  if (MIME_EXTENSION_MAP[mime]) {
    return MIME_EXTENSION_MAP[mime];
  }
  // 4) MIME 子类型兜底(如 image/foo → foo), 仍校验合法
  const subtype = mime.includes("/") ? mime.split("/").pop()?.trim() : undefined;
  if (isLikelyExtension(subtype)) {
    return subtype;
  }
  // 5) 最终兜底: 附件不一定是音频, 用通用 bin
  return "bin";
}
