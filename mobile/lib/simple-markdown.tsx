/**
 * Lightweight Markdown renderer for React Native.
 * Supports: headings (一、二、三 / ## / 1.), bold (**text**), lists (- item), paragraphs.
 * No external dependencies.
 */
import React, { useMemo } from "react";
import { Text, View, StyleSheet } from "react-native";
import type { TextStyle } from "react-native";
import { colors } from "./theme";

interface SimpleMarkdownProps {
  text: string;
  baseStyle?: TextStyle;
}

type Block =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[]; ordered: boolean };

function parseBlocks(raw: string): Block[] {
  const lines = raw.split("\n");
  const blocks: Block[] = [];
  let listBuffer: string[] = [];
  let listOrdered = false;
  let paragraphBuffer: string[] = [];

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return;
    blocks.push({ type: "paragraph", text: paragraphBuffer.join(" ").trim() });
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push({ type: "list", items: [...listBuffer], ordered: listOrdered });
    listBuffer = [];
    listOrdered = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    // Heading patterns: 一、二、三 / ## heading / 1. short heading (standalone)
    if (
      /^[一二三四五六七八九十]+、/.test(trimmed) ||
      /^#{1,4}\s+/.test(trimmed) ||
      /^第[一二三四五六七八九十\d]+部分/.test(trimmed)
    ) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", text: trimmed.replace(/^#{1,4}\s*/, "") });
      continue;
    }

    // Numbered heading: "1. Short title" (≤42 chars, no punctuation ending)
    const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch && trimmed.length <= 42 && !/[。！？!?：:]$/.test(trimmed)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", text: trimmed });
      continue;
    }

    // Unordered list
    const ulMatch = trimmed.match(/^[-*•]\s+(.+)$/);
    if (ulMatch) {
      flushParagraph();
      if (listBuffer.length && listOrdered) flushList();
      listOrdered = false;
      listBuffer.push(ulMatch[1]);
      continue;
    }

    // Ordered list item (longer than heading threshold)
    if (numberedMatch && trimmed.length > 42) {
      flushParagraph();
      if (listBuffer.length && !listOrdered) flushList();
      listOrdered = true;
      listBuffer.push(numberedMatch[2]);
      continue;
    }

    // Regular text
    flushList();
    paragraphBuffer.push(trimmed);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInlineEmphasis(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <Text key={idx} style={inlineStyles.bold}>
          {part.slice(2, -2)}
        </Text>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

export function SimpleMarkdown({ text, baseStyle }: SimpleMarkdownProps) {
  const blocks = useMemo(() => parseBlocks(text), [text]);

  if (!blocks.length) {
    return <Text style={baseStyle}>{text}</Text>;
  }

  return (
    <View style={mdStyles.container}>
      {blocks.map((block, idx) => {
        if (block.type === "heading") {
          return (
            <Text key={`h-${idx}`} style={[baseStyle, mdStyles.heading]}>
              {renderInlineEmphasis(block.text)}
            </Text>
          );
        }
        if (block.type === "list") {
          return (
            <View key={`l-${idx}`} style={mdStyles.listContainer}>
              {block.items.map((item, i) => (
                <View key={`li-${idx}-${i}`} style={mdStyles.listItem}>
                  <Text style={[baseStyle, mdStyles.bullet]}>
                    {block.ordered ? `${i + 1}.` : "•"}
                  </Text>
                  <Text style={[baseStyle, mdStyles.listText]}>
                    {renderInlineEmphasis(item)}
                  </Text>
                </View>
              ))}
            </View>
          );
        }
        return (
          <Text key={`p-${idx}`} style={[baseStyle, mdStyles.paragraph]}>
            {renderInlineEmphasis(block.text)}
          </Text>
        );
      })}
    </View>
  );
}

const inlineStyles = StyleSheet.create({
  bold: {
    fontWeight: "700",
    color: colors.text,
  },
});

const mdStyles = StyleSheet.create({
  container: {
    gap: 8,
  },
  heading: {
    fontWeight: "700",
    fontSize: 15,
    lineHeight: 24,
    color: colors.text,
    marginTop: 4,
  },
  paragraph: {
    lineHeight: 22,
  },
  listContainer: {
    gap: 4,
    paddingLeft: 4,
  },
  listItem: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  bullet: {
    width: 20,
    lineHeight: 22,
    color: colors.brand,
    fontWeight: "600",
  },
  listText: {
    flex: 1,
    lineHeight: 22,
  },
});
