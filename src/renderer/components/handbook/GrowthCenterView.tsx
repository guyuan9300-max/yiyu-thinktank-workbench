import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Eye,
  Heart,
  Layers3,
  Lightbulb,
  Lock,
  PenTool,
  Rocket,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Swords,
  Target,
  Trophy,
  Users,
  X,
  type LucideIcon,
  Flag,
  Briefcase,
  CalendarClock,
  Gauge,
  FileStack,
  CircleDashed,
  Handshake,
  HandHelping,
  Radar,
  Wrench,
  Star,
} from 'lucide-react';

import {
  getGrowthOverview,
  getHandbook,
  getGrowthBadges,
  markHandbookEntryReused,
} from '../../lib/api';
import { useGrowthOverviewState } from '../growth/GrowthContext';
import type {
  GrowthAbilityKey,
  GrowthAbilityScore,
  GrowthAbilityGap,
  GrowthOverview,
  XpLedgerEntry,
  HandbookEntry,
  BadgeBoard,
  BadgeProgress,
  BadgeState,
  BadgeCategory,
  BadgeBoardOverview,
} from '../../../shared/types';

/* ══════════════════════════════════════════════════════════════════════
   CSS — injected once, matches growth-center-preview.html exactly
   ──────────────────────────────────────────────────────────────────── */
