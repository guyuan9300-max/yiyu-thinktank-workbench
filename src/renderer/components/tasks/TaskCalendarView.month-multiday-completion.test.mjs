import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import ts from 'typescript';

const componentUrl = new URL('./TaskCalendarView.tsx', import.meta.url);
const sourceText = readFileSync(componentUrl, 'utf8');
const sourceFile = ts.createSourceFile(
  componentUrl.pathname,
  sourceText,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);

function visit(node, predicate, matches = []) {
  if (predicate(node)) matches.push(node);
  ts.forEachChild(node, (child) => {
    visit(child, predicate, matches);
  });
  return matches;
}

function openingElementOf(node) {
  return ts.isJsxElement(node) ? node.openingElement : node;
}

function isButtonElement(node) {
  if (!ts.isJsxElement(node) && !ts.isJsxSelfClosingElement(node)) return false;
  return openingElementOf(node).tagName.getText(sourceFile) === 'button';
}

function hasJsxAttribute(node, name) {
  return openingElementOf(node).attributes.properties.some(
    (attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText(sourceFile) === name,
  );
}

function jsxAttributeExpressionText(node, name) {
  const attribute = openingElementOf(node).attributes.properties.find(
    (candidate) => ts.isJsxAttribute(candidate) && candidate.name.getText(sourceFile) === name,
  );
  if (!attribute || !ts.isJsxAttribute(attribute) || !attribute.initializer) return '';
  if (!ts.isJsxExpression(attribute.initializer) || !attribute.initializer.expression) return '';
  return attribute.initializer.expression.getText(sourceFile);
}

function isInside(node, ancestorBranch) {
  return node.pos >= ancestorBranch.pos && node.end <= ancestorBranch.end;
}

function hasShowTitleAncestor(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isConditionalExpression(current) && current.condition.getText(sourceFile) === 'slot.showTitle') {
      return isInside(node, current.whenTrue);
    }
    if (
      ts.isBinaryExpression(current)
      && current.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
      && current.left.getText(sourceFile) === 'slot.showTitle'
    ) {
      return isInside(node, current.right);
    }
  }
  return false;
}

function hasDraggableButtonAncestor(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (!ts.isJsxElement(current)) continue;
    const openingText = current.openingElement.getText(sourceFile);
    if (/\brole=["']button["']/.test(openingText) && hasJsxAttribute(current, 'draggable')) return true;
  }
  return false;
}

test('月视图跨天任务的每个可见周段提供独立完成按钮', () => {
  const completionButtons = visit(sourceFile, isButtonElement).filter((button) =>
    visit(button, (node) =>
      ts.isCallExpression(node)
      && node.expression.getText(sourceFile) === 'onToggleTaskStatus'
      && node.arguments[0]?.getText(sourceFile) === 'slot.task.id',
    ).length > 0,
  );

  assert.equal(
    completionButtons.length,
    1,
    '跨天连续条应有且只有一个按钮模板调用 onToggleTaskStatus(slot.task.id)',
  );

  const button = completionButtons[0];
  const buttonText = button.getText(sourceFile);
  const openingText = openingElementOf(button).getText(sourceFile);
  const clickHandlerText = jsxAttributeExpressionText(button, 'onClick');
  const keyDownHandlerText = jsxAttributeExpressionText(button, 'onKeyDown');

  assert.equal(hasShowTitleAncestor(button), true, '按钮只能在 slot.showTitle 周段首格渲染');
  assert.equal(hasDraggableButtonAncestor(button), false, '完成按钮不能嵌套在可拖拽任务条内');
  assert.equal(hasJsxAttribute(button, 'type'), true);
  assert.equal(hasJsxAttribute(button, 'draggable'), true);
  assert.equal(hasJsxAttribute(button, 'data-no-month-range-drag'), true);
  assert.equal(hasJsxAttribute(button, 'aria-label'), true);
  assert.equal(hasJsxAttribute(button, 'aria-pressed'), true);
  assert.match(openingText, /draggable=\{false\}/);
  assert.match(clickHandlerText, /event\.stopPropagation\(\)/);
  assert.match(clickHandlerText, /isLocalDraftTaskId\(slot\.task\.id\)/);
  assert.match(clickHandlerText, /onCalendarNotice\?\.\('info', LOCAL_DRAFT_NOTICE\)/);
  assert.match(clickHandlerText, /onToggleTaskStatus\(slot\.task\.id\)/);
  assert.match(keyDownHandlerText, /event\.stopPropagation\(\)/, '键盘事件必须隔离，避免同时打开任务编辑器');
  assert.match(buttonText, /slot\.task\.status === 'done'/);
  assert.match(buttonText, /`取消完成 \$\{slot\.task\.title\}`/);
  assert.match(buttonText, /`完成 \$\{slot\.task\.title\}`/);
});

test('每个周段的第一个可见格被标记为 showTitle', () => {
  assert.match(sourceText, /showTitle:\s*col === bar\.firstCol/);
});
