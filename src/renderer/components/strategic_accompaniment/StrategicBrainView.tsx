import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  BrainCircuit, Sparkles, FileText, CheckCircle, MessageCircle,
  GitBranch, BookOpen, Award, Layers, ChevronDown,
  AlertCircle, ClipboardList, Check, Folder, Target, FolderTree,
  Activity, Lightbulb, Bot, Clock, User, PenLine, Calendar,
  ArrowLeft, AlertTriangle, ChevronRight, XCircle,
  Users, Flag, AlertOctagon, HelpCircle, CornerDownRight
} from 'lucide-react';
import { getBrainDashboard, type BrainDashboard, type BrainPulse, type BrainClientData } from '../../lib/api';

// --- Mock Data ---

const CLIENTS = ['全部客户', '为爱黔行', 'CFFC', '日慈基金会', '益语智库', '云南儿童资助研究', '顾源源', '顾源源文章'];

const TABS = [
  { id: 'pulse', label: '大脑脉搏' },
  { id: 'thoughts', label: '思考与研判' },
  { id: 'clients', label: '项目认知' },
  { id: 'learning', label: '学习清单' }
];

const PULSE_METRICS_1 = [
  { icon: BrainCircuit, label: '组织记忆', value: '1,847' },
  { icon: FileText, label: '资料归档', value: '390' },
  { icon: CheckCircle, label: '任务追踪', value: '19' },
  { icon: MessageCircle, label: 'AI 对话', value: '549' },
];

const PULSE_METRICS_2 = [
  { icon: GitBranch, label: '事件线', value: '8' },
  { icon: BookOpen, label: '知识画像', value: '19' },
  { icon: Award, label: '成长徽章', value: '4' },
  { icon: Layers, label: '经验沉淀', value: '5' },
];

// Client name → client_id mapping (for task association)
const CLIENT_ID_MAP: Record<string, string> = {
  'CFFC': 'client_a4d1db29a7',
  '为爱黔行': 'client_cffc',
  '日慈基金会': 'client_284afd836e',
  '益语智库': 'client_53d82aa249',
  '云南儿童资助研究': 'client_bda0f1d379',
  '顾源源': 'client_952be522fb',
  '顾源源文章': 'client_30a392788c',
};

export type ThoughtTaskPayload = {
  suggestion: string;
  ceoComment: string;
  thoughtLine: string;
  clientId: string;
  dueDate: string;
};

const THOUGHTS_DATA = [
  {
    id: 1,
    line: '洪峰讨论赋能合作',
    clientName: 'CFFC',
    confidence: 85,
    observation: '洪峰正在推动鸿鹄计划的 AI 技术合作，你已经跟他聊过 3 次，方向基本锁定在 AI 赋能方向。但合作方案的要点和 CFFC 侧的对接人目前还没有正式记录进系统。',
    suggestion: '方向确认后最容易出现的问题是"共识停在口头"。建议本周做两件事：把合作要点写成一份简短备忘录，哪怕只有半页；同时确认 CFFC 侧的具体对接人和第一个时间节点。如果这周不落纸面，双方可能都觉得在推进，但实际没人动手。',
    dueDateHint: '本周',
    tags: [{ icon: MessageCircle, text: '3 次对话' }, { icon: GitBranch, text: '1 条事件线' }, { icon: Clock, text: '上次更新：本周' }]
  },
  {
    id: 2,
    line: '日慈战略陪伴',
    clientName: '日慈基金会',
    confidence: 58,
    observation: '日慈 Q1 三个项目都进入了复盘阶段，笑雨和高老师的复盘记录已经进入系统。但教师赋能项目的项目设计部分有缺口，目前没有人在跟进补完。',
    suggestion: '教师赋能的设计补完是当前最具体的卡点。如果这周不推进，Q2 的项目迭代就缺少 Q1 结论作为基础。建议指定一个人把教师赋能的设计缺口列成一份问题清单——不需要写完整方案，有清单就能让下一步有抓手。',
    dueDateHint: '本周',
    tags: [{ icon: FileText, text: '来自复盘数据' }, { icon: GitBranch, text: '1 条事件线' }]
  },
  {
    id: 5,
    isSystem: true,
    line: '系统观察',
    clientName: '',
    confidence: undefined as number | undefined,
    observation: 'W14 周复盘已创建但内容为空。已准备的 6 场会议没有一场完成全流程。当前系统中最活跃的信号来源是 AI 对话（549 条），但对话中的洞察还没有被结构化地沉淀下来。',
    suggestion: '复盘和完整的会议记录是系统提升认知最快的两个渠道——比上传 100 份文档都有效，因为它们直接包含你们当下的判断和决策。建议本周至少完成一件：写一份有内容的周复盘，或者把一场会议走完全流程。做哪个都行，系统都能从中学到很多。',
    dueDateHint: '本周',
    tags: [{ icon: Bot, text: '来源：周复盘 + 会议系统' }]
  }
];