const GROWTH_CSS = `
.gc-root { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: #F9FAFB; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', 'Hiragino Sans GB', sans-serif; color: #374151; -webkit-font-smoothing: antialiased; }

/* Header */
.gc-header { background: #fff; border-bottom: 1px solid #F3F4F6; padding: 20px 24px 0; flex-shrink: 0; }
.gc-header-inner { width: 100%; max-width: 1160px; margin: 0 auto; box-sizing: border-box; }
.gc-header-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.gc-page-title { font-size: 18px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }
.gc-page-subtitle { font-size: 11px; color: #94a3b8; font-weight: 500; margin-top: 3px; }
.gc-xp-area { display: flex; align-items: center; gap: 12px; }
.gc-rank-chip { display: flex; align-items: center; gap: 8px; background: #EEF3FF; border: 1px solid #D6E1FF; border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; color: #334155; }
.gc-xp-num { font-size: 14px; font-weight: 600; color: #1e293b; letter-spacing: -0.3px; text-align: right; }
.gc-xp-label { font-size: 11px; color: #94a3b8; font-weight: 400; }
.gc-xp-week { font-size: 11px; font-weight: 600; color: #10b981; text-align: right; }

/* Tab pills */
.gc-tab-bar { display: inline-flex; gap: 4px; background: #f1f5f9; border-radius: 16px; padding: 4px; }
.gc-tab-btn { background: none; border: none; cursor: pointer; padding: 6px 16px; font-size: 13px; font-weight: 500; border-radius: 16px; color: #64748b; transition: all 0.2s; }
.gc-tab-btn:hover { color: #334155; }
.gc-tab-btn.active { background: #fff; color: #5B7BFE; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }

/* Content */
.gc-content { flex: 1; overflow-y: auto; padding: 20px 24px; }
.gc-content-inner { width: 100%; max-width: 1160px; margin: 0 auto; box-sizing: border-box; }

/* Cards */
.gc-card { background: #fff; border: 1px solid #f3f4f6; border-radius: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.gc-card-inner { background: #fff; border: 1px solid #f3f4f6; border-radius: 22px; }
.gc-section-header { display: flex; align-items: flex-end; justify-content: space-between; padding: 0 4px; margin-bottom: 12px; }
.gc-section-title { font-size: 16px; font-weight: 600; color: #1e293b; }
.gc-section-hint { font-size: 11px; font-weight: 500; letter-spacing: 0.3px; color: #94a3b8; }

/* Icon token */
.gc-icon-token { display: flex; align-items: center; justify-content: center; border-radius: 999px; flex-shrink: 0; }
.gc-icon-token.sm { width: 20px; height: 20px; }
.gc-icon-token.md { width: 28px; height: 28px; }
.gc-icon-token.lg { width: 40px; height: 40px; }
.gc-icon-token.xl { width: 56px; height: 56px; }
.gc-icon-token.brand { background: #EEF3FF; }
.gc-icon-token.brand-border { background: #EEF3FF; border: 1px solid #D6E1FF; }
.gc-icon-token.gray { background: #f1f5f9; }

/* Insight cards */
.gc-insight-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.gc-insight-card { padding: 20px; }
.gc-insight-quote { font-size: 13px; color: #1e293b; line-height: 1.9; }
.gc-insight-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
.gc-insight-author { display: flex; align-items: center; gap: 8px; }
.gc-author-name { font-size: 11px; font-weight: 500; color: #64748b; }
.gc-source-tag { background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 999px; padding: 2px 8px; font-size: 10px; color: #94a3b8; font-weight: 500; letter-spacing: 0.2px; }
.gc-like-btn { display: flex; align-items: center; gap: 4px; background: none; border: none; cursor: pointer; font-size: 11px; color: #D1D5DB; transition: color 0.2s; }
.gc-like-btn:hover { color: #5B7BFE; }
.gc-like-btn.liked { color: #5B7BFE; }

/* AI section */
.gc-ai-section { border-radius: 24px; background: radial-gradient(circle at top left, rgba(51,92,254,0.06), transparent 40%), linear-gradient(180deg, #fff 0%, #fafbff 100%); border: 1px solid #DDE6FF; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-top: 24px; }
.gc-ai-chip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; border: 1px solid #D6E1FF; background: #fff; padding: 4px 12px; font-size: 12px; font-weight: 500; color: #335CFE; box-shadow: 0 1px 2px rgba(0,0,0,0.04); margin-bottom: 16px; }
.gc-pending-actions { display: flex; gap: 8px; margin-top: 12px; }
.gc-btn-brand { display: inline-flex; align-items: center; gap: 6px; background: #335CFE; color: #fff; border: none; border-radius: 999px; padding: 8px 16px; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.gc-btn-brand:hover:not(:disabled) { background: #2C50E0; }
.gc-btn-brand:disabled { opacity: 0.6; cursor: not-allowed; }
@keyframes gc-toast-in { from { opacity: 0; transform: translateX(-50%) translateY(-8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
.gc-btn-ghost { background: none; border: 1px solid #e2e8f0; color: #64748b; border-radius: 999px; padding: 8px 16px; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.gc-btn-ghost:hover { background: #f8fafc; }

.gc-progress-track { flex: 1; height: 3px; background: #f1f5f9; border-radius: 999px; overflow: hidden; }
.gc-progress-fill { height: 100%; border-radius: 999px; }

/* XP Overview hero */
.gc-xp-hero { border-radius: 28px; border: 1px solid #DDE6FF; background: radial-gradient(circle at top left, rgba(51,92,254,0.08), transparent 34%), linear-gradient(180deg, #fff 0%, #fafbff 100%); padding: 24px; box-shadow: 0 24px 70px rgba(15,23,42,0.04); }
.gc-xp-hero-top { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.gc-xp-hero-rank { font-size: 16px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }
.gc-xp-hero-num { font-size: 24px; font-weight: 600; color: #0f172a; letter-spacing: -0.5px; }
.gc-xp-hero-badge { display: inline-flex; align-items: center; gap: 4px; background: #ecfdf5; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 600; color: #059669; }
.gc-xp-breakdown { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
.gc-xp-break-card { border-radius: 22px; border: 1px solid rgba(255,255,255,0.8); background: rgba(255,255,255,0.88); padding: 16px; box-shadow: 0 18px 40px rgba(148,163,184,0.08); backdrop-filter: blur(8px); }
.gc-xp-break-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.gc-xp-break-label { font-size: 10px; font-weight: 500; color: #94a3b8; }
.gc-xp-break-val { font-size: 20px; font-weight: 600; color: #0f172a; letter-spacing: -0.3px; }

/* Badge milestones */
.gc-badge-section { border-radius: 24px; border: 1px solid #eef2ff; background: #fff; padding: 20px; box-shadow: 0 16px 48px rgba(15,23,42,0.035); }
.gc-badge-section + .gc-badge-section { margin-top: 16px; }
.gc-badge-section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.gc-badge-section-title { font-size: 14px; font-weight: 600; color: #0f172a; letter-spacing: -0.2px; }
.gc-badge-section-hint { font-size: 11px; font-weight: 500; color: #94a3b8; text-align: right; }
.gc-badge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 10px; }
.gc-badge-cell { min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px 8px; cursor: pointer; transition: transform 0.2s, background 0.2s; background: none; border: none; border-radius: 18px; }
.gc-badge-cell:hover { transform: translateY(-2px); background: rgba(248,250,252,0.86); }
.gc-badge-name { font-size: 11px; font-weight: 500; text-align: center; line-height: 1.35; max-width: 96px; min-height: 30px; display: flex; align-items: center; justify-content: center; }
.gc-badge-name.lit { color: #334155; }
.gc-badge-name.prog { color: #64748b; }
.gc-badge-name.lock { color: #94a3b8; }
.gc-badge-sub { font-size: 10px; font-weight: 600; }
.gc-badge-status { display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 8px; font-size: 9px; font-weight: 600; }
.gc-badge-status.lit { background: #ecfdf5; color: #059669; }
.gc-badge-status.ready { background: rgba(91,123,254,0.1); color: #335CFE; }
.gc-badge-status.progress { background: rgba(91,123,254,0.08); color: #5B7BFE; }
.gc-badge-status.locked { background: #f1f5f9; color: #94a3b8; }
.gc-badge-category-list { display: flex; flex-direction: column; gap: 14px; }
.gc-badge-category-card { border: 1px solid #edf2f7; border-radius: 22px; background: #fff; padding: 18px; }
.gc-badge-category-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.gc-badge-category-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.gc-badge-category-name { font-size: 13px; font-weight: 600; color: #0f172a; letter-spacing: -0.2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gc-badge-category-meta { font-size: 11px; font-weight: 500; color: #94a3b8; flex-shrink: 0; }
.gc-badge-category-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(108px, 1fr)); gap: 8px; }

/* Personal rank */
.gc-rank-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 4px; }
.gc-rank-header-left { display: flex; align-items: center; gap: 8px; }
.gc-rank-list { padding: 18px; display: flex; flex-direction: column; gap: 14px; }
.gc-rank-row { display: flex; align-items: center; gap: 14px; padding: 16px; border-radius: 18px; background: rgba(248,250,252,0.72); }
.gc-rank-name-text { font-size: 14px; font-weight: 600; color: #0f172a; letter-spacing: -0.2px; }
.gc-rank-meta { font-size: 11px; font-weight: 500; color: #94a3b8; margin-top: 3px; }
.gc-rank-xp { font-size: 13px; font-weight: 600; color: #335CFE; text-align: right; white-space: nowrap; flex-shrink: 0; }
.gc-rank-bar { height: 4px; background: #f1f5f9; border-radius: 999px; overflow: hidden; }
.gc-rank-bar-fill { height: 100%; border-radius: 999px; background: #5B7BFE; }
.gc-rank-week { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-radius: 18px; background: rgba(236,253,245,0.72); border: 1px solid #d1fae5; padding: 14px 16px; font-size: 12px; font-weight: 500; color: #047857; }
.gc-modal-subtitle { font-size: 11px; font-weight: 600; letter-spacing: 1.2px; color: #94a3b8; margin-bottom: 8px; }
.gc-modal-link-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.gc-modal-link-pill { border-radius: 999px; border: 1px solid #dbeafe; background: #eff6ff; padding: 4px 10px; font-size: 10px; font-weight: 600; color: #335CFE; }

.gc-space-y > * + * { margin-top: 24px; }

/* Ability growth tab */
.gc-radar-card { display: flex; flex-direction: column; align-items: stretch; gap: 28px; padding: 32px 36px; }
@media (min-width: 900px) { .gc-radar-card { flex-direction: row; align-items: center; gap: 56px; } }
.gc-radar-visual { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.gc-radar-visual svg { max-width: 100%; height: auto; }
@media (min-width: 900px) { .gc-radar-visual { width: 380px; } }
.gc-radar-legend { display: flex; align-items: center; gap: 16px; font-size: 11px; font-weight: 500; color: #94a3b8; margin-top: 4px; }
.gc-radar-legend-dot { width: 8px; height: 8px; border-radius: 999px; margin-right: 6px; display: inline-block; }
.gc-ability-list { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.gc-ability-row-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.gc-ability-row-left { display: flex; align-items: center; gap: 8px; }
.gc-ability-icon-box { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; }
.gc-ability-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.gc-ability-stage { border-radius: 6px; border: 1px solid #f1f5f9; background: #f8fafc; padding: 1px 6px; font-size: 9px; font-weight: 500; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; }
.gc-ability-xp { font-size: 12px; font-weight: 600; color: #335CFE; }
.gc-ability-delta { font-size: 10px; font-weight: 500; color: #10b981; margin-left: 6px; }
.gc-ability-bar { height: 6px; background: #f8fafc; border-radius: 999px; overflow: hidden; }
.gc-ability-bar-fill { height: 100%; background: #5B7BFE; border-radius: 999px; }
.gc-ability-evidence { font-size: 10px; font-weight: 500; color: #94a3b8; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Timeline */
.gc-timeline-entry { display: flex; gap: 16px; }
.gc-timeline-line { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.gc-timeline-dot { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; flex-shrink: 0; }
.gc-timeline-tail { width: 1px; flex: 1; background: #f1f5f9; margin: 4px 0; }
.gc-timeline-content { flex: 1; padding-bottom: 20px; }
.gc-timeline-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.gc-timeline-title { font-size: 13px; font-weight: 500; color: #1e293b; line-height: 1.4; }
.gc-timeline-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.gc-timeline-tag { border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 500; letter-spacing: 0.2px; }
.gc-timeline-tag.special { background: #fff7ed; color: #ea580c; }
.gc-timeline-tag.normal { background: #f1f5f9; color: #64748b; }
.gc-timeline-xp { font-size: 13px; font-weight: 600; letter-spacing: -0.3px; flex-shrink: 0; }
.gc-timeline-time { font-size: 10px; font-weight: 500; color: #94a3b8; margin-top: 2px; text-align: right; }

/* Gap card */
.gc-gap-card { padding: 20px; }
.gc-gap-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.gc-no-gap { border-radius: 24px; background: rgba(236,253,245,0.4); border: 1px solid #a7f3d0; padding: 16px 20px; }

@media (max-width: 640px) {
  .gc-header { padding: 16px 16px 0; }
  .gc-content { padding: 16px; }
  .gc-header-top { gap: 12px; }
  .gc-radar-card { padding: 24px 16px; }
  .gc-xp-breakdown { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gc-badge-section { padding: 16px; }
  .gc-badge-section-head, .gc-badge-category-header { align-items: flex-start; flex-direction: column; gap: 4px; }
  .gc-badge-section-hint { text-align: left; }
  .gc-badge-grid, .gc-badge-category-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gc-rank-row { align-items: flex-start; }
}

/* Loading */
.gc-loading { display: flex; align-items: center; justify-content: center; padding: 80px 0; }
.gc-loading-icon { width: 40px; height: 40px; border-radius: 999px; background: #EEF3FF; display: flex; align-items: center; justify-content: center; animation: gc-pulse 1.5s ease-in-out infinite; margin-bottom: 12px; }
@keyframes gc-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.gc-loading-text { font-size: 13px; font-weight: 500; color: #94a3b8; }

/* Empty state */
.gc-empty { border-radius: 24px; border: 1px dashed #e2e8f0; background: #fff; padding: 40px 20px; text-align: center; }
.gc-empty-title { font-size: 14px; font-weight: 600; color: #475569; margin-bottom: 4px; }
.gc-empty-desc { font-size: 13px; color: #94a3b8; max-width: 400px; margin: 0 auto; line-height: 1.6; }

/* Badge modal */
.gc-modal-overlay { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; background: rgba(15,23,42,0.2); backdrop-filter: blur(4px); }
.gc-modal { border-radius: 28px; border: 1px solid rgba(255,255,255,0.7); background: #fff; box-shadow: 0 24px 80px rgba(15,23,42,0.18); padding: 24px; width: 420px; max-width: 90vw; max-height: 80vh; overflow-y: auto; }
`;

