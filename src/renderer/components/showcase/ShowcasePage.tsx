import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowRight, Download, CheckCircle2, XCircle,
  BookOpen, Users, Handshake, Code, Lightbulb,
  ChevronRight, Share2, Compass, Zap,
  CheckSquare, Briefcase, Target, Newspaper,
  LayoutTemplate, Settings, Calendar, Brain,
  Shield, TrendingUp, Layers, GitBranch,
  FileText, MessageSquare, BarChart3, Award,
  Search, Eye, ArrowUpRight, Sparkles,
  Database, RefreshCw,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Hooks & Primitives
// ---------------------------------------------------------------------------

const useScrollReveal = () => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.08, rootMargin: '0px 0px -80px 0px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, isVisible };
};

interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  direction?: 'up' | 'left' | 'right';
}

const FadeIn = ({ children, delay = 0, className = '', direction = 'up' }: FadeInProps) => {
  const { ref, isVisible } = useScrollReveal();

  const translateClass =
    direction === 'left' ? '-translate-x-12' :
    direction === 'right' ? 'translate-x-12' :
    'translate-y-12';

  return (
    <div
      ref={ref}
      className={`transition-all duration-[1200ms] ${
        isVisible ? 'opacity-100 translate-x-0 translate-y-0' : `opacity-0 ${translateClass}`
      } ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Section: Hero
// ---------------------------------------------------------------------------

const HeroSection = () => (
  <section className="max-w-7xl mx-auto px-6 md:px-10 pb-32 flex items-center min-h-[85vh]">
    <div className="grid lg:grid-cols-2 gap-20 items-center">
      {/* Left — Narrative */}
      <div className="space-y-10 relative z-20">
        <FadeIn>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#5A52FF]/5 text-[#5A52FF] text-[13px] font-semibold tracking-wide">
            <span className="w-1.5 h-1.5 rounded-full bg-[#5A52FF] animate-pulse" />
            开源计划进行中
          </div>
        </FadeIn>

        <FadeIn delay={100}>
          <h1 className="text-5xl md:text-[4.2rem] font-extrabold leading-[1.08] tracking-tighter text-[#1D1D1F]">
            帮助普通团队 <br />
            在熟悉界面里进入{' '}
            <span className="bg-clip-text [-webkit-background-clip:text] [-webkit-text-fill-color:transparent] bg-gradient-to-r from-[#5A52FF] via-[#7C3AED] to-[#A855F7] pb-1 inline-block">
              AI&nbsp;协作时代。
            </span>
          </h1>
        </FadeIn>

        <FadeIn delay={200}>
          <p className="text-[20px] text-[#86868B] leading-[1.65] max-w-lg font-medium tracking-tight">
            不是再造一个工具，而是保留你熟悉的工作方式——让资料、任务、时间线与经验，在做事现场被&nbsp;AI&nbsp;真正接通。
          </p>
        </FadeIn>

        <FadeIn delay={300}>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button className="flex items-center justify-center gap-2 bg-[#5A52FF] hover:bg-[#4c45df] text-white px-8 py-4 rounded-full font-semibold text-[15px] transition-all shadow-[0_4px_20px_rgba(90,82,255,0.3)] hover:shadow-[0_10px_30px_rgba(90,82,255,0.4)] hover:-translate-y-0.5 active:scale-95 group">
              免费下载社区版
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="flex items-center justify-center gap-2 bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#1D1D1F] px-8 py-4 rounded-full font-semibold text-[15px] transition-all active:scale-95">
              深入了解开源
            </button>
          </div>
        </FadeIn>
      </div>

      {/* Right — System Mockup: show "connection" not just a single page */}
      <div className="relative h-[650px] hidden lg:block">
        <FadeIn delay={300} direction="right" className="absolute inset-0">
          {/* Main device frame */}
          <div className="absolute top-[12%] left-[3%] w-[94%] h-[72%] bg-white rounded-[2.5rem] shadow-[0_30px_80px_rgba(0,0,0,0.06)] animate-[float-premium_8s_ease-in-out_infinite] flex flex-col p-7 overflow-hidden z-10 ring-1 ring-black/[0.03]">
            {/* Window chrome */}
            <div className="flex items-center gap-3 mb-6">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-[#FF5F56]" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
                <div className="w-3 h-3 rounded-full bg-[#27C93F]" />
              </div>
              <div className="ml-4 h-2.5 w-28 bg-[#F5F5F7] rounded-full" />
            </div>

            {/* Mock: sidebar + content */}
            <div className="flex-1 flex gap-4">
              {/* Sidebar — 7 modules */}
              <div className="w-[52px] shrink-0 flex flex-col gap-3 pt-1">
                {[
                  { color: 'bg-blue-100 text-blue-600', Icon: CheckSquare },
                  { color: 'bg-purple-100 text-purple-600', Icon: Briefcase },
                  { color: 'bg-amber-100 text-amber-600', Icon: Target },
                  { color: 'bg-emerald-100 text-emerald-600', Icon: Newspaper },
                  { color: 'bg-rose-100 text-rose-600', Icon: LayoutTemplate },
                  { color: 'bg-indigo-100 text-indigo-600', Icon: BookOpen },
                  { color: 'bg-gray-100 text-gray-500', Icon: Settings },
                ].map(({ color, Icon }, i) => (
                  <div key={i} className={`w-10 h-10 rounded-xl ${color} flex items-center justify-center`}>
                    <Icon className="w-4 h-4" />
                  </div>
                ))}
              </div>

              {/* Main content area */}
              <div className="flex-1 grid grid-cols-5 gap-4">
                <div className="col-span-3 space-y-3">
                  {/* Task card mockup */}
                  <div className="h-[100px] bg-[#FBFBFD] rounded-2xl p-5 relative overflow-hidden">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-2 h-2 rounded-full bg-[#5A52FF]" />
                      <div className="w-24 h-2.5 bg-[#E8E8ED] rounded-full" />
                    </div>
                    <div className="space-y-2.5">
                      <div className="w-full h-2 bg-[#F5F5F7] rounded-full" />
                      <div className="w-4/5 h-2 bg-[#F5F5F7] rounded-full" />
                    </div>
                    {/* Event line indicator */}
                    <div className="absolute right-4 top-4 flex items-center gap-1">
                      <GitBranch className="w-3 h-3 text-purple-400" />
                      <div className="w-10 h-1.5 bg-purple-100 rounded-full" />
                    </div>
                  </div>

                  {/* Connection indicators */}
                  <div className="flex gap-3">
                    <div className="flex-1 h-20 bg-[#FBFBFD] rounded-2xl p-4 flex flex-col justify-between">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-blue-400" />
                        <div className="w-12 h-2 bg-[#E8E8ED] rounded-full" />
                      </div>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((d) => (
                          <div key={d} className={`flex-1 h-6 rounded-md ${d === 3 ? 'bg-blue-100' : 'bg-[#F5F5F7]'}`} />
                        ))}
                      </div>
                    </div>
                    <div className="flex-1 h-20 bg-[#FBFBFD] rounded-2xl p-4 flex flex-col justify-between">
                      <div className="flex items-center gap-1.5">
                        <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                        <div className="w-12 h-2 bg-[#E8E8ED] rounded-full" />
                      </div>
                      <div className="flex items-end gap-1 h-6">
                        {[40, 60, 35, 80, 55].map((h, i) => (
                          <div key={i} className="flex-1 bg-emerald-100 rounded-sm" style={{ height: `${h}%` }} />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Evidence trace */}
                  <div className="h-14 bg-[#FBFBFD] rounded-2xl p-4 flex items-center gap-3">
                    <Shield className="w-4 h-4 text-amber-500" />
                    <div className="flex-1 flex items-center gap-2">
                      <div className="w-16 h-2 bg-amber-100 rounded-full" />
                      <ArrowRight className="w-3 h-3 text-[#E8E8ED]" />
                      <div className="w-12 h-2 bg-purple-100 rounded-full" />
                      <ArrowRight className="w-3 h-3 text-[#E8E8ED]" />
                      <div className="w-10 h-2 bg-blue-100 rounded-full" />
                    </div>
                  </div>
                </div>

                {/* AI Intelligence panel */}
                <div className="col-span-2 bg-gradient-to-b from-[#F9F8FF] to-white rounded-2xl p-5 flex flex-col relative overflow-hidden ring-1 ring-[#5A52FF]/10">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#5A52FF] to-[#A855F7]" />
                  <div className="flex items-center gap-2 text-[#5A52FF] mb-4">
                    <Zap className="w-3.5 h-3.5 fill-current" />
                    <span className="text-[11px] font-bold tracking-widest uppercase">情境建议</span>
                  </div>
                  {/* Confidence indicator */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-full h-1.5 bg-[#E8E8ED] rounded-full overflow-hidden">
                      <div className="w-[72%] h-full bg-gradient-to-r from-[#5A52FF] to-[#A855F7] rounded-full" />
                    </div>
                    <span className="text-[10px] text-[#86868B] whitespace-nowrap">72%</span>
                  </div>
                  <div className="h-14 bg-white rounded-xl w-full shadow-sm ring-1 ring-black/[0.02] mb-3 p-3">
                    <div className="space-y-1.5">
                      <div className="w-full h-1.5 bg-[#F5F5F7] rounded-full" />
                      <div className="w-3/4 h-1.5 bg-[#F5F5F7] rounded-full" />
                    </div>
                  </div>
                  <div className="space-y-2 mt-auto mb-4">
                    <div className="h-1.5 bg-[#E8E8ED] rounded-full w-4/5" />
                    <div className="h-1.5 bg-[#E8E8ED] rounded-full w-full" />
                  </div>
                  <div className="h-9 bg-[#1D1D1F] text-white rounded-xl w-full flex items-center justify-center text-[12px] font-semibold">
                    采纳建议
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Floating: five-layer context */}
          <div className="absolute top-[5%] right-[-2%] bg-white/70 backdrop-blur-2xl rounded-2xl animate-[float-premium_9s_ease-in-out_infinite_2s] p-4 z-20 shadow-[0_20px_40px_rgba(0,0,0,0.05)] ring-1 ring-white">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-[#5A52FF]" />
              <span className="text-[11px] font-bold text-[#5A52FF]">五层上下文</span>
            </div>
            <div className="space-y-1.5">
              {['组织', '客户', '协作', '事件线', '当前'].map((label, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: `hsl(${250 - i * 20}, 70%, ${55 + i * 5}%)` }} />
                  <span className="text-[10px] text-[#86868B]">{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Floating: closed loop */}
          <div className="absolute bottom-[8%] left-[-4%] bg-white/70 backdrop-blur-2xl rounded-2xl animate-[float-premium_10s_ease-in-out_infinite_1s] p-4 z-20 shadow-[0_20px_40px_rgba(0,0,0,0.05)] ring-1 ring-white">
            <div className="flex items-center gap-2 mb-2">
              <RefreshCw className="w-4 h-4 text-emerald-500" />
              <span className="text-[11px] font-bold text-emerald-600">闭环流转</span>
            </div>
            <div className="text-[10px] text-[#86868B] leading-relaxed">
              任务 → 复盘 → 判断 → 成长
            </div>
          </div>
        </FadeIn>
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: The Real Problem — AI 鸿沟
// ---------------------------------------------------------------------------

const ProblemSection = () => (
  <section className="py-32 relative bg-white">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-extrabold text-[#1D1D1F] tracking-tight leading-tight">
            AI 在快速前进。
            <br />
            <span className="text-[#86868B] font-semibold">但绝大多数团队，还站在鸿沟这一边。</span>
          </h2>
          <p className="mt-6 text-[18px] text-[#86868B] max-w-2xl mx-auto leading-relaxed">
            真正拦住普通团队的，不是有没有模型，而是有没有一个能理解、敢使用、能持续建立习惯的入口。
          </p>
        </div>
      </FadeIn>

      <div className="grid md:grid-cols-3 gap-10">
        {[
          {
            num: '01.',
            title: '任务是孤岛',
            desc: '任务完成了就结束了。没有人追踪同一件事跨三周的推进线，没有人把上次会议的结论和这周的行动串起来。',
            detail: '事件线断裂、经验无法积累',
          },
          {
            num: '02.',
            title: '经验在流失',
            desc: '一个人积累的判断、方法和手感，换个人就从零开始。组织每天在产出经验，但几乎没有沉淀下来。',
            detail: '人走知识散、重复踩坑',
          },
          {
            num: '03.',
            title: '判断缺乏依据',
            desc: '周会上做决策，靠的是记忆和感觉。哪些风险在增加、哪些机会被忽略、哪些信息还不够——没有系统告诉你。',
            detail: '决策凭直觉、缺少证据链',
            highlight: true,
          },
        ].map((item, i) => (
          <FadeIn key={i} delay={i * 150}>
            <div className={`h-full rounded-[2rem] p-10 transition-all duration-500
              ${item.highlight ? 'bg-[#F9F8FF] ring-1 ring-[#5A52FF]/10' : 'bg-[#FBFBFD]'}`}>
              <div className={`text-2xl font-bold mb-6 tracking-tighter
                ${item.highlight ? 'text-[#5A52FF]' : 'text-[#86868B]'}`}>
                {item.num}
              </div>
              <h3 className="text-[22px] font-bold mb-4 text-[#1D1D1F] tracking-tight">{item.title}</h3>
              <p className="text-[#86868B] leading-[1.7] text-[16px] mb-4">{item.desc}</p>
              <span className="inline-block text-[13px] text-[#A1A1A6] bg-[#F5F5F7] px-3 py-1 rounded-full">{item.detail}</span>
            </div>
          </FadeIn>
        ))}
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: What It IS / IS NOT
// ---------------------------------------------------------------------------

const DefinitionSection = () => (
  <section className="py-32 relative bg-[#FBFBFD]">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <div className="text-center mb-6">
          <h2 className="text-4xl md:text-5xl font-extrabold text-[#1D1D1F] tracking-tight">
            重新定义，它不是"那种软件"。
          </h2>
        </div>
        <p className="text-center text-[18px] text-[#86868B] mb-20 max-w-3xl mx-auto leading-relaxed">
          一款开源的、陪伴式的、建议型的&nbsp;AI&nbsp;工作界面。<br />
          它不是为了把人拿掉，而是为了让&nbsp;AI&nbsp;在人们熟悉的界面里开始真正工作。
        </p>
      </FadeIn>

      <div className="grid md:grid-cols-2 gap-8">
        <FadeIn direction="up" delay={100}>
          <div className="h-full bg-white p-12 rounded-[2.5rem] shadow-[0_20px_60px_rgba(0,0,0,0.03)] hover:-translate-y-2 transition-transform duration-700">
            <h3 className="text-[28px] font-extrabold text-[#1D1D1F] mb-10 tracking-tight">它是</h3>
            <ul className="space-y-6">
              {[
                '能在做事现场调动知识，而不是只负责存和查的系统',
                '通过任务、日历、资料等入口，持续理解人和组织的工作界面',
                '能在上下文里给建议，而不是一问一答就结束的陪伴式系统',
                '让资料、时间、任务、经验和判断发生联动的建议型软件',
              ].map((item, i) => (
                <li key={i} className="flex gap-4 text-[16px] text-[#1D1D1F]/80 font-medium items-start">
                  <div className="w-6 h-6 mt-0.5 rounded-full bg-[#5A52FF]/10 flex items-center justify-center shrink-0">
                    <CheckCircle2 className="w-4 h-4 text-[#5A52FF]" />
                  </div>
                  <span className="leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </FadeIn>

        <FadeIn direction="up" delay={200}>
          <div className="h-full bg-[#F5F5F7] p-12 rounded-[2.5rem] transition-transform duration-700">
            <h3 className="text-[28px] font-extrabold text-[#86868B] mb-10 tracking-tight">它不是</h3>
            <ul className="space-y-6">
              {[
                { wrong: '知识库', right: '不只存和查，而是在做事现场调用知识' },
                { wrong: '个人管理工具', right: '不只管自己，而是接通组织协作和事件推进线' },
                { wrong: '聊天机器人外壳', right: '不只一问一答，而是持续理解上下文给出建议' },
                { wrong: '功能的堆叠', right: '不堆模块，而是让信息在模块间真正流动' },
              ].map((item, i) => (
                <li key={i} className="flex gap-4 text-[16px] text-[#86868B] font-medium items-start">
                  <div className="w-6 h-6 mt-0.5 rounded-full bg-[#E8E8ED] flex items-center justify-center shrink-0">
                    <XCircle className="w-4 h-4 text-[#A1A1A6]" />
                  </div>
                  <span className="leading-relaxed">
                    <span className="line-through">{item.wrong}</span>
                    <span className="text-[#A1A1A6] mx-2">→</span>
                    <span className="text-[#86868B]">{item.right}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </FadeIn>
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: The Unique Layer — "页面下面那一层"
// ---------------------------------------------------------------------------

const UniqueLayerSection = () => (
  <section className="py-32 relative bg-white">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <div className="text-center mb-24">
          <h2 className="text-4xl md:text-5xl font-extrabold mb-6 text-[#1D1D1F] tracking-tight leading-tight">
            独特之处不在页面多少。<br />
            <span className="text-[#5A52FF]">在于页面下面那一层。</span>
          </h2>
          <p className="text-[18px] text-[#86868B] max-w-2xl mx-auto leading-relaxed">
            它不是只把文件切块塞进知识库，也不是只回答问题。<br />
            它围绕任务、角色、时间线和当前场景去理解信息，在你做事的时候给出下一步指引。
          </p>
        </div>
      </FadeIn>

      <div className="grid md:grid-cols-3 gap-8">
        {[
          {
            icon: <Layers />,
            title: '五层上下文叠加',
            desc: '每一次判断，都参考五层信息：组织背景 → 客户画像 → 协作关系 → 事件线历史 → 当前任务。不是通用回答，是贴合你具体处境的建议。',
            bg: 'bg-[#F9F8FF]',
            color: 'text-[#5A52FF]',
          },
          {
            icon: <Shield />,
            title: '置信度标记与证据追溯',
            desc: 'AI 不会假装确定。每条判断都标注置信度，每个结论都能追溯到具体证据来源。信息不够时，系统会明确告诉你缺什么。',
            bg: 'bg-[#FFF9F0]',
            color: 'text-[#F59E0B]',
          },
          {
            icon: <RefreshCw />,
            title: '闭环：做事即沉淀',
            desc: '完成任务自动产生成长证据，周复盘自动提炼事件线趋势，经验沉淀后被下一个类似任务复用。工作本身就是学习，学习反过来改善工作。',
            bg: 'bg-[#F0FDF4]',
            color: 'text-[#10B981]',
          },
        ].map((item, i) => (
          <FadeIn key={i} delay={i * 120}>
            <div className="h-full bg-white rounded-[2rem] p-10 shadow-[0_8px_30px_rgba(0,0,0,0.03)] hover:shadow-[0_30px_60px_rgba(0,0,0,0.06)] hover:-translate-y-2 transition-all duration-700">
              <div className={`w-14 h-14 rounded-2xl ${item.bg} flex items-center justify-center mb-8 ${item.color}`}>
                {React.cloneElement(item.icon, { className: 'w-6 h-6' })}
              </div>
              <h3 className="text-[22px] font-bold mb-4 text-[#1D1D1F] tracking-tight">{item.title}</h3>
              <p className="text-[#86868B] text-[16px] leading-[1.7]">{item.desc}</p>
            </div>
          </FadeIn>
        ))}
      </div>

      {/* Five-layer context visualization */}
      <FadeIn delay={200}>
        <div className="mt-20 bg-[#FBFBFD] rounded-[2.5rem] p-12 relative overflow-hidden">
          <h3 className="text-[20px] font-bold text-[#1D1D1F] mb-8 text-center">当你打开一条任务时，系统已经理解了这些</h3>
          <div className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-0">
            {[
              { label: '组织 DNA', sub: '年度目标 · 季度主线 · 团队结构', color: 'bg-[#5A52FF]' },
              { label: '客户画像', sub: '项目背景 · 导入资料 · 知识库', color: 'bg-[#7C3AED]' },
              { label: '协作关系', sub: '协作者 · 审批流 · 支持请求', color: 'bg-[#9333EA]' },
              { label: '事件线记忆', sub: '跨周推进 · 风险机会 · 完成度', color: 'bg-[#A855F7]' },
              { label: '当前任务', sub: '本周行动 · 截止时间 · 归属建议', color: 'bg-[#C084FC]' },
            ].map((layer, i) => (
              <React.Fragment key={i}>
                {i > 0 && (
                  <div className="hidden md:flex items-center px-3">
                    <ChevronRight className="w-5 h-5 text-[#E8E8ED]" />
                  </div>
                )}
                <div className="flex-1 text-center">
                  <div className={`${layer.color} text-white text-[13px] font-semibold px-5 py-2.5 rounded-full inline-block mb-3`}>
                    {layer.label}
                  </div>
                  <p className="text-[12px] text-[#A1A1A6] leading-relaxed">{layer.sub}</p>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </FadeIn>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Seven Modules
// ---------------------------------------------------------------------------

const MODULE_DATA = [
  {
    id: 'tasks',
    icon: CheckSquare,
    title: '任务与日程',
    headline: '不只是待办清单，而是事件线驱动的执行台',
    features: [
      '协作收件箱：接收、退回、复核团队任务',
      '事件线：同一件事跨多周的推进线自动追踪',
      '内部月历 / 周历：任务按时间排布，可拖拽',
      '周复盘：AI 采集本周事实，生成叙事分析与风险/机会判断',
    ],
    color: 'from-blue-500 to-blue-600',
    lightBg: 'bg-blue-50',
    lightColor: 'text-blue-600',
  },
  {
    id: 'client',
    icon: Briefcase,
    title: '客户工作台',
    headline: '把空壳客户变成 AI 能理解的项目上下文',
    features: [
      '导入 Word / PDF / PPT / 纪要 → 自动建知识库',
      '项目问答：带检索增强的 AI 对话，基于项目资料回答',
      '会议流：创建 → 导入纪要 → 自动抽取决策与行动项',
      '项目模块与流程：拆解长期交付件，挂接任务与事件线',
    ],
    color: 'from-purple-500 to-purple-600',
    lightBg: 'bg-purple-50',
    lightColor: 'text-purple-600',
  },
  {
    id: 'strategy',
    icon: Target,
    title: '战略陪伴',
    headline: '经营判断不靠猜，靠证据和置信度',
    features: [
      '战略驾驶舱：本周一句话、主矛盾、核心突破、焦点事项',
      '组织健康五维度：方向、资源承接、协同、决策、知识留存',
      '周会清单自动生成：待讨论事项 + 已掌握情况 + 会前材料',
      '证据底稿：每条判断可追溯到具体任务事实和会议信号',
    ],
    color: 'from-amber-500 to-amber-600',
    lightBg: 'bg-amber-50',
    lightColor: 'text-amber-600',
  },
  {
    id: 'topics',
    icon: Newspaper,
    title: '资讯情报站',
    headline: '外部信号不停留在收件箱，直接转化成行动',
    features: [
      '选题雷达：设定持续监控的主题，系统自动抓取候选资讯',
      'AI 洞察提炼：关键要点、与雷达的关系、实操启示、讨论引子',
      '一键转任务：从一篇资讯生成带标题、描述、截止时间的任务',
      '全链路可追溯：候选 → 雷达 → 多条可能任务 → 执行跟踪',
    ],
    color: 'from-emerald-500 to-emerald-600',
    lightBg: 'bg-emerald-50',
    lightColor: 'text-emerald-600',
  },
  {
    id: 'workbench',
    icon: LayoutTemplate,
    title: '测试工作台',
    headline: '内部分析与诊断的实验运行区',
    features: [
      '选择模板运行分析：筹款分析、系统诊断、风险 DNA',
      '结合组织画像和知识库做结构化判断',
      '分析结果可沉淀为成长学习卡',
      '支持 Bettafish 外部信号整合与多模式推断',
    ],
    color: 'from-rose-500 to-rose-600',
    lightBg: 'bg-rose-50',
    lightColor: 'text-rose-600',
  },
  {
    id: 'growth',
    icon: BookOpen,
    title: '成长手册',
    headline: '工作本身就是学习，学习反过来改善工作',
    features: [
      'XP 账本与段位：执行、协作、分析、洞察、风控、写作六维度',
      '能力缺口预测：项目开始前就知道哪些能力需要补',
      '经验沉淀 → 复用追踪：方法卡被引用越多，组织能力越强',
      '成长证据自动采集：完成任务即产生可追溯的成长信号',
    ],
    color: 'from-indigo-500 to-indigo-600',
    lightBg: 'bg-indigo-50',
    lightColor: 'text-indigo-600',
  },
  {
    id: 'settings',
    icon: Settings,
    title: '系统设置',
    headline: '组织治理后台，而不只是偏好设置',
    features: [
      '组织搭建中心：CEO 起盘 → 部门 → 岗位 → 权限 → 季度重点',
      '各模块规则配置：任务、客户、情报、分析、成长的治理规则',
      '组织 DNA 四卡：组织介绍、业务介绍、团队介绍、市场介绍',
      '飞书集成：单机器人配置、扫码绑定、会议联动',
    ],
    color: 'from-gray-500 to-gray-600',
    lightBg: 'bg-gray-50',
    lightColor: 'text-gray-600',
  },
];

const ModulesSection = () => {
  const [activeModule, setActiveModule] = useState(0);
  const mod = MODULE_DATA[activeModule];

  return (
    <section className="py-32 relative bg-[#FBFBFD]">
      <div className="max-w-7xl mx-auto px-6 md:px-10">
        <FadeIn>
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-extrabold mb-6 text-[#1D1D1F] tracking-tight">
              七个工作台，一套底盘。
            </h2>
            <p className="text-[18px] text-[#86868B] max-w-2xl mx-auto leading-relaxed">
              不是七个独立工具的拼接，而是同一套对象模型上的七个视角。<br />
              任务、客户、事件线、知识、成长信号——在模块之间自然流动。
            </p>
          </div>
        </FadeIn>

        <FadeIn delay={100}>
          {/* Module tabs */}
          <div className="flex flex-wrap justify-center gap-2 mb-12">
            {MODULE_DATA.map((m, i) => {
              const Icon = m.icon;
              const isActive = i === activeModule;
              return (
                <button
                  key={m.id}
                  onClick={() => setActiveModule(i)}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-[14px] font-semibold transition-all duration-300
                    ${isActive
                      ? 'bg-[#1D1D1F] text-white shadow-lg'
                      : 'bg-white text-[#86868B] hover:bg-[#F5F5F7] hover:text-[#1D1D1F]'
                    }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{m.title}</span>
                </button>
              );
            })}
          </div>

          {/* Active module detail */}
          <div className="bg-white rounded-[2.5rem] p-12 shadow-[0_20px_60px_rgba(0,0,0,0.03)] ring-1 ring-black/[0.02] transition-all duration-500">
            <div className="grid md:grid-cols-2 gap-12 items-start">
              <div>
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${mod.lightBg} ${mod.lightColor} text-[13px] font-semibold mb-6`}>
                  {React.createElement(mod.icon, { className: 'w-4 h-4' })}
                  {mod.title}
                </div>
                <h3 className="text-[28px] font-extrabold text-[#1D1D1F] tracking-tight mb-4 leading-snug">
                  {mod.headline}
                </h3>
              </div>

              <div>
                <ul className="space-y-5">
                  {mod.features.map((feat, i) => (
                    <li key={i} className="flex gap-4 items-start">
                      <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${mod.color} flex items-center justify-center shrink-0 mt-0.5`}>
                        <span className="text-white text-[12px] font-bold">{i + 1}</span>
                      </div>
                      <span className="text-[16px] text-[#1D1D1F]/80 leading-relaxed font-medium">{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
};

// ---------------------------------------------------------------------------
// Section: Closed-Loop Workflows
// ---------------------------------------------------------------------------

const WorkflowSection = () => (
  <section className="py-32 relative bg-[#1D1D1F]">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <h2 className="text-4xl md:text-5xl font-extrabold text-center mb-6 text-white tracking-tight">
          信息不是存起来就有用。
        </h2>
        <p className="text-center text-[18px] text-[#86868B] mb-24 max-w-2xl mx-auto leading-relaxed">
          它需要流动、被理解、被行动、再被沉淀。<br />
          这是三条在系统中真实运转的闭环。
        </p>
      </FadeIn>

      <div className="grid md:grid-cols-3 gap-8">
        {[
          {
            title: '情报 → 行动闭环',
            color: 'from-emerald-400 to-emerald-600',
            steps: [
              { label: '雷达捕获信号', icon: Search },
              { label: 'AI 提炼洞察', icon: Sparkles },
              { label: '转化为任务', icon: CheckSquare },
              { label: '事件线追踪执行', icon: GitBranch },
            ],
          },
          {
            title: '执行 → 判断闭环',
            color: 'from-[#5A52FF] to-[#7C3AED]',
            steps: [
              { label: '任务推进产生事实', icon: CheckSquare },
              { label: '周复盘采集证据', icon: FileText },
              { label: '事件线叙事分析', icon: Brain },
              { label: '战略驾驶舱输出判断', icon: Target },
            ],
          },
          {
            title: '工作 → 成长闭环',
            color: 'from-amber-400 to-amber-600',
            steps: [
              { label: '完成任务产生证据', icon: CheckSquare },
              { label: '系统识别成长信号', icon: Lightbulb },
              { label: '沉淀为经验方法卡', icon: BookOpen },
              { label: '下次类似任务自动复用', icon: RefreshCw },
            ],
          },
        ].map((flow, fi) => (
          <FadeIn key={fi} delay={fi * 150}>
            <div className="bg-[#2C2C2E] rounded-[2rem] p-8 h-full">
              <div className={`inline-block bg-gradient-to-r ${flow.color} bg-clip-text [-webkit-background-clip:text] [-webkit-text-fill-color:transparent] text-[18px] font-bold mb-8`}>
                {flow.title}
              </div>
              <div className="space-y-5">
                {flow.steps.map((step, si) => {
                  const Icon = step.icon;
                  return (
                    <div key={si} className="flex items-center gap-4">
                      <div className="relative">
                        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${flow.color} flex items-center justify-center`}>
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                        {si < flow.steps.length - 1 && (
                          <div className="absolute left-1/2 top-full -translate-x-1/2 w-[2px] h-3 bg-[#3A3A3C]" />
                        )}
                      </div>
                      <span className="text-[15px] text-white/80 font-medium">{step.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </FadeIn>
        ))}
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: User Journey
// ---------------------------------------------------------------------------

const JourneySection = () => (
  <section className="py-32 relative bg-white">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <h2 className="text-4xl md:text-5xl font-extrabold text-center mb-24 text-[#1D1D1F] tracking-tight">
          一个团队的真实使用旅程。
        </h2>
      </FadeIn>

      <div className="grid md:grid-cols-4 gap-12 relative">
        <div className="hidden md:block absolute top-[28px] left-[10%] right-[10%] h-[1px] bg-[#E8E8ED]" />

        {[
          { step: '1', title: '导入资料，建立上下文', desc: '把客户资料、组织背景、历史纪要导入系统。AI 自动索引、切分、建立可检索的知识库。', icon: Database },
          { step: '2', title: '推进任务，产生事实', desc: '在熟悉的界面中管理任务和日历。每条任务自动挂到事件线上，跨周追踪推进状况。', icon: CheckSquare },
          { step: '3', title: '周复盘，提炼判断', desc: '每周系统自动采集事实，生成叙事分析、风险卡和机会卡。置信度不够时明确告诉你缺什么。', icon: Brain },
          { step: '4', title: '经验沉淀，能力升级', desc: '做过的事变成方法卡和经验沉淀。下一个面对类似问题的人，可以直接复用组织智慧。', icon: Award },
        ].map((item, i) => {
          const Icon = item.icon;
          return (
            <FadeIn key={i} delay={i * 150} className="relative text-center md:text-left">
              <div className="w-14 h-14 mx-auto md:mx-0 bg-white border-2 border-[#E8E8ED] rounded-full flex items-center justify-center mb-8 relative z-10 shadow-[0_0_0_8px_white]">
                <Icon className="w-5 h-5 text-[#5A52FF]" />
              </div>
              <div className="text-[13px] text-[#5A52FF] font-bold mb-2">步骤 {item.step}</div>
              <h3 className="text-[18px] font-bold mb-3 text-[#1D1D1F] tracking-tight">{item.title}</h3>
              <p className="text-[#86868B] text-[15px] leading-relaxed">{item.desc}</p>
            </FadeIn>
          );
        })}
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Open Source Philosophy
// ---------------------------------------------------------------------------

const OpenSourceSection = () => (
  <section className="py-32 bg-[#FBFBFD]">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-extrabold text-[#1D1D1F] tracking-tight leading-tight">
            选择开源，不是情怀。
            <br />
            <span className="text-[#86868B] font-semibold">而是更符合这件事本身的路径。</span>
          </h2>
        </div>
      </FadeIn>

      <div className="grid md:grid-cols-2 gap-8 mb-16">
        <FadeIn delay={100}>
          <div className="bg-white rounded-[2rem] p-10 shadow-[0_8px_30px_rgba(0,0,0,0.03)] h-full">
            <div className="w-12 h-12 rounded-2xl bg-[#F9F8FF] flex items-center justify-center mb-6">
              <Eye className="w-6 h-6 text-[#5A52FF]" />
            </div>
            <h3 className="text-[20px] font-bold text-[#1D1D1F] mb-3 tracking-tight">开源建立信任</h3>
            <p className="text-[#86868B] text-[16px] leading-[1.7]">
              我们面对的很多对象，更看重信任、可迁移、可共建，而不是被某个平台永久锁定。开源让软件本身成为一种公共过渡基础设施。
            </p>
          </div>
        </FadeIn>

        <FadeIn delay={200}>
          <div className="bg-white rounded-[2rem] p-10 shadow-[0_8px_30px_rgba(0,0,0,0.03)] h-full">
            <div className="w-12 h-12 rounded-2xl bg-[#F0FDF4] flex items-center justify-center mb-6">
              <TrendingUp className="w-6 h-6 text-[#10B981]" />
            </div>
            <h3 className="text-[20px] font-bold text-[#1D1D1F] mb-3 tracking-tight">影响力驱动商业</h3>
            <p className="text-[#86868B] text-[16px] leading-[1.7]">
              不靠锁住基础能力挣钱。用开源底座建立信任与影响力，通过部署、定制、维护、培训与行业共建获得可持续收入。
            </p>
          </div>
        </FadeIn>
      </div>

      {/* Community roles */}
      <FadeIn delay={100}>
        <div className="bg-white rounded-[2.5rem] p-12 shadow-[0_20px_60px_rgba(0,0,0,0.03)]">
          <h3 className="text-[24px] font-extrabold text-[#1D1D1F] mb-10 text-center tracking-tight">
            不只是程序员社区，而是复合型共同体
          </h3>
          <div className="grid md:grid-cols-4 gap-8">
            {[
              { icon: Code, title: '开发者', desc: '参与架构、模块、修复、插件与开源协作', color: 'bg-blue-50 text-blue-600' },
              { icon: Compass, title: '产品共建者', desc: '基于真实场景给功能优先级、流程设计和交互建议', color: 'bg-purple-50 text-purple-600' },
              { icon: Lightbulb, title: '知识贡献者', desc: '贡献谈判经验、评估经验、方法卡与行动检查清单', color: 'bg-amber-50 text-amber-600' },
              { icon: Handshake, title: '支持者', desc: '赞助模块、行业共建、传播或资源连接', color: 'bg-emerald-50 text-emerald-600' },
            ].map((role, i) => {
              const Icon = role.icon;
              return (
                <div key={i} className="text-center">
                  <div className={`w-14 h-14 ${role.color} rounded-2xl flex items-center justify-center mx-auto mb-5`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <h4 className="text-[17px] font-bold text-[#1D1D1F] mb-2">{role.title}</h4>
                  <p className="text-[14px] text-[#86868B] leading-relaxed">{role.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </FadeIn>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Current Focus
// ---------------------------------------------------------------------------

const FocusSection = () => (
  <section className="py-32 bg-white">
    <div className="max-w-5xl mx-auto px-6 md:px-10">
      <FadeIn>
        <h2 className="text-4xl font-extrabold text-center mb-6 text-[#1D1D1F] tracking-tight">
          专注当下：先接通底层连接。
        </h2>
        <p className="text-center text-[18px] text-[#86868B] mb-20 max-w-2xl mx-auto leading-relaxed">
          不追求"看起来更聪明"的表面升级。<br />
          先把现有功能下面的判断链与行动链接通，让软件真正成为一个可信的建议系统。
        </p>
      </FadeIn>

      <FadeIn delay={100}>
        <div className="bg-[#FBFBFD] rounded-[3rem] p-12 ring-1 ring-black/[0.02]">
          <div className="grid md:grid-cols-2 gap-16">
            <div>
              <h3 className="text-[20px] font-bold text-[#1D1D1F] mb-8 flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-[#5A52FF]" /> 优先接通
              </h3>
              <ul className="space-y-5 text-[16px] text-[#1D1D1F]/80 font-medium">
                {[
                  '真源与归属：每条任务、资料、事件线的来源理清楚',
                  '摘要预处理：会议、附件、文档真正进入可理解的上下文',
                  '统一上下文包：当前任务 + 角色 + 阶段 → 最相关的信息',
                  '可信判断引擎：先给信号和证据，再给解释和建议',
                  '降级机制：信息不够时明确说"缺什么"，而不是硬编',
                ].map((item, i) => (
                  <li key={i} className="flex gap-3 items-start">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#5A52FF] mt-2.5 shrink-0" />
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-[20px] font-bold text-[#86868B] mb-8 flex items-center gap-3">
                <XCircle className="w-6 h-6 text-[#A1A1A6]" /> 暂不优先
              </h3>
              <ul className="space-y-5 text-[16px] text-[#86868B]">
                {[
                  '大规模改版功能界面外观',
                  '盲目堆砌零散的边缘新模块',
                  '用漂亮页面掩盖底层未通的问题',
                ].map((item, i) => (
                  <li key={i} className="flex gap-3 items-start">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#A1A1A6] mt-2.5 shrink-0" />
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </FadeIn>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Navigation Cards
// ---------------------------------------------------------------------------

const NavigationSection = () => (
  <section className="py-32 bg-[#FBFBFD]">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <FadeIn>
        <h2 className="text-4xl font-extrabold text-center mb-20 text-[#1D1D1F] tracking-tight">探索更多。</h2>
      </FadeIn>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        {[
          { icon: <Code />, title: '开源理念', desc: '查看共建方式与贡献路径', btn: '深入了解' },
          { icon: <Download />, title: '下载中心', desc: '获取社区版，即刻本地体验', btn: '获取应用' },
          { icon: <ArrowUpRight />, title: 'GitHub', desc: '源码、Issue 与贡献指南', btn: '查看源码' },
          { icon: <BookOpen />, title: '开发文档', desc: '安装说明与高级配置手册', btn: '阅读文档' },
          { icon: <Users />, title: '共建计划', desc: '成为技术、产品或知识的贡献者', btn: '申请加入' },
          { icon: <Handshake />, title: '生态合作', desc: '机构部署与行业模块共建', btn: '联系我们' },
        ].map((item, i) => (
          <FadeIn key={i} delay={i * 50}>
            <div className="bg-white p-10 rounded-[2rem] hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)] transition-all duration-500 group">
              <div className="w-14 h-14 bg-[#F5F5F7] shadow-sm text-[#1D1D1F] rounded-full flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-[#5A52FF] group-hover:text-white transition-all duration-300">
                {item.icon}
              </div>
              <h3 className="text-[22px] font-bold mb-3 text-[#1D1D1F] tracking-tight">{item.title}</h3>
              <p className="text-[#86868B] text-[15px] mb-8">{item.desc}</p>
              <a href="#" className="inline-flex items-center gap-1 text-[15px] font-semibold text-[#5A52FF] hover:text-[#4c45df] transition-colors">
                {item.btn} <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </a>
            </div>
          </FadeIn>
        ))}
      </div>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Final CTA
// ---------------------------------------------------------------------------

const CtaSection = () => (
  <section className="py-40 relative text-center bg-white">
    <div className="max-w-4xl mx-auto px-6 relative z-10">
      <FadeIn>
        <h2 className="text-5xl md:text-6xl font-extrabold mb-8 tracking-tighter text-[#1D1D1F]">
          让普通团队<br />也能跨过 AI 鸿沟。
        </h2>
        <p className="text-[21px] text-[#86868B] mb-16 font-medium leading-relaxed">
          下载应用开始体验，或参与我们的开源共建。<br />
          <span className="text-[#A1A1A6]">技术不只属于少数人。</span>
        </p>
      </FadeIn>

      <FadeIn delay={200}>
        <div className="flex flex-col sm:flex-row justify-center gap-5">
          <button className="bg-[#1D1D1F] hover:bg-[#333336] text-white px-10 py-5 rounded-full font-semibold text-[17px] transition-all active:scale-95 shadow-md">
            下载社区版
          </button>
          <button className="bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#1D1D1F] px-10 py-5 rounded-full font-semibold text-[17px] transition-all active:scale-95">
            查看 GitHub
          </button>
        </div>
      </FadeIn>
    </div>
  </section>
);

// ---------------------------------------------------------------------------
// Section: Footer
// ---------------------------------------------------------------------------

const FooterSection = () => (
  <footer className="bg-[#F5F5F7] pt-20 pb-10 border-t border-[#E8E8ED]">
    <div className="max-w-7xl mx-auto px-6 md:px-10">
      <div className="grid md:grid-cols-4 gap-10 mb-16">
        <div className="md:col-span-1">
          <span className="text-[18px] font-bold text-[#1D1D1F] tracking-tight mb-4 block">益语智库</span>
          <p className="text-[#86868B] text-[13px] leading-relaxed">
            帮助普通团队在熟悉界面里进入 AI 协作时代。
          </p>
        </div>

        <div>
          <h4 className="font-semibold mb-4 text-[13px] text-[#1D1D1F]">快速导航</h4>
          <ul className="space-y-3 text-[13px] text-[#86868B]">
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">开源计划</a></li>
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">下载中心</a></li>
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">开发文档</a></li>
          </ul>
        </div>

        <div>
          <h4 className="font-semibold mb-4 text-[13px] text-[#1D1D1F]">参与共建</h4>
          <ul className="space-y-3 text-[13px] text-[#86868B]">
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">GitHub</a></li>
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">贡献者指南</a></li>
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">反馈建议</a></li>
          </ul>
        </div>

        <div>
          <h4 className="font-semibold mb-4 text-[13px] text-[#1D1D1F]">联系</h4>
          <ul className="space-y-3 text-[13px] text-[#86868B]">
            <li><a href="#" className="hover:text-[#1D1D1F] transition-colors">商业合作</a></li>
            <li>hello@yiyu.love</li>
          </ul>
        </div>
      </div>

      <div className="border-t border-[#E8E8ED] pt-6 flex flex-col md:flex-row justify-between items-center gap-4 text-[12px] text-[#A1A1A6]">
        <p>Copyright &copy; {new Date().getFullYear()} 益语智库. 保留所有权利。</p>
        <p>技术不只属于少数人。</p>
      </div>
    </div>
  </footer>
);

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function ShowcasePage() {
  useEffect(() => {
    const style = document.createElement('style');
    style.innerHTML = `
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

      :root {
        --apple-bg: #FBFBFD;
        --apple-text-title: #1D1D1F;
        --apple-text-body: #86868B;
        --yiyu-primary: #5A52FF;
      }

      body {
        background-color: var(--apple-bg);
        color: var(--apple-text-title);
        font-family: 'SF Pro Display', 'SF Pro Icons', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }

      @keyframes float-premium {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-12px); }
        100% { transform: translateY(0px); }
      }
    `;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  return (
    <div className="min-h-screen selection:bg-[#5A52FF] selection:text-white overflow-hidden relative text-[#1D1D1F]">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden bg-[#FBFBFD]">
        <div className="absolute top-[-20%] right-[-10%] w-[60%] h-[60%] bg-[#5A52FF] opacity-[0.02] blur-[150px] rounded-full" />
        <div className="absolute top-[30%] left-[-20%] w-[50%] h-[50%] bg-[#A855F7] opacity-[0.02] blur-[150px] rounded-full" />
      </div>

      <div className="relative z-10 pt-16 md:pt-24">
        <HeroSection />
        <ProblemSection />
        <DefinitionSection />
        <UniqueLayerSection />
        <ModulesSection />
        <WorkflowSection />
        <JourneySection />
        <OpenSourceSection />
        <FocusSection />
        <NavigationSection />
        <CtaSection />
      </div>

      <FooterSection />
    </div>
  );
}