const CLIENTS_DNA_DATA = [
  {
    name: 'CFFC', confidence: 85, stage: '战略陪伴中',
    desc: '我对 CFFC 了解最深。读过他们 168 份文档，完成了组织、项目、团队、市场四篇 DNA 画像。我知道他们 Q2 的两个目标——提升项目传播清晰度和补齐捐赠人关系素材——都跟品牌表达有关。',
    metrics: [
      { icon: Folder, label: '168 文档' }, { icon: FileText, label: '4 篇 DNA' },
      { icon: Activity, label: '3 事件线' }, { icon: Target, label: '2 个 Q2 目标' }
    ]
  },
  {
    name: '为爱黔行', confidence: 62, stage: '审计中',
    desc: '91 份文档已读完，资料量在所有客户中排第二。庆华正在输出战略诊断提纲。但我还没有生成任何 DNA 画像——一旦诊断提纲完成，我建议立刻生成，能大幅提升认知结构。',
    metrics: [
      { icon: Folder, label: '91 文档' }, { icon: FileText, label: '0 篇 DNA' },
      { icon: Activity, label: '1 事件线' }, { icon: FolderTree, label: '8 个文件夹' }
    ],
    alert: 'DNA 画像尚未生成——建议在诊断完成后立即创建'
  },
  {
    name: '顾源源', confidence: 38, stage: '资料待补',
    desc: '目前只有 1 份文档，没有 DNA 画像，也没有事件线。我对你个人项目的理解还非常初步。多跟我聊聊你在做什么，或者把相关资料放进来，我会学得很快。',
    metrics: [
      { icon: Folder, label: '1 文档' }, { icon: FileText, label: '0 篇 DNA' },
      { icon: Activity, label: '0 事件线' }
    ]
  }
];

const LEARNING_REQUESTS = [
  {
    title: '完成一场完整的会议记录',
    desc: '你准备了 6 场会议，但没有一场完成了全流程——从准备到纪要到提取决策。会议是我学习组织运转的最高效渠道。只要完成 1 场，我对相关客户的判断能力就会显著提升。',
    btn1: '开一场会', btn2: '上传已有纪要'
  }
];

// --- 详情页专属 MOCK 数据 ---
const PROJECT_DETAILS: Record<string, any> = {
  'CFFC': {
    name: 'CFFC',
    stage: '战略陪伴中',
    confidence: 85,
    docsCount: 168,
    conversations: 276,
    understanding: {
      what: "CFFC 对外不再分散讲多个'产品群'，而是讲一个平台型业务群，用'业务层—网络层—资产层'的结构解释其如何运转、升级和产生行业复利。",
      people: [
        { name: '李超', role: '战略负责人' },
        { name: '史成斌', role: '业务运营' },
        { name: '吴艾思', role: '品牌传播' },
        { name: '顾源源', role: '战略陪伴顾问' },
        { name: '洪峰', role: '鸿鹄计划 AI 合作方' }
      ],
      stageDesc: "当前处于战略陪伴阶段。3 条活跃事件线：洪峰合作（85%，方向锁定待落地）、项目结项（14%，几乎无信息）、战略讨论会（70%，聚焦鸿鹄计划）。上一次有内容进来是洪峰合作相关的文档上传。",
      goals: [] as string[],
      challenges: [
        "缺乏行业筹款下滑的量化数据",
        "公众信任危机的案例缺少量化影响",
        "资源本地化收缩缺少地域分布数据"
      ],
      boundaries: [
        { level: 'missing', text: '"cffc 项目结项"事件线几乎无信息（conf 14%）', action: '补充结项报告，我就能判断交付质量和遗留问题' },
        { level: 'weak', text: '团队介绍只有 829 字', action: '补充后我能判断"谁适合推什么"' },
        { level: 'weak', text: '市场背景缺少筹款下滑数据', action: '补充后行业判断从定性变定量' }
      ]
    },
    dimensions: [
      { name: 'DNA 画像', status: 'ready', value: '4篇' },
      { name: '深度分析', status: 'missing', value: '0次' },
      { name: '会议记录', status: 'missing', value: '0场完成' },
      { name: '业务目标', status: 'missing', value: '0个' },
      { name: '业务模块', status: 'missing', value: '0个' },
      { name: '关键流程', status: 'missing', value: '0条' },
      { name: '复盘信号', status: 'weak', value: '有但空' },
      { name: '任务与事件线', status: 'ready', value: '8任务3线' }
    ],
    supplements: [
      {
        name: '深度分析', status: 'missing',
        desc: '深度分析是我对项目做过的系统性思考——不是扫一眼文档摘要，而是针对一个具体问题做过的深入推理。有了它，我在战略研判中能引用自己之前的分析结论，建议的逻辑链条会更严密。',
        buttons: ['发起一次深度分析']
      },
      {
        name: '会议记录', status: 'missing',
        desc: '会议是我了解你们真实讨论和决策的唯一渠道。文档告诉我"事情是什么样的"，但会议告诉我"你们是怎么想的、怎么决定的"。完成一场完整的会议流程，我对这个项目的判断能力会有质的飞跃。',
        buttons: ['开一场会', '上传已有纪要']
      },
      {
        name: '业务目标', status: 'missing',
        desc: '没有目标锚点，我无法判断什么算"进展"、什么算"偏离"。目前我只能描述正在发生什么，但无法评价这些事情对不对、快不快。设定哪怕一个核心目标，我的研判就能从描述变成评价。',
        buttons: ['设定业务目标']
      },
      {
        name: '复盘信号', status: 'weak',
        desc: '复盘是我学习你们当周真实节奏的最快渠道——哪些事在推进、哪些卡住了、方向有没有变。它比文档更新鲜，比任务状态更有深度。每写一次复盘，我对这个项目下一周的研判质量都会明显提升。',
        buttons: ['去写周复盘']
      }
    ]
  },
  '顾源源': {
    name: '顾源源',
    stage: '资料待补',
    confidence: 38,
    docsCount: 1,
    conversations: 2,
    understanding: {
      what: null,
      people: [] as Array<{ name: string; role: string }>,
      stageDesc: null,
      goals: [] as string[],
      challenges: [] as string[],
      boundaries: [
        { level: 'missing', text: '我对这个项目的认知非常初步，只有 1 份文档', action: '上传任何项目相关资料都会显著提升我的理解' },
        { level: 'missing', text: '没有任何 DNA 画像', action: '先生成组织介绍，我就能建立基本的认知框架' },
        { level: 'missing', text: '没有事件线', action: '创建一条核心事件线，我就能开始追踪项目推进动态' },
        { level: 'missing', text: '缺乏 AI 对话', action: '聊一次就能快速建立初步理解' }
      ]
    },
    dimensions: [
      { name: 'DNA 画像', status: 'missing', value: '0篇' },
      { name: '深度分析', status: 'missing', value: '0次' },
      { name: '会议记录', status: 'missing', value: '0场完成' },
      { name: '业务目标', status: 'missing', value: '0个' },
      { name: '业务模块', status: 'missing', value: '0个' },
      { name: '关键流程', status: 'missing', value: '0条' },
      { name: '复盘信号', status: 'missing', value: '0个' },
      { name: '任务与事件线', status: 'missing', value: '0任务0线' }
    ],
    supplements: [
      {
        name: 'DNA 画像', status: 'missing',
        desc: 'DNA 画像是我理解项目的基础框架——组织是谁、做什么业务、团队怎么分工、市场环境如何。没有它，我只能从零散的文档中拼凑理解，容易遗漏关键信息，也容易被单一文档的视角带偏。生成后，我后续收到的每一份新资料都能自动归位到正确的认知结构中。',
        buttons: ['一键生成全部 DNA', '上传资料后生成']
      },
      {
        name: '任务与事件线', status: 'missing',
        desc: '任务和事件线是我追踪项目动态的基本信号源。没有它们，我只能基于静态文档做判断，无法感知项目的"脉搏"——谁在做什么、做到哪了、卡在哪了。',
        buttons: ['创建事件线', '创建任务']
      }
    ]
  }
};


