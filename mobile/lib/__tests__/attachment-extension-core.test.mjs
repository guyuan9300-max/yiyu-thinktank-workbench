import test from "node:test";
import assert from "node:assert/strict";

import {
  inferAttachmentExtension,
  isLikelyExtension,
} from "../../.mobile-core-tests/dist/lib/attachment-extension-core.js";

// 回归: 相册/SAF 选图时 name 是 content document-id "image:1000000019"(无点、带冒号)
// 旧实现会把整串当后缀, 拼进路径带 ":" → IOException。修复后必须落到 MIME/兜底, 不含冒号。
test("相册 document-id 文件名不会被当作后缀(回归 IOException)", () => {
  const ext = inferAttachmentExtension({
    uri: "content://com.android.providers.media.documents/document/image%3A1000000019",
    name: "image:1000000019",
    type: "image/jpeg",
  });
  assert.equal(ext, "jpg");
  assert.ok(!ext.includes(":"), "后缀不能含冒号");
});

test("无任何线索的 document-id → 通用 bin 兜底, 不抛冒号", () => {
  const ext = inferAttachmentExtension({
    uri: "content://x/document/raw%3A12345",
    name: "raw:12345",
    type: "",
  });
  assert.equal(ext, "bin");
});

test("正常带后缀文件名优先采用", () => {
  assert.equal(
    inferAttachmentExtension({ uri: "file:///a/b/photo.PNG", name: "photo.PNG", type: "image/png" }),
    "png",
  );
});

test("多点文件名取最后一段", () => {
  assert.equal(
    inferAttachmentExtension({ uri: "file:///a/report.2024.final.pdf", name: "report.2024.final.pdf", type: "application/pdf" }),
    "pdf",
  );
});

test("无后缀名 + 走 URI 后缀", () => {
  assert.equal(
    inferAttachmentExtension({ uri: "file:///cache/clip.mp4", name: "clip", type: "" }),
    "mp4",
  );
});

test("MIME 映射: 图片/文档/音频", () => {
  assert.equal(inferAttachmentExtension({ uri: "content://x", name: "x", type: "image/heic" }), "heic");
  assert.equal(inferAttachmentExtension({ uri: "content://x", name: "x", type: "application/pdf" }), "pdf");
  assert.equal(inferAttachmentExtension({ uri: "content://x", name: "rec", type: "audio/m4a" }), "m4a");
});

test("MIME 带 charset 参数也能解析", () => {
  assert.equal(
    inferAttachmentExtension({ uri: "content://x", name: "x", type: "image/png; charset=binary" }),
    "png",
  );
});

test("isLikelyExtension 只认 1-5 位纯字母数字", () => {
  assert.equal(isLikelyExtension("jpg"), true);
  assert.equal(isLikelyExtension("jpeg"), true);
  assert.equal(isLikelyExtension("image:1000000019"), false);
  assert.equal(isLikelyExtension("toolongext"), false);
  assert.equal(isLikelyExtension(""), false);
  assert.equal(isLikelyExtension(undefined), false);
});