/* Inject CSS once */
let cssInjected = false;
function injectGrowthCSS() {
  if (cssInjected) return;
  const style = document.createElement('style');
  style.setAttribute('data-growth-center', 'true');
  style.textContent = GROWTH_CSS;
  document.head.appendChild(style);
  cssInjected = true;
}

/* ══════════════════════════════════════════════════════════════════════
   Icon motif map — for badge rendering from API data
   ──────────────────────────────────────────────────────────────────── */
const MOTIF_ICON_MAP: Record<string, LucideIcon> = {
  meeting_ring: Users,
  report_arrow: ArrowRight,
  chat_bolt: Sparkles,
  linked_rings: Users,
  handoff: HandHelping,
  radar_ping: Radar,
  search_chat: Search,
  stack_docs: Layers3,
  path_nodes: Target,
  handshake_seal: Handshake,
  blueprint_flag: Flag,
  grid_blocks: Layers3,
  summit_flag: Flag,
  shield_ping: ShieldCheck,
  seal_box: Briefcase,
  calendar_lines: CalendarClock,
  dashboard_gauge: Gauge,
  manual_stack: BookOpen,
  stamp_flow: CircleDashed,
  loop_note: ArrowRight,
  invoice_shield: ShieldCheck,
  wallet_gate: Briefcase,
  scroll_seal: FileStack,
  bill_return: ArrowRight,
  cart_checklist: Briefcase,
  mentor_orbit: Users,
  idea_burst: Lightbulb,
  cards_spark: Sparkles,
  path_flag: Flag,
  wrench_up: Wrench,
  spark_card: Sparkles,
  converge_box: CircleDashed,
  check_list: ShieldCheck,
  steps_forward: ArrowRight,
  split_arrows: ArrowRight,
  split_blocks: Layers3,
  roadblock_light: ShieldAlert,
  calendar_zero: CalendarClock,
  bullseye_arrow: Target,
  shield_card: ShieldCheck,
  loop_flag: Flag,
  time_blocks: CalendarClock,
  door_focus: Lock,
  bell_early: CalendarClock,
  bubble_basket: HandHelping,
  dial_clock: Gauge,
  timeline_split: ArrowRight,
  sunrise_card: Sparkles,
  lamp_notebook: BookOpen,
  parallel_lines: Layers3,
  week_baton: CalendarClock,
  hand_card: HandHelping,
  highlight_lines: Lightbulb,
  bubble_to_list: ArrowRight,
  flag_margin: Flag,
  anchor_bubbles: Target,
  stamp_card: ShieldCheck,
  path_branch: Target,
  card_stack: Layers3,
  question_bridge: Search,
  sync_loop: CircleDashed,
  focus_lens: Eye,
  decision_gate: ShieldAlert,
  orbit_users: Users,
  pen_signal: PenTool,
  file_stack: FileStack,
  star_step: Star,
  arrow_db_return: ArrowRight,
  boundary_blocks: Layers3,
  bridge_bubble_gear: Handshake,
  bridge_depts: Handshake,
  bridge_platforms: Handshake,
  bulb_question: Lightbulb,
  card_to_box: Briefcase,
  card_to_people: Users,
  card_up_arrow: ArrowRight,
  center_copy: FileStack,
  chairs_lamp: Users,
  cloud_to_tag: BookOpen,
  compass_correct: Target,
  connector_dual: Handshake,
  dialog_reverse: ArrowRight,
  doc_shelf_light: BookOpen,
  door_source: Lock,
  dual_pens: PenTool,
  dual_rings: Users,
  eye_dials: Eye,
  filter_clean: Search,
  flag_people: Flag,
  flow_to_ui: ArrowRight,
  folder_stack: FileStack,
  footprint_box: Target,
  gauge_red: Gauge,
  gears_people: Users,
  hand_light_path: HandHelping,
  helix_card: BrainCircuit,
  ice_warm: Sparkles,
  knot_hand: Handshake,
  lens_seed: Search,
  lever_rock: Wrench,
  map_pieces: Layers3,
  map_to_cards: Layers3,
  milestone_steps: Target,
  mirror_outline: Eye,
  modules_chain: Layers3,
  mold_cards: Layers3,
  net_sparkle: Sparkles,
  news_to_task: ArrowRight,
  page_sections: FileStack,
  page_structure: FileStack,
  pan_gold: ShieldCheck,
  part_slot: Layers3,
  pen_screen_correct: PenTool,
  person_highlight: Users,
  person_lens: Users,
  pin_evidence: ShieldCheck,
  puzzle_outline: Layers3,
  question_frame: Search,
  radar_waves: Radar,
  reply_bubble: Users,
  scene_frame: Eye,
  scissors_vine: Wrench,
  spotlight_crack: ShieldAlert,
  sprout_flow: Sparkles,
  stacked_stones: Layers3,
  stamp_smooth: ShieldCheck,
  stone_stairs: Target,
  table_path: Layers3,
  thermometer_hand: Gauge,
  thick_line: PenTool,
  thread_nodes: Target,
  toolbox_docs: Wrench,
  version_up: ArrowRight,
  warning_crack: ShieldAlert,
  wave_to_text: PenTool,
  web_nodes: Target,
  whiteboard_spot: BookOpen,
  window_path_stars: Sparkles,
  wrench_module: Wrench,
  zip_folder: Briefcase,
};

const ABILITY_FALLBACK_ICONS: Record<GrowthAbilityKey, LucideIcon> = {
  exec: Rocket,
  collab: Users,
  analyze: BrainCircuit,
  insight: Eye,
  risk: ShieldAlert,
  write: PenTool,
};

function badgeIconFor(badge: BadgeProgress): LucideIcon {
  return MOTIF_ICON_MAP[badge.iconMotif] || ABILITY_FALLBACK_ICONS[badge.abilityKey] || Sparkles;
}