// --- Helpers ---

const getConfColor = (conf?: number) => {
  if (conf === undefined) return '#94a3b8';
  if (conf >= 70) return '#3b82f6';
  if (conf >= 50) return '#f59e0b';
  return '#ef4444';
};

const getConfBg = (conf?: number) => {
  if (conf === undefined) return 'bg-slate-100 text-slate-500';
  if (conf >= 70) return 'bg-blue-50 text-blue-600';
  if (conf >= 50) return 'bg-amber-50 text-amber-600';
  return 'bg-red-50 text-red-600';
};

function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: (event: MouseEvent) => void) {
  useEffect(() => {
    const listener = (event: MouseEvent) => {
      if (!ref.current || ref.current.contains(event.target as Node)) return;
      handler(event);
    };
    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [ref, handler]);
}

// --- Detail View Components ---

function DetailHeader({ client, onBack }: { client: any; onBack: () => void }) {
  return (
    <header className="sticky top-0 left-0 right-0 bg-white/90 backdrop-blur-xl border-b border-slate-200/60 z-50 px-6 sm:px-8 py-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onBack}
          className="w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50 transition-colors"
        >
          <ArrowLeft size={16} className="text-slate-600" />
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-800">{client.name}</h1>
          <span className="bg-slate-100 border border-slate-200 text-slate-600 text-[11px] font-bold px-2.5 py-1 rounded-lg">
            {client.stage}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-100">
          <Folder size={12} className="text-slate-400" />
          <span className="text-[12px] font-semibold text-slate-500">{client.docsCount} 文档</span>
        </div>
        <div className={`px-3 py-1.5 rounded-full text-[12px] font-bold flex items-center gap-1.5 ${getConfBg(client.confidence)}`}>
          <Activity size={14} className="opacity-80" />
          Confidence {client.confidence}%
        </div>
      </div>
    </header>
  );
}

function DimensionGrid({ dimensions }: { dimensions: any[] }) {
  const readyCount = dimensions.filter((d: any) => d.status === 'ready').length;
  return (
    <div className="mt-8">
      <div className="flex items-baseline justify-between mb-4 px-1">
        <h2 className="text-[15px] font-bold text-slate-800">认知维度</h2>
        <span className="text-[12px] font-bold text-blue-600">就绪 {readyCount}/8</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
        {dimensions.map((dim: any, i: number) => {
          const isReady = dim.status === 'ready';
          const isWeak = dim.status === 'weak';
          return (
            <div key={i} className="bg-white rounded-[16px] border border-slate-100 p-3.5 min-h-[80px] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              <div className="flex items-start gap-2 mb-2">
                {isReady && <CheckCircle size={12} className="text-emerald-500 mt-0.5 shrink-0" />}
                {isWeak && <AlertTriangle size={12} className="text-amber-500 mt-0.5 shrink-0" />}
                {!isReady && !isWeak && <XCircle size={12} className="text-red-500 mt-0.5 shrink-0" />}
                <span className={`text-[12px] font-bold ${isReady || isWeak ? 'text-slate-800' : 'text-slate-400'}`}>
                  {dim.name}
                </span>
              </div>
              <div className="flex items-center gap-1.5 pl-5">
                {isReady && <span className="text-[11px] font-semibold text-slate-500">{dim.value}</span>}
                {isWeak && (
                  <>
                    <span className="text-[11px] font-semibold text-slate-500">{dim.value}</span>
                    <span className="bg-orange-50 text-orange-600 text-[9px] font-bold px-1.5 py-0.5 rounded-full">薄弱</span>
                  </>
                )}
                {!isReady && !isWeak && (
                  <span className="bg-red-50 text-red-600 text-[9px] font-bold px-1.5 py-0.5 rounded-full">未就绪</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProjectDetailView({ clientId, onBack }: { clientId: string; onBack: () => void }) {
  const data = PROJECT_DETAILS[clientId] || PROJECT_DETAILS['CFFC'];
  const u = data.understanding;

  return (
    <div className="animate-in fade-in duration-300">
      <DetailHeader client={data} onBack={onBack} />
      <div className="max-w-full mx-auto px-6 py-8 pb-24">
        {/* ❶ 我对这个项目的理解 */}
        <section
          className="rounded-[28px] border border-blue-100 p-6 sm:p-8 relative"
          style={{
            backgroundImage: 'radial-gradient(circle at top left, rgba(51,92,254,0.04), transparent 40%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
            boxShadow: '0 10px 40px -10px rgba(51,92,254,0.06)'
          }}
        >
          <div className="inline-flex items-center gap-1.5 bg-blue-50/80 border border-blue-100/80 rounded-full px-3.5 py-1.5 mb-6 shadow-sm">
            <BrainCircuit size={14} className="text-blue-600" />
            <span className="text-[12px] font-bold text-blue-600 tracking-wide">系统对项目的完整认知</span>
          </div>
          <div className="space-y-7">
            {/* 做什么 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2.5 flex items-center gap-1.5">
                <Target size={14} className="text-blue-500" /> 这个项目是做什么的
              </h3>
              {u.what ? (
                <p className="text-[13px] leading-[2.0] text-slate-600 font-medium pl-5">{u.what}</p>
              ) : (
                <p className="text-[13px] leading-[2.0] text-slate-400 italic pl-5">"我还不了解这个项目的基本情况。上传一份组织介绍或项目说明，我就能建立起初步认知。"</p>
              )}
            </div>
            {/* 关键人物 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2.5 flex items-center gap-1.5">
                <Users size={14} className="text-blue-500" /> 关键人物
              </h3>
              {u.people && u.people.length > 0 ? (
                <div className="bg-slate-50/80 rounded-[14px] p-3 border border-slate-100 ml-5">
                  {u.people.map((p: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 py-1.5">
                      <span className="text-[13px] font-bold text-slate-800 w-16">{p.name}</span>
                      <span className="text-[13px] text-slate-500">— {p.role}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[13px] leading-[2.0] text-slate-400 italic pl-5">"我还不知道这个项目的关键人物。补充团队介绍 DNA 或在对话中告诉我。"</p>
              )}
            </div>
            {/* 阶段 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2.5 flex items-center gap-1.5">
                <Activity size={14} className="text-blue-500" /> 当前阶段与推进状态
              </h3>
              {u.stageDesc ? (
                <p className="text-[13px] leading-[2.0] text-slate-600 font-medium pl-5">{u.stageDesc}</p>
              ) : (
                <p className="text-[13px] leading-[2.0] text-slate-400 italic pl-5">"当前阶段：待导入资料。没有活跃的事件线。我无法追踪这个项目的动态推进——建议创建至少一条事件线来记录核心工作流。"</p>
              )}
            </div>
            {/* 目标 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2.5 flex items-center gap-1.5">
                <Flag size={14} className="text-blue-500" /> 业务目标
              </h3>
              {u.goals && u.goals.length > 0 ? (
                <ul className="text-[13px] leading-[2.0] text-slate-600 font-medium list-decimal pl-9">
                  {u.goals.map((g: string, i: number) => <li key={i}>{g}</li>)}
                </ul>
              ) : (
                <p className="text-[13px] leading-[2.0] text-slate-400 italic pl-5">"我还不知道这个项目当前的核心目标。没有目标锚点，我的研判就缺少方向参照——不知道什么算'推进了'、什么算'偏了'。"</p>
              )}
            </div>
            {/* 挑战 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-2.5 flex items-center gap-1.5">
                <AlertOctagon size={14} className="text-blue-500" /> 主要挑战与风险
              </h3>
              {u.challenges && u.challenges.length > 0 ? (
                <div className="space-y-2 pl-5">
                  {u.challenges.map((c: string, i: number) => (
                    <div key={i} className="flex items-start gap-2">
                      <AlertTriangle size={14} className="text-orange-500 mt-1 shrink-0" />
                      <span className="text-[13px] leading-[1.8] text-slate-700 font-medium">{c}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[13px] leading-[2.0] text-slate-400 italic pl-5">"暂未识别到明确的挑战信号。随着更多复盘和会议记录进入系统，我会逐渐发现需要关注的问题。"</p>
              )}
            </div>
            {/* 认知边界 */}
            <div>
              <h3 className="text-[13px] font-bold text-slate-800 mb-3.5 flex items-center gap-1.5">
                <HelpCircle size={14} className="text-blue-500" /> 认知边界 — 我不确定的地方
              </h3>
              <div className="space-y-2.5 pl-5">
                {u.boundaries.map((b: any, i: number) => (
                  <div key={i} className={`p-4 rounded-[16px] border ${b.level === 'missing' ? 'bg-red-50/50 border-red-100' : 'bg-orange-50/50 border-orange-100'}`}>
                    <div className="flex items-start gap-2 mb-1.5">
                      {b.level === 'missing' ? (
                        <XCircle size={14} className="text-red-500 mt-[2px] shrink-0" />
                      ) : (
                        <AlertTriangle size={14} className="text-orange-500 mt-[2px] shrink-0" />
                      )}
                      <span className={`text-[13px] font-bold ${b.level === 'missing' ? 'text-red-800' : 'text-orange-800'}`}>{b.text}</span>
                    </div>
                    <div className="flex items-start gap-1.5 pl-5">
                      <CornerDownRight size={14} className="text-slate-400 mt-[2px] shrink-0" />
                      <span className="text-[12px] leading-[1.7] text-slate-600 font-semibold">{b.action}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ❷ 认知维度看板 */}
        <DimensionGrid dimensions={data.dimensions} />

        {/* ❸ 帮我补充 */}
        {data.supplements.length > 0 && (
          <section className="mt-10">
            <div className="flex items-baseline justify-between mb-4 px-1">
              <h2 className="text-[15px] font-bold text-slate-800">帮我补充</h2>
              <span className="text-[12px] font-medium text-slate-400">每一步都让我的判断更准确</span>
            </div>
            <div className="space-y-3">
              {data.supplements.map((sup: any, i: number) => (
                <div key={i} className="bg-white border border-slate-200 rounded-[20px] p-5 shadow-sm hover:border-slate-300 transition-colors">
                  <div className="flex items-center gap-2.5 mb-3">
                    {sup.status === 'missing' ? (
                      <XCircle size={16} className="text-red-500 shrink-0" />
                    ) : (
                      <AlertTriangle size={16} className="text-amber-500 shrink-0" />
                    )}
                    <h3 className="text-[14px] font-bold text-slate-800">{sup.name}</h3>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${sup.status === 'missing' ? 'bg-red-50 text-red-600' : 'bg-orange-50 text-orange-600'}`}>
                      {sup.status === 'missing' ? '缺失' : '薄弱'}
                    </span>
                  </div>
                  <p className="text-[13px] leading-[1.8] text-slate-600 font-medium mb-4 pl-[26px]">{sup.desc}</p>
                  <div className="flex flex-wrap items-center gap-2 pl-[26px]">
                    {sup.buttons.map((btn: string, idx: number) => (
                      <button key={idx} type="button" className={`rounded-xl px-4 py-2 text-[12px] font-bold transition-colors shadow-sm ${
                        idx === 0
                          ? 'bg-slate-800 text-white hover:bg-slate-700'
                          : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}>
                        {btn}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ❹ 澄清入口 */}
        <section className="mt-8">
          <button
            type="button"
            className="w-full group text-left p-5 rounded-[22px] border border-blue-100 relative overflow-hidden transition-all hover:shadow-[0_4px_16px_rgba(51,92,254,0.08)]"
            style={{ background: 'radial-gradient(circle at top left, rgba(51,92,254,0.04), transparent 40%), #fff' }}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <MessageCircle size={18} className="text-blue-600" />
                  <h3 className="text-[14px] font-bold text-slate-800">以上理解有偏差？跟我聊聊</h3>
                </div>
                <p className="text-[12px] leading-[1.7] text-slate-500 font-medium pl-6 max-w-[90%]">
                  直接告诉我哪里理解错了。你的纠正是我提升最快的方式——比上传 10 份文档都有效。
                </p>
                <div className="pl-6 mt-2">
                  <span className="text-[11px] font-semibold text-slate-400">已有 {data.conversations} 条对话记录</span>
                </div>
              </div>
              <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center shrink-0 group-hover:bg-blue-100 transition-colors">
                <ChevronRight size={16} className="text-blue-500" />
              </div>
            </div>
          </button>
        </section>
      </div>
    </div>
  );
}


// ================= TAB CONTENT =================

function PulseTab({ pulse }: { pulse: BrainPulse | null }) {
  const p = pulse;
  const metrics1 = [
    { icon: BrainCircuit, label: '组织记忆', value: p ? p.memoryCount.toLocaleString() : '...' },
    { icon: FileText, label: '资料归档', value: p ? p.docCount.toLocaleString() : '...' },
    { icon: CheckCircle, label: '任务追踪', value: p ? p.taskCount.toLocaleString() : '...' },
    { icon: MessageCircle, label: 'AI 对话', value: p ? p.chatCount.toLocaleString() : '...' },
  ];
  const metrics2 = [
    { icon: GitBranch, label: '事件线', value: p ? p.eventLineCount.toLocaleString() : '...' },
    { icon: BookOpen, label: '知识画像', value: p ? p.dnaCount.toLocaleString() : '...' },
    { icon: Award, label: '成长徽章', value: p ? p.badgeCount.toLocaleString() : '...' },
    { icon: Layers, label: '经验沉淀', value: p ? p.handbookCount.toLocaleString() : '...' },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-[32px] border border-blue-100 p-8 bg-white" style={{ backgroundImage: 'radial-gradient(circle at 10% 10%, rgba(59, 130, 246, 0.08), transparent 50%), linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)', boxShadow: '0 20px 40px -15px rgba(15,23,42,0.05)' }}>
        <div className="flex items-start justify-between mb-8">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100/50 flex items-center justify-center shadow-inner">
              <BrainCircuit size={32} className="text-blue-600" strokeWidth={1.5} />
            </div>
            <div>
              <div className="text-[22px] font-bold text-slate-800 tracking-tight flex items-baseline gap-2">
                已陪伴 <span className="tabular-nums text-2xl text-blue-600">{p ? p.daysAccompanied : '...'}</span> 天
              </div>
              <div className="text-[12px] font-medium text-slate-400 mt-1 flex items-center gap-1.5">
                <Clock size={12} /> {p ? `${p.reviewCount} 次复盘 · ${p.meetingCount} 场会议` : '加载中...'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 bg-emerald-50 text-emerald-600 px-4 py-2 rounded-full border border-emerald-100/50 shadow-sm">
            <Sparkles size={14} />
            <span className="text-[12px] font-semibold">本周 +{p ? p.weeklyNewFacts : '...'} 条新记忆</span>
          </div>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics1.map((m, i) => (
              <div key={i} className="bg-white/80 border border-slate-100 rounded-[20px] p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2">
                  <m.icon size={16} className="text-blue-500" />
                  <span className="text-[11px] font-semibold text-slate-400 tracking-wide uppercase">{m.label}</span>
                </div>
                <div className="text-[24px] font-bold text-slate-800 tracking-tight mt-2 tabular-nums">{m.value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics2.map((m, i) => (
              <div key={i} className="bg-white/80 border border-slate-100 rounded-[20px] p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2">
                  <m.icon size={16} className="text-indigo-400" />
                  <span className="text-[11px] font-semibold text-slate-400 tracking-wide uppercase">{m.label}</span>
                </div>
                <div className="text-[24px] font-bold text-slate-800 tracking-tight mt-2 tabular-nums">{m.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ThoughtCard({ thought, onCreateTask }: { thought: any; onCreateTask?: (payload: ThoughtTaskPayload) => void }) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [reviewText, setReviewText] = useState('');
  const [taskCreated, setTaskCreated] = useState(false);

  const handleCreateTask = () => {
    // If there's a comment, save it as review first
    if (reviewText.trim()) {
      setIsSubmitted(true);
      setIsEditing(false);
    }
    setTaskCreated(true);

    // Build the task description: suggestion + optional CEO comment
    const clientId = thought.clientName ? (CLIENT_ID_MAP[thought.clientName] || '') : '';
    const today = new Date();
    const endOfWeek = new Date(today);
    endOfWeek.setDate(today.getDate() + (7 - today.getDay()));
    const dueDate = thought.dueDateHint === '本周' ? endOfWeek.toISOString().slice(0, 10) : '';

    onCreateTask?.({
      suggestion: thought.suggestion,
      ceoComment: reviewText.trim(),
      thoughtLine: thought.line,
      clientId,
      dueDate,
    });
  };

  const handleConfirm = () => {
    if (reviewText.trim()) {
      setIsSubmitted(true);
      setIsEditing(false);
    }
  };

  return (
    <div className="break-inside-avoid bg-white rounded-[24px] border border-slate-100 p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)] relative hover:shadow-[0_8px_30px_rgba(0,0,0,0.04)] transition-all duration-300">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          {!thought.isSystem && <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getConfColor(thought.confidence) }} />}
          <span className={`text-[13px] font-bold ${thought.isSystem ? 'text-slate-500' : 'text-slate-800'}`}>{thought.line}</span>
        </div>
        <div className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider ${getConfBg(thought.confidence)}`}>
          {thought.isSystem ? '系统观察' : `Conf ${thought.confidence}%`}
        </div>
      </div>
      <div className="mb-4">
        <span className="inline-block text-[10px] font-bold text-slate-400 tracking-[0.5px] uppercase mb-2">我观察到</span>
        <p className="text-[13px] leading-[1.9] text-slate-600 font-medium">{thought.observation}</p>
      </div>
      <div>
        <span className="inline-block text-[10px] font-bold text-blue-600 tracking-[0.5px] uppercase mb-2">我的建议</span>
        <p className="text-[13px] leading-[1.9] text-slate-700 font-medium">{thought.suggestion}</p>
      </div>
      <div className="mt-6 pt-4 border-t border-slate-50">
        {/* Review display (shown when confirmed OR when task was created with a comment) */}
        {isSubmitted && (
          <div className="bg-slate-50 rounded-[16px] p-4 mb-3">
            <div className="flex items-center gap-1.5 mb-2">
              <CheckCircle size={14} className="text-emerald-500" />
              <span className="text-[11px] font-semibold text-slate-500">已批阅 · {new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}</span>
            </div>
            <p className="text-[12px] leading-[1.7] text-slate-700 font-medium">"{reviewText}"</p>
          </div>
        )}

        {/* Task created link */}
        {taskCreated && (
          <div className="bg-blue-50/50 rounded-[14px] px-4 py-3 mb-3">
            <div className="text-[11px] text-blue-600 font-semibold flex items-center gap-1.5">
              <CornerDownRight size={12} /> 已转为任务 · 来自研判：{thought.line}
            </div>
          </div>
        )}

        {/* Editing area */}
        {isEditing && !isSubmitted ? (
          <div className="bg-slate-50 rounded-[18px] p-4">
            <textarea
              className="w-full min-h-[72px] border border-slate-200 rounded-[14px] p-3 text-[13px] text-slate-700 bg-white resize-y outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-100"
              placeholder="写下你的看法..."
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value)}
              autoFocus
            />
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={handleCreateTask}
                className="text-[11px] font-bold px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
              >
                转为任务
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="ml-auto bg-blue-600 text-white rounded-full px-5 py-1.5 text-[12px] font-bold hover:bg-blue-700 transition-colors"
              >
                确认
              </button>
            </div>
          </div>
        ) : !isSubmitted && !taskCreated ? (
          /* Default state: tags + two buttons */
          <div>
            <div className="flex flex-wrap gap-2 mb-3">
              {thought.tags.map((t: any, idx: number) => (
                <span key={idx} className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-bold bg-slate-50 text-slate-400 border border-slate-100">
                  {t.icon && <t.icon size={12} className="opacity-70" />}
                  {t.text}
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="flex-1 flex items-center gap-2 bg-transparent border border-slate-200 text-slate-500 rounded-[16px] px-4 py-2.5 text-[12px] font-semibold text-left hover:border-blue-300 hover:text-slate-700 transition-colors"
              >
                <PenLine size={14} className="text-slate-400" />
                写下我的判断...
              </button>
              <button
                type="button"
                onClick={handleCreateTask}
                className="flex items-center gap-1.5 border border-blue-200 bg-blue-50 text-blue-600 rounded-[16px] px-4 py-2.5 text-[12px] font-bold hover:bg-blue-100 transition-colors shrink-0"
              >
                <ClipboardList size={14} />
                转为任务
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ThoughtsTab({ onCreateTask }: { onCreateTask?: (payload: ThoughtTaskPayload) => void }) {
  return (
    <div>
      <div className="columns-1 md:columns-2 gap-5 space-y-5">
        {THOUGHTS_DATA.map((thought) => (
          <ThoughtCard key={thought.id} thought={thought} onCreateTask={onCreateTask} />
        ))}
      </div>
    </div>
  );
}

function ClientsTab({ onOpenDetail, clients }: { onOpenDetail: (name: string) => void; clients: BrainClientData[] }) {
  const sorted = [...clients].sort((a, b) => b.confidence - a.confidence);
  return (
    <div>
      <div className="flex items-center justify-between mb-6 px-2">
        <h2 className="text-[15px] font-bold text-slate-800 flex items-center gap-2">
          <FolderTree size={18} className="text-indigo-500" /> 项目认知图谱
        </h2>
        <span className="text-[12px] font-medium text-slate-400">目前收录 {clients.length} 个项目空间</span>
      </div>
      <div className="columns-1 md:columns-2 gap-5 space-y-5">
        {sorted.map((client, i) => (
          <div
            key={i}
            onClick={() => onOpenDetail(client.name)}
            className="break-inside-avoid bg-white rounded-[24px] border border-slate-100 p-6 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.05)] hover:border-blue-200 transition-all duration-300 cursor-pointer group"
          >
            <div className="flex flex-col mb-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[16px] font-bold text-slate-800 group-hover:text-blue-600 transition-colors">{client.name}</h3>
                <span className="bg-slate-50 border border-slate-100 text-slate-500 text-[11px] font-bold px-2.5 py-1 rounded-lg">
                  {client.stage}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-1.5 bg-slate-100 rounded-full w-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${client.confidence}%`, backgroundColor: getConfColor(client.confidence) }}
                  />
                </div>
                <span className="text-[12px] font-bold tabular-nums w-8 text-right" style={{ color: getConfColor(client.confidence) }}>
                  {client.confidence}%
                </span>
              </div>
            </div>
            {client.intro ? (
              <p className="text-[13px] leading-[1.8] text-slate-600 font-medium mb-5 line-clamp-3">
                {client.intro}
              </p>
            ) : (
              <p className="text-[13px] leading-[1.8] text-slate-400 italic mb-5">
                系统对这个项目的了解还很初步
              </p>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-2 mb-4 pt-4 border-t border-slate-50">
              {[
                { icon: Folder, label: `${client.docs} 文档` },
                { icon: FileText, label: `${client.dna} 篇 DNA` },
                { icon: Activity, label: `${client.eventLines} 事件线` },
                { icon: BrainCircuit, label: `${client.memoryFacts} 条记忆` },
              ].map((metric, idx) => (
                <span key={idx} className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                  <metric.icon size={12} className="text-slate-300" />
                  {metric.label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LearningTab() {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-50 border border-blue-100 mb-4 shadow-sm">
          <Lightbulb size={24} className="text-blue-600" />
        </div>
        <h2 className="text-[20px] font-bold text-slate-800 mb-2">我渴望学习更多</h2>
        <p className="text-[13px] text-slate-400">学习清单功能即将上线</p>
      </div>
    </div>
  );
}


// ================= MAIN EXPORT =================

export type StrategicBrainViewProps = {
  clients?: Array<{ id: string; name: string }>;
  currentClientId?: string | null;
  onClientChange?: (clientId: string) => void;
  onCreateTaskFromThought?: (payload: ThoughtTaskPayload) => void;
};

export function StrategicBrainView({ onCreateTaskFromThought }: StrategicBrainViewProps) {
  const [selectedClient, setSelectedClient] = useState('全部客户');
  const [activeTab, setActiveTab] = useState('pulse');
  const [viewState, setViewState] = useState<{ type: 'tabs'; detailId: null } | { type: 'detail'; detailId: string }>({ type: 'tabs', detailId: null });
  const [isOpen, setIsOpen] = useState(false);
  const [dashboard, setDashboard] = useState<BrainDashboard | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  useClickOutside(dropdownRef, () => setIsOpen(false));

  useEffect(() => {
    getBrainDashboard()
      .then(setDashboard)
      .catch(() => setDashboard(null));
  }, []);

  const clientNames = ['全部客户', ...(dashboard?.clients.map(c => c.name) || [])];

  if (viewState.type === 'detail') {
    return (
      <div className="h-full flex flex-col bg-white/50 overflow-y-auto">
        <ProjectDetailView clientId={viewState.detailId} onBack={() => setViewState({ type: 'tabs', detailId: null })} />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#F9FAFB] overflow-hidden font-sans">
      {/* Header */}
      <div className="bg-[#F9FAFB]/80 backdrop-blur-xl border-b border-slate-200/60 pt-5 pb-4 px-6 flex flex-col gap-4 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[18px] font-semibold tracking-tight text-slate-900 flex items-center gap-2">
              战略陪伴
            </h1>
            <p className="text-[11px] font-medium text-slate-400 mt-0.5">AI 陪伴组织成长 · 越用越懂你</p>
          </div>
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center gap-2 bg-white border border-slate-200 shadow-sm rounded-full px-4 py-2 hover:bg-slate-50 transition-all duration-200"
            >
              <div className="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center">
                <User size={12} className="text-blue-600" />
              </div>
              <span className="text-[13px] font-semibold text-slate-700">{selectedClient}</span>
              <ChevronDown size={14} className="text-slate-400" />
            </button>
            {isOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-100 rounded-2xl shadow-xl py-1.5 z-50 overflow-hidden">
                {clientNames.map(client => (
                  <button
                    key={client}
                    type="button"
                    className={`w-full text-left px-4 py-2.5 text-[13px] font-medium transition-colors hover:bg-slate-50 ${selectedClient === client ? 'text-blue-600 bg-blue-50/50' : 'text-slate-600'}`}
                    onClick={() => { setSelectedClient(client); setIsOpen(false); }}
                  >
                    {client}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex bg-slate-100/80 p-1 rounded-2xl w-fit">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 rounded-2xl text-[13px] font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-white text-[#5B7BFE] shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="max-w-full mx-auto">
          {activeTab === 'pulse' && <PulseTab pulse={dashboard?.pulse ?? null} />}
          {activeTab === 'thoughts' && <ThoughtsTab onCreateTask={onCreateTaskFromThought} />}
          {activeTab === 'clients' && <ClientsTab clients={dashboard?.clients ?? []} onOpenDetail={(name) => setViewState({ type: 'detail', detailId: name })} />}
          {activeTab === 'learning' && <LearningTab />}
        </div>
      </div>
    </div>
  );
}

export default StrategicBrainView;