/* ══════════════════════════════════════════════════════════════════════
   Ability visual config
   ──────────────────────────────────────────────────────────────────── */
const ABILITY_VISUALS: Record<string, { icon: LucideIcon; color: string; bg: string }> = {
  exec:    { icon: Rocket,      color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
  collab:  { icon: Users,       color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
  analyze: { icon: BrainCircuit, color: '#64748b', bg: '#f1f5f9' },
  insight: { icon: Eye,         color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
  risk:    { icon: ShieldAlert,  color: '#f97316', bg: 'rgba(249,115,22,0.08)' },
  write:   { icon: PenTool,     color: '#5B7BFE', bg: 'rgba(91,123,254,0.1)' },
};

/* ══════════════════════════════════════════════════════════════════════
   Utility functions
   ──────────────────────────────────────────────────────────────────── */
function formatRelativeMoment(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) return '刚刚';
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) return `${diffDays}天前`;
  if (diffDays < 14) return '1周前';
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function weekLabelFromDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const oneJan = new Date(date.getFullYear(), 0, 1);
  const weekNum = Math.ceil(((date.getTime() - oneJan.getTime()) / 86400000 + oneJan.getDay() + 1) / 7);
  return `第${weekNum}周`;
}

const SOURCE_TYPE_CN: Record<string, string> = {
  weekly_review_task_entry: '任务复盘',
  task_note: '任务备注',
  review_insight: '复盘提炼',
  meeting: '会议沉淀',
  meeting_source: '会议资料',
  event_line_activity: '事件线活动',
  v2_document: '数据中心资料',
  document: '资料文档',
  task_context_candidate: '任务经验',
  task_attachment_candidate: '附件提炼',
  review_insight_pending: '复盘提炼',
  manual: '手动录入',
};

function sourceTypeCN(raw: string): string {
  return SOURCE_TYPE_CN[raw] || raw.replace(/_/g, ' ');
}

function pickQuoteText(entry: HandbookEntry): string {
  const title = entry.title || '';
  const summary = entry.summary || '';
  if (title.length > 0 && title.length <= 80) return title;
  if (summary.length > 120) return summary.slice(0, 117) + '…';
  return summary || title.slice(0, 117) + (title.length > 117 ? '…' : '');
}

function xpTypeLabel(xpType: string): string {
  if (xpType === 'codification') return '经验沉淀';
  if (xpType === 'reuse') return '方法复用';
  if (xpType === 'improvement') return '成长改进';
  return '复盘反思';
}

/* ══════════════════════════════════════════════════════════════════════
   Badge palette + BadgeToken — SVG ring with icon center
   ──────────────────────────────────────────────────────────────────── */
const STATE_LABELS: Record<BadgeState, string> = {
  locked: '未解锁',
  progress: '进行中',
  ready: '待点亮',
  lit: '已点亮',
  mastered: '已精通',
};

function badgePalette(state: BadgeState) {
  if (state === 'lit' || state === 'mastered') {
    return {
      ring: '#335CFE', glow: 'drop-shadow(0 16px 40px rgba(51,92,254,0.18))',
      outer: 'linear-gradient(180deg,rgba(246,249,255,0.98),rgba(225,233,255,0.98))',
      center: 'linear-gradient(180deg,rgba(83,121,255,0.98),rgba(44,78,233,0.98))',
      iconColor: '#fff', border: 'rgba(113,144,255,0.26)',
    };
  }
  if (state === 'ready') {
    return {
      ring: '#5B7BFE', glow: 'drop-shadow(0 12px 30px rgba(91,123,254,0.16))',
      outer: 'linear-gradient(180deg,#fff,rgba(240,244,255,1))',
      center: 'linear-gradient(180deg,rgba(239,244,255,1),rgba(221,231,255,1))',
      iconColor: '#335CFE', border: 'rgba(113,144,255,0.22)',
    };
  }
  if (state === 'progress') {
    return {
      ring: '#8FA4FF', glow: 'drop-shadow(0 8px 20px rgba(143,164,255,0.08))',
      outer: 'linear-gradient(180deg,#fff,rgba(243,246,253,1))',
      center: 'linear-gradient(180deg,#fff,rgba(243,246,253,1))',
      iconColor: '#5B7BFE', border: 'rgba(203,213,225,0.8)',
    };
  }
  return {
    ring: '#D5DCE8', glow: 'none',
    outer: 'linear-gradient(180deg,#fff,rgba(245,247,250,1))',
    center: 'linear-gradient(180deg,#fff,rgba(245,247,250,1))',
    iconColor: '#94a3b8', border: 'rgba(226,232,240,0.9)',
  };
}

function badgeIsLit(badge: BadgeProgress): boolean {
  return badge.state === 'lit' || badge.state === 'mastered';
}

function normalizeProgressPercent(value?: number | null): number {
  const raw = Number(value ?? 0);
  const pct = raw <= 1 ? raw * 100 : raw;
  if (!Number.isFinite(pct)) return 0;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

function BadgeToken({ badge, size = 'md' }: { badge: BadgeProgress; size?: 'md' | 'lg' }) {
  const pal = badgePalette(badge.state);
  const Icon = badgeIconFor(badge);
  const d = size === 'lg' ? 116 : 84;
  const r = size === 'lg' ? 44 : 31;
  const sw = size === 'lg' ? 5 : 4;
  const circ = 2 * Math.PI * r;
  const off = circ - (circ * badge.progressPercent) / 100;
  const innerSize = size === 'lg' ? 76 : 56;
  const iconSize = size === 'lg' ? 32 : 24;

  return (
    <div style={{ position: 'relative', width: d, height: d, filter: pal.glow }}>
      <div style={{ position: 'absolute', inset: 0, borderRadius: 999, border: `1px solid ${pal.border}`, background: pal.outer }} />
      <svg style={{ position: 'absolute', inset: 0, transform: 'rotate(-90deg)' }} viewBox={`0 0 ${d} ${d}`}>
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke="rgba(226,232,240,0.66)" strokeWidth={sw} />
        <circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke={pal.ring} strokeWidth={sw}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={off}
          style={{ transition: 'stroke-dashoffset 0.7s ease' }} />
      </svg>
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: innerSize, height: innerSize, borderRadius: 999,
        border: `1px solid ${pal.border}`, background: pal.center,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon width={iconSize} height={iconSize} color={pal.iconColor} strokeWidth={1.9} />
      </div>
    </div>
  );
}

function BadgeCell({ badge, onSelect }: { badge: BadgeProgress; onSelect: (badge: BadgeProgress) => void }) {
  const isLit = badgeIsLit(badge);
  const isReady = badge.state === 'ready';
  const inProgress = badge.state === 'progress';
  const nameClass = isLit ? 'lit' : inProgress || isReady ? 'prog' : 'lock';
  const statusClass = isLit ? 'lit' : isReady ? 'ready' : inProgress ? 'progress' : 'locked';
  const statusText = isLit ? STATE_LABELS[badge.state] : isReady ? '即将点亮' : inProgress ? `${badge.progressPercent}%` : '未解锁';

  return (
    <button className="gc-badge-cell" onClick={() => onSelect(badge)}>
      <BadgeToken badge={badge} size="md" />
      <span className={`gc-badge-name ${nameClass}`}>{badge.name}</span>
      <span className={`gc-badge-status ${statusClass}`}>{statusText}</span>
    </button>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Badge Modal
   ──────────────────────────────────────────────────────────────────── */
function BadgeModal({ badge, onClose }: { badge: BadgeProgress; onClose: () => void }) {
  const pal = badgePalette(badge.state);
  return (
    <div className="gc-modal-overlay" onClick={onClose}>
      <div className="gc-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <BadgeToken badge={badge} size="lg" />
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#0f172a', letterSpacing: -0.3 }}>{badge.name}</div>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#94a3b8', marginTop: 2 }}>{badge.categoryLabel} · +{badge.xp} XP</div>
              <span style={{
                display: 'inline-block', marginTop: 4, borderRadius: 999, padding: '2px 8px',
                fontSize: 10, fontWeight: 600,
                background: pal.iconColor === '#fff' ? 'rgba(51,92,254,0.1)' : '#f1f5f9',
                color: pal.iconColor === '#fff' ? '#335CFE' : '#475569',
              }}>{STATE_LABELS[badge.state]}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 999, color: '#94a3b8' }}>
            <X size={16} />
          </button>
        </div>

        <div>
          <div className="gc-modal-subtitle">为什么重要</div>
          <p style={{ fontSize: 13, lineHeight: 1.8, color: '#475569' }}>{badge.whyItMatters || badge.description}</p>
          {badge.description && badge.description !== badge.whyItMatters && (
            <p style={{ marginTop: 8, fontSize: 12, lineHeight: 1.7, color: '#64748b' }}>{badge.description}</p>
          )}
        </div>

        {badge.systemHowText && (
          <div style={{ marginTop: 16 }}>
            <div className="gc-modal-subtitle">系统如何识别</div>
            <p style={{ fontSize: 12, lineHeight: 1.7, color: '#64748b' }}>{badge.systemHowText}</p>
          </div>
        )}

        {/* Progress bar */}
        <div style={{ marginTop: 16, borderRadius: 18, background: '#f8fafc', padding: 16 }}>
          <div className="gc-modal-subtitle">当前进度</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>{badge.progressText}</span>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#335CFE' }}>{badge.progressPercent}%</span>
          </div>
          <div style={{ height: 8, borderRadius: 999, background: '#fff', overflow: 'hidden' }}>
            <div style={{ height: '100%', borderRadius: 999, background: '#335CFE', width: `${badge.progressPercent}%`, transition: 'width 0.5s' }} />
          </div>
          {badge.nextActionText && (
            <p style={{ marginTop: 12, fontSize: 11, lineHeight: 1.6, color: '#64748b' }}>{badge.nextActionText}</p>
          )}
        </div>

        {badge.unlockedAt && (
          <p style={{ marginTop: 12, fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>获得时间：{formatRelativeMoment(badge.unlockedAt)}</p>
        )}

        {badge.missingSignals.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#94a3b8', marginBottom: 8 }}>还差什么</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {badge.missingSignals.map((signal) => (
                <span key={signal} style={{ borderRadius: 999, border: '1px solid #e2e8f0', background: '#f8fafc', padding: '4px 10px', fontSize: 10, fontWeight: 500, color: '#64748b' }}>
                  {signal}
                </span>
              ))}
            </div>
          </div>
        )}

        {badge.evidence.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: '#94a3b8', marginBottom: 8 }}>达成证据</p>
            {badge.evidence.slice(0, 3).map((ev, i) => (
              <div key={i} style={{ borderRadius: 14, background: '#f8fafc', padding: '8px 12px', marginBottom: 8 }}>
                <p style={{ fontSize: 12, fontWeight: 500, color: '#334155' }}>{ev.title}</p>
                <p style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{ev.subtitle} · {formatRelativeMoment(ev.occurredAt)}</p>
              </div>
            ))}
          </div>
        )}

        {badge.actionLinks.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="gc-modal-subtitle">相关入口</div>
            <div className="gc-modal-link-list">
              {badge.actionLinks.map((link) => (
                <span key={`${link.tab}-${link.label}`} className="gc-modal-link-pill">{link.label}</span>
              ))}
            </div>
          </div>
        )}

        <button onClick={onClose} style={{
          marginTop: 20, width: '100%', borderRadius: 999, border: '1px solid #e2e8f0',
          background: '#fff', fontSize: 13, fontWeight: 500, color: '#475569', padding: '10px 0',
          cursor: 'pointer', transition: 'background 0.2s',
        }}>关闭</button>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Hexagonal Radar Chart — matches preview exactly
   ──────────────────────────────────────────────────────────────────── */
function AbilityRadar({ abilities, gaps }: { abilities: GrowthAbilityScore[]; gaps?: GrowthAbilityGap[] }) {
  const size = 320;
  const cx = 160, cy = 160, R = 110;
  const n = abilities.length;
  if (n < 3) return null;

  const angles = abilities.map((_, i) => (Math.PI * 2 * i / n) - Math.PI / 2);
  const hexPt = (angle: number, r: number): [number, number] => [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  const hexPoly = (r: number) => angles.map(a => hexPt(a, r).join(',')).join(' ');

  const gapMap = new Map((gaps || []).map(g => [g.abilityKey, g.requiredScore]));
  const hasRequired = gapMap.size > 0;

  const prevPts = abilities.map((ab, i) => hexPt(angles[i], R * ab.previousScore / 100).join(',')).join(' ');
  const curPts = abilities.map((ab, i) => hexPt(angles[i], R * ab.currentScore / 100).join(',')).join(' ');
  const reqPts = hasRequired
    ? abilities.map((ab, i) => hexPt(angles[i], R * (gapMap.get(ab.abilityKey) ?? ab.currentScore) / 100).join(',')).join(' ')
    : '';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {/* Grid */}
      {[0.2, 0.4, 0.6, 0.8, 1.0].map(s => (
        <polygon key={s} points={hexPoly(R * s)} fill="none" stroke="#f1f5f9" strokeWidth="1" />
      ))}
      {/* Axis lines */}
      {angles.map((a, i) => {
        const [ex, ey] = hexPt(a, R);
        return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="#f1f5f9" strokeWidth="1" />;
      })}
      {/* Previous (gray dashed) */}
      <polygon points={prevPts} fill="rgba(203,213,225,0.12)" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 3" />
      {/* Required (amber dashed) */}
      {hasRequired && (
        <polygon points={reqPts} fill="none" stroke="#f59e0b" strokeWidth="1.2" strokeDasharray="3 3" />
      )}
      {/* Current (blue filled) */}
      <polygon points={curPts} fill="rgba(91,123,254,0.15)" stroke="#5B7BFE" strokeWidth="2" />
      {/* Current dots */}
      {abilities.map((ab, i) => {
        const [dx, dy] = hexPt(angles[i], R * ab.currentScore / 100);
        return <circle key={ab.abilityKey} cx={dx} cy={dy} r={4} fill="#5B7BFE" stroke="#fff" strokeWidth={2} />;
      })}
      {/* Labels */}
      {abilities.map((ab, i) => {
        const [lx, ly] = hexPt(angles[i], R + 32);
        const anchor = lx < cx - 10 ? 'end' : lx > cx + 10 ? 'start' : 'middle';
        return (
          <g key={`lbl-${ab.abilityKey}`}>
            <text x={lx} y={ly - 2} textAnchor={anchor} dominantBaseline="central" fontSize="12" fontWeight="500" fill="#64748b">{ab.label}</text>
            <text x={lx} y={ly + 14} textAnchor={anchor} dominantBaseline="central" fontSize="11" fontWeight="600" fill="#5B7BFE">{ab.currentScore}</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 1: Quote Wall
   ══════════════════════════════════════════════════════════════════ */
function ExperienceWallTab() {
  const [entries, setEntries] = useState<HandbookEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'month' | 'quarter'>('all');

  const reloadExperienceWall = useCallback(async () => {
    try {
      const result = await getHandbook();
      setEntries(result.entries || []);
    } catch {
      setEntries([]);
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    reloadExperienceWall()
      .finally(() => setIsLoading(false));
  }, [reloadExperienceWall]);

  const sortedEntries = useMemo(() => {
    let filtered = [...entries];
    const now = new Date();
    if (filter === 'month') {
      const cutoff = new Date(now.getFullYear(), now.getMonth(), 1);
      filtered = filtered.filter((e) => new Date(e.createdAt) >= cutoff);
    } else if (filter === 'quarter') {
      const quarterStart = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
      filtered = filtered.filter((e) => new Date(e.createdAt) >= quarterStart);
    }
    return filtered.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [entries, filter]);

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><BookOpen size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载经验金句...</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="gc-section-header">
        <div>
          <div className="gc-section-title">组织经验金句</div>
          <span className="gc-section-hint">已沉淀 {sortedEntries.length} 条</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {(['all', 'month', 'quarter'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: filter === f ? '#EEF3FF' : 'transparent',
                color: filter === f ? '#335CFE' : '#94a3b8',
              }}
            >
              {{ all: '全部', month: '本月', quarter: '本季度' }[f]}
            </button>
          ))}
        </div>
      </div>

      {sortedEntries.length > 0 ? (
        <div className="gc-insight-grid">
          {sortedEntries.map((entry) => {
            const isAI = entry.authorUserName?.includes('大周') || entry.authorUserName?.includes('庆华') || entry.authorUserName?.includes('花花') || entry.authorUserName?.includes('罗茜茜') || entry.sourceType?.includes('ai');
            const hasLikes = entry.reuseCount > 0;
            const quoteText = pickQuoteText(entry);
            const authorName = entry.authorUserName || '团队';
            const projectName = entry.clientName || '';
            return (
              <div key={entry.id} className="gc-card gc-insight-card">
                <div className="gc-insight-quote">“{quoteText}”</div>
                <div className="gc-insight-meta">
                  <div className="gc-insight-author">
                    <div className={`gc-icon-token sm ${isAI ? 'brand' : 'gray'}`}>
                      {isAI ? <Sparkles size={10} color="#335CFE" /> : <Users size={10} color="#64748b" />}
                    </div>
                    <span className="gc-author-name">{authorName}</span>
                    {projectName && <span className="gc-source-tag">{projectName}</span>}
                    <span className="gc-source-tag">{sourceTypeCN(entry.sourceType || '经验')} · {weekLabelFromDate(entry.createdAt)}</span>
                  </div>
                  <button
                    className={`gc-like-btn${hasLikes ? ' liked' : ''}`}
                    onClick={() => {
                      markHandbookEntryReused(entry.id)
                        .then(() => reloadExperienceWall())
                        .catch(() => {});
                    }}
                  >
                    <Heart size={12} fill={hasLikes ? '#5B7BFE' : 'none'} color={hasLikes ? '#5B7BFE' : '#D1D5DB'} strokeWidth={2} />
                    {entry.reuseCount > 0 ? ` ${entry.reuseCount}` : ''}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="gc-empty">
          <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
            <BookOpen size={20} color="#335CFE" />
          </div>
          <div className="gc-empty-title">金句墙暂无内容</div>
          <div className="gc-empty-desc">完成任务复盘和经验沉淀后，值得复用的经验金句会展示在这里。</div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 2: Ability Growth
   ══════════════════════════════════════════════════════════════════ */
function AbilityGrowthTab({ overview }: { overview: GrowthOverview | null }) {
  const growthState = useGrowthOverviewState();
  const isLoading = !overview && (growthState?.isGrowthLoading ?? false);
  const abilities = overview?.abilities || [];
  const topGaps = useMemo(() => (overview?.abilityGaps || []).slice(0, 3), [overview]);

  const recentEntries = useMemo(() => {
    if (!overview?.recentEntries?.length) return [];
    const seen = new Map<string, XpLedgerEntry>();
    for (const entry of overview.recentEntries) {
      const dateKey = entry.createdAt?.slice(0, 10) || '';
      const key = `${entry.sourceType}|${entry.sourceId}|${entry.abilityKey}|${dateKey}`;
      const existing = seen.get(key);
      if (existing) {
        (existing as XpLedgerEntry & { totalXp: number }).totalXp += entry.totalXp || entry.delta;
      } else {
        seen.set(key, { ...entry });
      }
    }
    return [...seen.values()]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 8);
  }, [overview]);

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><BrainCircuit size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载能力数据...</div>
        </div>
      </div>
    );
  }

  if (!abilities.length) {
    return (
      <div className="gc-empty">
        <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none', width: 48, height: 48 }}>
          <BrainCircuit size={24} color="#335CFE" />
        </div>
        <div className="gc-empty-title">能力雷达待激活</div>
        <div className="gc-empty-desc">完成任务并写下复盘后，六维能力分布会在这里自动生成。系统会从会议、任务、复盘和知识沉淀中自动识别你的成长信号。</div>
      </div>
    );
  }

  return (
    <div className="gc-space-y">
      {/* Radar + Ability List */}
      <div className="gc-card gc-radar-card">
        <div className="gc-radar-visual">
          <AbilityRadar abilities={abilities} gaps={topGaps} />
          <div className="gc-radar-legend" style={{ justifyContent: 'center', marginTop: 12 }}>
            <span><span className="gc-radar-legend-dot" style={{ background: '#5B7BFE' }} />当前</span>
            <span><span className="gc-radar-legend-dot" style={{ background: '#cbd5e1' }} />上期</span>
            {topGaps.length > 0 && <span><span className="gc-radar-legend-dot" style={{ background: '#f59e0b' }} />要求</span>}
          </div>
        </div>
        <div className="gc-ability-list">
          {[...abilities].sort((a, b) => b.weeklyXp - a.weeklyXp).map((ab) => {
            const v = ABILITY_VISUALS[ab.abilityKey] || ABILITY_VISUALS.exec;
            const AbIcon = v.icon;
            return (
              <div key={ab.abilityKey}>
                <div className="gc-ability-row-top">
                  <div className="gc-ability-row-left">
                    <div className="gc-ability-icon-box" style={{ background: v.bg }}>
                      <AbIcon size={14} color={v.color} />
                    </div>
                    <span className="gc-ability-name">{ab.label}</span>
                    <span className="gc-ability-stage">{ab.stage}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className="gc-ability-xp">{ab.totalXp} XP</span>
                    {ab.weeklyXp > 0 && <span className="gc-ability-delta">+{ab.weeklyXp}</span>}
                  </div>
                </div>
                <div className="gc-ability-bar">
                  <div className="gc-ability-bar-fill" style={{ width: `${Math.min(ab.currentScore, 100)}%` }} />
                </div>
                <div className="gc-ability-evidence">{ab.evidence}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Timeline */}
      <div>
        <div className="gc-section-header">
          <div className="gc-section-title">成长时间线</div>
          <span className="gc-section-hint">近期能力变化</span>
        </div>
        {recentEntries.length > 0 ? (
          <div className="gc-card" style={{ padding: 20 }}>
            {recentEntries.map((entry, i) => {
              const v = ABILITY_VISUALS[entry.abilityKey] || ABILITY_VISUALS.exec;
              const AbIcon = v.icon;
              const isSpecial = entry.premiumXp > 0 || entry.xpType !== 'reflection' || entry.totalXp >= 14;
              const isLast = i === recentEntries.length - 1;
              return (
                <div key={`${entry.id}-${i}`} className="gc-timeline-entry">
                  <div className="gc-timeline-line">
                    <div className="gc-timeline-dot" style={{ background: v.bg }}>
                      <AbIcon size={14} color={v.color} />
                    </div>
                    {!isLast && <div className="gc-timeline-tail" />}
                  </div>
                  <div className="gc-timeline-content">
                    <div className="gc-timeline-top">
                      <div>
                        <div className="gc-timeline-title">{entry.sourceTitle || entry.reason || entry.abilityLabel}</div>
                        <div className="gc-timeline-tags">
                          <span className={`gc-timeline-tag ${isSpecial ? 'special' : 'normal'}`}>+{entry.totalXp || entry.delta} XP</span>
                          <span className="gc-timeline-tag normal">{entry.abilityLabel}</span>
                          {entry.clientName && <span className="gc-timeline-tag normal">{entry.clientName}</span>}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, color: '#94a3b8', whiteSpace: 'nowrap', flexShrink: 0 }}>
                        {formatRelativeMoment(entry.createdAt)}
                      </span>
                    </div>
                    {entry.contextSummary && (
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 6, lineHeight: 1.6 }}>{entry.contextSummary}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="gc-empty">
            <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
              <Sparkles size={20} color="#335CFE" />
            </div>
            <div className="gc-empty-title">本周成长记录待生成</div>
            <div className="gc-empty-desc">完成任务并写下复盘后，成长动态会在这里实时出现。</div>
          </div>
        )}
      </div>

      {/* Gap Cards */}
      {topGaps.length > 0 && (
        <div>
          <div className="gc-section-header">
            <div className="gc-section-title">能力缺口</div>
            <span className="gc-section-hint">需要重点突破的方向</span>
          </div>
          <div className="gc-gap-grid">
            {topGaps.map((gap) => {
              const v = ABILITY_VISUALS[gap.abilityKey] || ABILITY_VISUALS.exec;
              const GapIcon = v.icon;
              const pct = Math.round(gap.currentScore / gap.requiredScore * 100);
              return (
                <div key={`${gap.sourceType}-${gap.abilityKey}`} className="gc-card" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <div className="gc-ability-icon-box" style={{ background: v.bg }}>
                      <GapIcon size={16} color={v.color} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{gap.label}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{gap.currentScore} → {gap.requiredScore} (差 {gap.gap})</div>
                    </div>
                  </div>
                  <div className="gc-ability-bar" style={{ marginBottom: 8 }}>
                    <div className="gc-ability-bar-fill" style={{ width: `${pct}%`, background: '#f97316' }} />
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.6, marginBottom: 8 }}>{gap.reason}</div>
                  <div style={{ fontSize: 10, color: '#94a3b8' }}>来源: {gap.sourceLabel}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      {topGaps.length === 0 && (
        <div className="gc-no-gap">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600, color: '#047857' }}>
            <ShieldCheck size={16} color="#047857" />
            没有明显的能力缺口
          </div>
          <div style={{ fontSize: 11, color: 'rgba(4,120,87,0.7)', marginTop: 4, marginLeft: 24 }}>
            当前项目和事件线对你的能力要求都在覆盖范围内。
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Tab 3: Badges & Rank
   ══════════════════════════════════════════════════════════════════ */
function BadgesAndRankTab({ overview }: { overview: GrowthOverview | null }) {
  const [badgeBoard, setBadgeBoard] = useState<BadgeBoard | null>(null);
  const [selectedBadge, setSelectedBadge] = useState<BadgeProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    getGrowthBadges()
      .then(setBadgeBoard)
      .catch(() => setBadgeBoard(null))
      .finally(() => setIsLoading(false));
  }, []);

  const rank = overview?.rank;
  const totalXp = overview?.totalXp ?? 0;
  const weeklyXp = overview?.weeklyXp ?? 0;
  const boardOverview = badgeBoard?.overview;
  const categories = badgeBoard?.categories ?? [];
  const rankProgressPercent = normalizeProgressPercent(rank?.progress);

  const allBadges = useMemo(() => {
    return categories.flatMap((cat) => cat.badges);
  }, [categories]);

  const litBadges = useMemo(() => {
    return allBadges
      .filter(badgeIsLit)
      .sort((a, b) => new Date(b.unlockedAt || 0).getTime() - new Date(a.unlockedAt || 0).getTime());
  }, [allBadges]);

  const upcomingBadges = useMemo(() => {
    const ids = new Set(boardOverview?.upcomingBadgeIds ?? []);
    const explicit = allBadges.filter((badge) => ids.has(badge.id) && !badgeIsLit(badge));
    const fallback = allBadges.filter((badge) => !badgeIsLit(badge) && badge.progressPercent > 0);
    const source = explicit.length > 0 ? explicit : fallback;
    return source
      .slice()
      .sort((a, b) => b.progressPercent - a.progressPercent || a.name.localeCompare(b.name, 'zh-CN'))
      .slice(0, 8);
  }, [allBadges, boardOverview?.upcomingBadgeIds]);

  const totalBadgeCount = boardOverview?.totalBadges ?? allBadges.length;
  const litBadgeCount = boardOverview?.litBadges ?? litBadges.length;
  const badgeXp = boardOverview?.totalXp ?? litBadges.reduce((sum, badge) => sum + badge.xp, 0);
  const badgeStats = [
    { label: '已点亮', value: `${litBadgeCount}/${totalBadgeCount}`, icon: Trophy },
    { label: '即将点亮', value: upcomingBadges.length, icon: Sparkles },
    { label: '本月新增', value: boardOverview?.monthlyNewBadges ?? 0, icon: CalendarClock },
    { label: '徽章 XP', value: badgeXp.toLocaleString(), icon: Swords },
  ];

  if (isLoading) {
    return (
      <div className="gc-loading">
        <div style={{ textAlign: 'center' }}>
          <div className="gc-loading-icon"><Trophy size={20} color="#335CFE" /></div>
          <div className="gc-loading-text">加载徽章数据...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="gc-space-y">
      {/* XP Hero */}
      <div className="gc-xp-hero">
        <div className="gc-xp-hero-top">
          <div className="gc-icon-token xl brand-border">
            <Swords size={28} color="#335CFE" strokeWidth={1.8} />
          </div>
          <div>
            <div className="gc-xp-hero-rank">{rank?.fullLabel || '加载中'}</div>
            <div className="gc-xp-hero-num">
              {totalXp.toLocaleString()} <span className="gc-xp-label">XP</span>
            </div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            {weeklyXp > 0 && (
              <div className="gc-xp-hero-badge">
                <Sparkles size={12} /> +{weeklyXp} 本周
              </div>
            )}
          </div>
        </div>
        {rank && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>
                {rank.nextName ? `距${rank.nextName}还需 ${rank.xpToNext} XP` : '已达最高段位'}
              </span>
              <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8' }}>{rankProgressPercent}%</span>
            </div>
            <div className="gc-progress-track" style={{ height: 4 }}>
              <div className="gc-progress-fill" style={{ width: `${rankProgressPercent}%`, background: '#5B7BFE' }} />
            </div>
          </div>
        )}
        <div className="gc-xp-breakdown">
          {badgeStats.map((item) => {
            const BIcon = item.icon;
            return (
              <div key={item.label} className="gc-xp-break-card">
                <div className="gc-xp-break-top">
                  <BIcon size={14} color="#335CFE" />
                  <span className="gc-xp-break-label">{item.label}</span>
                </div>
                <div className="gc-xp-break-val">{item.value}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Badge milestones */}
      <div>
        <div className="gc-section-header">
          <div className="gc-section-title">我的徽章</div>
          <span className="gc-section-hint">已点亮 {litBadgeCount}/{totalBadgeCount}</span>
        </div>
        {allBadges.length > 0 ? (
          <div>
            {upcomingBadges.length > 0 && (
              <div className="gc-badge-section">
                <div className="gc-badge-section-head">
                  <div className="gc-badge-section-title">即将点亮</div>
                  <div className="gc-badge-section-hint">离完成最近的成长里程碑</div>
                </div>
                <div className="gc-badge-grid">
                  {upcomingBadges.map((badge) => (
                    <BadgeCell key={badge.id} badge={badge} onSelect={setSelectedBadge} />
                  ))}
                </div>
              </div>
            )}

            {litBadges.length > 0 && (
              <div className="gc-badge-section">
                <div className="gc-badge-section-head">
                  <div className="gc-badge-section-title">已点亮</div>
                  <div className="gc-badge-section-hint">展示最近点亮的 {Math.min(litBadges.length, 12)} 枚</div>
                </div>
                <div className="gc-badge-grid">
                  {litBadges.slice(0, 12).map((badge) => (
                    <BadgeCell key={badge.id} badge={badge} onSelect={setSelectedBadge} />
                  ))}
                </div>
              </div>
            )}

            <div className="gc-badge-section">
              <div className="gc-badge-section-head">
                <div className="gc-badge-section-title">全部徽章分类</div>
                <div className="gc-badge-section-hint">按能力方向查看未来成长目标</div>
              </div>
              <div className="gc-badge-category-list">
                {categories.map((category) => {
                  const CategoryIcon = ABILITY_VISUALS[category.abilityKey]?.icon || ABILITY_FALLBACK_ICONS[category.abilityKey] || Trophy;
                  const categoryLitCount = category.litCount ?? category.badges.filter(badgeIsLit).length;
                  const categoryTotalCount = category.totalCount ?? category.badges.length;
                  return (
                    <div key={category.id} className="gc-badge-category-card">
                      <div className="gc-badge-category-header">
                        <div className="gc-badge-category-title">
                          <div className="gc-icon-token sm brand">
                            <CategoryIcon size={12} color="#335CFE" />
                          </div>
                          <span className="gc-badge-category-name">{category.label}</span>
                        </div>
                        <span className="gc-badge-category-meta">已点亮 {categoryLitCount}/{categoryTotalCount}</span>
                      </div>
                      <div className="gc-badge-category-grid">
                        {category.badges.map((badge) => (
                          <BadgeCell key={badge.id} badge={badge} onSelect={setSelectedBadge} />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="gc-empty">
            <div className="gc-loading-icon" style={{ margin: '0 auto 12px', animation: 'none' }}>
              <Trophy size={20} color="#335CFE" />
            </div>
            <div className="gc-empty-title">还没有可展示的成长徽章</div>
            <div className="gc-empty-desc">徽章数据暂未就绪，完成更多工作后会自动解锁。</div>
          </div>
        )}
      </div>

      {/* Personal rank */}
      <div>
        <div className="gc-rank-header">
          <div className="gc-rank-header-left">
            <Trophy size={16} color="#f59e0b" />
            <div className="gc-section-title" style={{ marginBottom: 0 }}>我的成长段位</div>
          </div>
        </div>
        <div className="gc-card gc-rank-list">
          <div className="gc-rank-row">
            <div className="gc-icon-token md brand">
              <Users size={14} color="#335CFE" />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="gc-rank-name-text">{overview?.userName || '当前用户'} · {rank?.fullLabel || '成长段位'}</div>
              <div className="gc-rank-meta">
                {rank?.nextName ? `下一段位：${rank.nextName}，还需 ${rank.xpToNext} XP` : '已达当前最高段位'}
              </div>
            </div>
            <div className="gc-rank-xp">{totalXp.toLocaleString()} XP</div>
          </div>
          <div className="gc-rank-bar">
            <div className="gc-rank-bar-fill" style={{ width: `${rankProgressPercent}%` }} />
          </div>
          {weeklyXp > 0 && (
            <div className="gc-rank-week">
              <span>本周新增成长值</span>
              <span>+{weeklyXp} XP</span>
            </div>
          )}
        </div>
      </div>

      {selectedBadge && <BadgeModal badge={selectedBadge} onClose={() => setSelectedBadge(null)} />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Main Export — GrowthCenterView
   ══════════════════════════════════════════════════════════════════ */
type GrowthTab = 'experience' | 'ability' | 'badges';

const TABS: { key: GrowthTab; label: string }[] = [
  { key: 'experience', label: '经验墙' },
  { key: 'ability', label: '能力成长' },
  { key: 'badges', label: '徽章与排行' },
];

export function GrowthCenterView() {
  const [activeTab, setActiveTab] = useState<GrowthTab>('experience');
  const growthState = useGrowthOverviewState();
  const [headerOverview, setHeaderOverview] = useState<GrowthOverview | null>(null);

  // Inject CSS on mount
  useEffect(() => { injectGrowthCSS(); }, []);

  // Load overview
  useEffect(() => {
    if (growthState?.growthOverview) return;
    getGrowthOverview().then(setHeaderOverview).catch(() => undefined);
  }, []);

  const overview = growthState?.growthOverview ?? headerOverview;
  const rankLabel = overview?.rank?.fullLabel || '加载中';
  const totalXp = overview?.totalXp ?? 0;
  const weeklyXp = overview?.weeklyXp ?? 0;

  return (
    <div className="gc-root">
      {/* Header */}
      <div className="gc-header">
        <div className="gc-header-inner">
          <div className="gc-header-top">
            <div>
              <div className="gc-page-title">成长中心</div>
              <div className="gc-page-subtitle">把工作经验变成组织资产</div>
            </div>
            <div className="gc-xp-area">
              <div className="gc-rank-chip">
                <Swords size={14} color="#335CFE" strokeWidth={2} />
                {rankLabel}
              </div>
              <div>
                <div className="gc-xp-num">{totalXp.toLocaleString()} <span className="gc-xp-label">XP</span></div>
                {weeklyXp > 0 && <div className="gc-xp-week">+{weeklyXp}</div>}
              </div>
            </div>
          </div>
          <div className="gc-tab-bar">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={`gc-tab-btn${activeTab === tab.key ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="gc-content">
        <div className="gc-content-inner">
          {activeTab === 'experience' && <ExperienceWallTab />}
          {activeTab === 'ability' && <AbilityGrowthTab overview={overview} />}
          {activeTab === 'badges' && <BadgesAndRankTab overview={overview} />}
        </div>
      </div>
    </div>
  );
}

export default GrowthCenterView;
